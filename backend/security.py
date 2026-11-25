
"""Anonymous, time-limited demo sessions with server-side rate limiting.

This is a lightweight interview-demo boundary, not a full user-account system.
In-memory/ephemeral disks lose data after service restarts on some hosting tiers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import db

LOGGER = logging.getLogger('career.security')
SESSION_TTL = 24 * 60 * 60


def hosted() -> bool:
    # Render sets RENDER automatically. Explicit opt-in supports other hosts.
    return bool(os.getenv('RENDER')) or os.getenv('CAREER_PUBLIC_DEMO') == '1'


def secret() -> bytes:
    value = os.getenv('CAREER_SESSION_SECRET', '')
    if len(value) < 32:
        raise RuntimeError('CAREER_SESSION_SECRET must be set to a random secret (>=32 chars) on Render')
    return value.encode('utf-8')


def _url_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def create_session_token() -> str:
    payload = {'id': secrets.token_urlsafe(24), 'exp': int(time.time()) + SESSION_TTL}
    encoded = _url_b64(json.dumps(payload, separators=(',', ':')).encode())
    signature = hmac.new(secret(), encoded.encode(), hashlib.sha256).digest()
    return f'{encoded}.{_url_b64(signature)}'


def verify_session_token(token: str) -> str | None:
    if not token or len(token) > 512 or token.count('.') != 1:
        return None
    try:
        encoded, supplied = token.split('.')
        expected = _url_b64(hmac.new(secret(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, supplied):
            return None
        raw = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        data = json.loads(raw)
        identity = data.get('id')
        if (not isinstance(identity, str) or len(identity) < 25 or
                not isinstance(data.get('exp'), int) or data['exp'] < time.time()):
            return None
        return identity
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return None


# This SQLite file is shared by all sessions of one application instance.
# Limits are atomic across worker processes sharing the same filesystem.
COUNTERS = db.DB_PATH.parent / 'demo_rate_counters.db'


def take_quota(rules: list[tuple[str, int, int]]) -> bool:
    """Atomically charge multiple buckets. Each tuple is (name, limit, period_s)."""
    COUNTERS.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    with sqlite3.connect(COUNTERS, timeout=15, isolation_level=None) as conn:
        conn.execute('PRAGMA busy_timeout=15000')
        conn.execute('CREATE TABLE IF NOT EXISTS quotas (bucket TEXT PRIMARY KEY, used INTEGER NOT NULL, expires INTEGER NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        try:
            conn.execute('DELETE FROM quotas WHERE expires <= ?', (now,))
            updates = []
            for name, limit, period in rules:
                slot = now // period
                key = f'{name}:{slot}'
                row = conn.execute('SELECT used FROM quotas WHERE bucket=?', (key,)).fetchone()
                current = row[0] if row else 0
                if current >= limit:
                    conn.execute('ROLLBACK')
                    return False
                updates.append((key, current + 1, (slot + 1) * period))
            for key, value, expiry in updates:
                conn.execute('INSERT INTO quotas(bucket,used,expires) VALUES(?,?,?) '
                             'ON CONFLICT(bucket) DO UPDATE SET used=excluded.used, expires=excluded.expires',
                             (key, value, expiry))
            conn.execute('COMMIT')
            return True
        except Exception:
            conn.execute('ROLLBACK')
            raise


def is_ai_call(method: str, path: str) -> bool:
    if method != 'POST':
        return False
    if path in {'/api/experiences/extract', '/api/jds',
                '/api/stories/generate', '/api/resumes/tailor',
                '/api/resumes/tailor/preview'}:
        return True
    if path.startswith('/api/experiences/') and path.endswith(('/question', '/answer')):
        return True
    if path.startswith('/api/stories/') and path.endswith('/introduction'):
        return True
    if path.startswith('/api/interviews/') and path.endswith('/reply'):
        return True
    return False


def install_security(app: FastAPI) -> None:
    @app.get('/api/session')
    async def new_demo_session(request: Request):
        if not hosted():
            return {'token': '', 'expires_in': 0, 'demo': False}
        try:
            secret()
        except RuntimeError:
            LOGGER.error('Missing CAREER_SESSION_SECRET')
            raise HTTPException(503, detail='线上会话配置未完成')
        ip = request.client.host if request.client else 'unknown'
        if not take_quota([(f'session-ip-minute:{ip}', 3, 60),
                           (f'session-ip-day:{ip}', 12, 86400),
                           ('session-global-day', 200, 86400)]):
            raise HTTPException(429, detail='今日演示会话创建次数已达上限，请稍后再试。')
        return {'token': create_session_token(), 'expires_in': SESSION_TTL, 'demo': True}

    @app.middleware('http')
    async def tenant_and_rate_limit(request: Request, call_next):
        if not hosted() or request.method == 'OPTIONS':
            return await call_next(request)

        path = request.url.path
        if not path.startswith('/api/') or path in {'/api/health', '/api/meta', '/api/session'}:
            return await call_next(request)
        if path in {'/api/export', '/api/data'}:
            return JSONResponse({'detail': '线上演示已关闭全量数据管理接口'}, status_code=403)

        auth = request.headers.get('Authorization', '')
        visitor = verify_session_token(auth[7:]) if auth.startswith('Bearer ') else None
        if not visitor:
            return JSONResponse({'detail': '演示会话已失效，请刷新页面重试'}, status_code=401)

        length = request.headers.get('content-length')
        if length and length.isdecimal() and int(length) > 6 * 1024 * 1024:
            return JSONResponse({'detail': '请求数据不能超过 6MB'}, status_code=413)

        ip = request.client.host if request.client else 'unknown'
        if is_ai_call(request.method, path):
            if not take_quota([
                (f'ai-visitor-minute:{visitor}', 3, 60),
                (f'ai-visitor-day:{visitor}', 10, 86400),
                (f'ai-ip-day:{ip}', 30, 86400),
                ('ai-global-day', 80, 86400),
            ]):
                return JSONResponse({'detail': 'AI 体验额度已用完，请稍后再试。'}, status_code=429)

        context = db.set_current_visitor(visitor)
        try:
            # All existing db.connection()/one()/all_rows() now use this visitor's file.
            db.init_db()
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            db.reset_current_visitor(context)

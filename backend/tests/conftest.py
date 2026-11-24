import os
import tempfile
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ['CAREER_DB_PATH'] = str(Path(_tmp.name) / 'test.db')
os.environ.pop('OPENAI_API_KEY', None)

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.delete('/api/data')
        yield c

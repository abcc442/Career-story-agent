# Career Story Agent — 求职职业叙事 Agent

一个可本地运行的全栈 MVP：**认识经历 → 理解岗位 → 构建职业故事 → 简历表达 → 模拟面试**。重点不是关键词润色，而是将真实经历和岗位要求之间的关系明确呈现，并要求用户确认事实。

## 实现范围

- 上传 PDF / DOCX / TXT / MD 简历，提取原文（扫描版 PDF 不支持 OCR）。
- 从简历提取经历**草稿**；用户可编辑事实、添加技能、手动确认。
- Agent 对单段经历主动追问，生成**待确认**的字段更新建议。
- 输入岗位 JD，分析要求与优先级。
- 仅用**已确认**的经历做证据匹配，指出缺口、排序及原因。
- 生成岗位相关的职业定位、主线、简历素材和面试自我介绍。
- 多轮模拟面试，每轮问题与回答保存在本地 SQLite。
- 导出 JSON 数据、删除所有本地数据，提供示例内容体验完整流程。
- 本地模式无需 API Key，但只是关键词规则演示（不会冒充 AI 理解）。

## 技术栈

React + TypeScript + Vite；FastAPI + Pydantic + SQLite；OpenAI Agents SDK（接入 API Key 后启用）。

## Windows PowerShell — 启动后端

在项目根目录执行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

若系统未安装 `py`，可使用 `python -m venv .venv`。

验证：<http://127.0.0.1:8000/api/health>，期待 `{"status":"ok"}`。

## 启动前端（新开 PowerShell 终端）

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>。

## 开启真正的 AI Agent

1. 复制项目根目录的 `.env.example` 为 `.env`。
2. 在 `.env` 中填写你自己的 `OPENAI_API_KEY=...`（**不要把 Key 发给任何人、提交到 Git 或放进前端**）。
3. 默认模型是 `gpt-4.1-mini`；若账户支持其他模型，可修改 `OPENAI_MODEL`。
4. 重启后端。顶部状态将显示 **真实 AI 模式**。

无 Key 时显示 **本地规则演示**；演示匹配基于字符串关键词，面试不会评价回答质量。示例经历是**虚构演示数据**，不能当成个人履历使用。

**收费提醒：** 真实 API 请求会按提供商 API 计费，与 ChatGPT 网页会员订阅不同。

### Agent 工作流（真实模式）

```
简历/项目资料 → 结构化经历草稿 → 用户确认 → SQLite 长期经历库
                                      ↓
岗位 JD → 结构化要求 → Agent 调用 read_confirmed_experiences 工具
                                ↓
                    有来源的证据匹配/能力缺口
                                ↓
              职业定位 + 经历排序 + 故事主线
                                ↓
                  简历素材 / 面试自我介绍
                                ↓
                    多轮追问与反馈
```

- 使用单个**可配置的 Agent**，不同任务执行结构化输出，而不是堆砌多个 Agent。
- `read_confirmed_experiences` 是真正的 Agents SDK `function_tool`，允许 Agent 查询受控的已确认事实。
- Pydantic 输出类型和经历 ID 过滤可减少无效引用；未核实的数字会提示人工审核，但**不能保证模型绝不发生事实错误**。
- Agent 追问仅返回建议，只有用户在表单中保存并再次确认后，事实才进入证据库。
- 故事存储为版本快照，修改经历后需主动重新生成故事。
- 默认关闭 SDK 云端执行追踪（`OPENAI_AGENTS_DISABLE_TRACING=1`），避免无意发送额外日志。

## 测试

在项目根目录：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

前端静态检查和生产构建：

```powershell
cd frontend
npm run build
```

## 重要限制与后续工作

- **这是本地单用户 MVP，不是已发布的互联网 SaaS。** 无登录、鉴权、限流和部署安全策略；不可直接暴露公网或向他人开放 API。
- 用户资料保存在 `backend/data/career.db`（默认本地文件）。PDF/DOCX 文件在内存中读取，**不保存上传文件本身**；用户接受后保存提取的文字。若启用 AI，相关文本会发送到配置的大模型 API。
- 资料本地存储不代表端到端加密；开发电脑的文件权限与备份需自行管理。
- 纯文本 PDF 可解析，扫描图 PDF 暂不支持 OCR。
- 简历 TXT 导出仅提供素材；完整 Word / PDF 排版暂不属于 MVP。
- 真实模型调用必须填写可用 API Key，并要求实际网络联通；提供代码不等同于已验证远程模型效果。
- 正式投入使用前，建议补充：多账号认证、密钥/数据保护、模型输出事实对照、监控与成本约束、人工评测集、隐私政策及数据删除流程。

## 目录

```
backend/
  main.py         HTTP API / 上传解析 / 人工确认工作流
  ai_service.py   单 Agent 结构化任务、工具调用、演示逻辑
  db.py           SQLite 持久化和执行结果记录
  schemas.py      Pydantic 数据契约
  tests/          离线接口集成测试
frontend/
  src/App.tsx     全部工作流页面、交互和状态
  src/api.ts      API 请求封装
  src/types.ts    TypeScript 类型
  src/styles.css  响应式 UI 样式
.env.example      模型配置模板
```

## 更简单的 Windows 启动方式

也可以直接双击项目根目录的 `start_windows.bat`。它会检查 Python 和 npm、安装依赖并分别启动前后端；第一次运行需要联网安装依赖。若脚本报错，使用上面的手动命令定位错误。**请先查看脚本内容再运行。**


## 本次更新（经历库与岗位定制 Word 简历）

### 经历库分类
- 增加实习、正式工作、独立项目、科研、竞赛、校园、其他类型。
- 项目可选关联到一段实习/工作经历。
- 原有 SQLite 数据会在后端启动时自动补充新字段，不会清空旧记录；历史记录默认显示为“待分类/其他”，需用户核对后手动分类，避免 AI 擅自猜测。
- 经历库新增类型筛选；编辑经历时可修改类型和所属实习/工作。

### 岗位定制 Word 简历
1. 先在「理解岗位」录入并分析目标 JD。
2. 在右侧「生成岗位定制 Word 简历」区域上传 `.docx` 简历。
3. 点击「生成定制简历并下载」。
4. 系统会根据 JD 重组内容、调整经历顺序和表达，并导出新的 `.docx` 文件。
5. 原始简历不会被覆盖；文档末尾附有 AI 修改说明和提交前核对事项。

限制与事实边界：
- 当前岗位定制功能只接受 `.docx`，最大 5MB；扫描图片型 Word 可能无法读取。
- 需要真实 AI 模式；规则演示模式不会伪装成 AI 改写。
- AI 只应改写原简历已有事实，不得虚构职责、数字、成果或技能。请逐条核对生成结果后再投递。
- 当前导出为清爽的标准 Word 排版，不保证像素级保留原始 Word 模板的复杂版式。

### DeepSeek 配置示例
在项目根目录创建 `.env`（不要上传或提交该文件）：
```env
OPENAI_API_KEY=你的DeepSeek_API_Key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
OPENAI_AGENTS_DISABLE_TRACING=1
```
请以 DeepSeek 控制台当前显示的 API 地址和模型名称为准。配置 `.env` 后重启后端。

### 安全提示
分享项目压缩包前，请删除 `.env`。如果密钥曾经进入聊天、截图或压缩包，应在服务商控制台撤销旧密钥并重新生成。

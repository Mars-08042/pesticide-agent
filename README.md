# 农药智能体（Pesticide Agent）

基于 FastAPI + LangGraph 的农药配方生成与优化系统。当前主运行形态为：

- 后端提供会话、对话流式响应、事件推送三组 API
- 前端提供聊天与会话管理界面
- 配方知识库的分块、检索、重排序与工具封装仍保留在后端，供 RAG、数据导入和后续能力扩展使用

## 当前状态

- **后端真实路由**：`/api/session`、`/api/chat`、`/api/events`、`/health`
- **已移除接口**：`/api/knowledge`、`/api/recipe-kb`、`/api/upload`
- **前端现状**：当前前端聚焦聊天、会话与右侧辅助面板；知识库管理/上传页面已移除，不再作为主链路功能暴露
- **保留模块**：`backend/tools`、`backend/rag/retrieval/hybrid_retriever.py`、`backend/tools/recipe_kb_retriever.py` 仍然保留

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / LangGraph / LangChain |
| 前端 | React 19 / Vite / TypeScript |
| 数据库 | PostgreSQL 16 + pgvector |
| 模型接入 | OpenAI 兼容接口（OpenRouter / VLLM） |
| 检索 | 向量检索 + Rerank 重排序 |

## 目录结构

```text
pesticide_agent/
├── backend/                  # Python 后端
│   ├── agent/               # LangGraph 工作流与子图
│   ├── api/                 # FastAPI 服务、SSE 与会话持久化
│   ├── infra/               # 配置、数据库、日志、任务管理
│   ├── rag/                 # 文档分块、向量检索与重排序
│   ├── tools/               # 检索/搜索/抓取工具封装（保留）
│   ├── knowledge_base/      # Markdown 知识库原始文件
│   ├── scripts/             # 数据导入与初始化脚本
│   └── docs/                # 设计与实现文档
├── frontend/                # React 前端
│   ├── src/
│   └── .env.example         # 前端可选环境变量模板
├── dify-rag-reference/      # 参考实现，不参与主运行链路
├── CLAUDE.md                # Claude Code 协作说明
└── AGENTS.md                # 通用仓库协作规范
```

## 快速开始

### 1. 准备环境变量

```powershell
Copy-Item backend/.env.example backend/.env
```

如果前端需要连接非默认后端地址，可额外创建：

```powershell
Copy-Item frontend/.env.example frontend/.env.local
```

### 2. 启动数据库

```powershell
Set-Location backend
docker-compose up -d
```

### 3. 启动后端

```powershell
Set-Location backend
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

可选 CLI 模式：

```powershell
Set-Location backend
python main.py
python main.py --query "帮我设计一个吡唑醚菌酯 25% SC 配方"
```

### 4. 启动前端

```powershell
Set-Location frontend
npm install
npm run dev
```

默认访问 `http://localhost:5173`。

## API 与前端说明

启动后端后可访问 `http://localhost:8000/docs` 查看 Swagger 文档。

| 路由前缀 | 功能 |
|---------|------|
| `/api/chat` | 对话接口（SSE 流式响应） |
| `/api/session` | 会话管理 |
| `/api/events` | 事件推送 |
| `/health` | 健康检查 |

说明：

- 当前前端不再暴露知识库管理、配方知识库管理和上传页面
- 后端 RAG / 工具链仍保留，用于数据导入、检索封装和后续功能恢复

## 配置说明

主要配置项见 `backend/.env.example`。当前模板要求与本地 `backend/.env` 保持**键名与顺序同步**。

| 变量 | 用途 |
|------|------|
| `OPENROUTER_API_KEY` / `LLM_MODEL_NAME` | 主对话模型配置 |
| `EMBEDDING_*` | 向量化模型配置 |
| `RERANK_*` | 重排序模型配置 |
| `POSTGRES_*` | PostgreSQL + pgvector 连接配置 |
| `VECTOR_SEARCH_TOP_N` | 向量检索初筛召回数量 |
| `RETRIEVAL_FINAL_TOP_K` | 最终返回数量（Rerank 成功或降级时统一生效） |
| `RECIPE_KB_MAX_CHUNK_WORDS` / `RECIPE_KB_MIN_CHUNK_WORDS` | Markdown 分块阈值 |
| `SERPER_KEY_ID` / `TAVILY_API_KEY` / `JINA_API_KEYS` | 搜索与网页抓取能力 |

前端当前仅有一个可选环境变量：

| 文件 | 变量 | 用途 |
|------|------|------|
| `frontend/.env.example` | `VITE_API_BASE_URL` | 覆盖默认后端地址 |

## 开发与验证

- 后端细节：见 `backend/README.md`
- 协作说明：见 `CLAUDE.md` 与 `AGENTS.md`

常用验证命令：

```powershell
Set-Location backend
python -B -m py_compile infra/config.py rag/retrieval/hybrid_retriever.py tools/recipe_kb_retriever.py

Set-Location ..\\frontend
npm run build
```

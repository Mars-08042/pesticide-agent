# Backend 目录说明

## 概述

`backend/` 是当前项目的真实后端主链路，负责：

- FastAPI API 与 SSE 流式响应
- LangGraph 工作流与配方生成/优化
- 知识库 Markdown 分块、向量检索与重排序
- 检索工具与数据导入脚本

## 当前真实入口

### API 服务

```powershell
Set-Location backend
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### CLI 模式

```powershell
Set-Location backend
python main.py
python main.py --query "帮我设计一个吡唑醚菌酯 25% SC 配方"
```

### 数据库

```powershell
Set-Location backend
docker-compose up -d
```

## 目录职责

```text
backend/
├── agent/               # LangGraph 工作流、状态与子图
├── api/                 # FastAPI 服务、路由、SSE、执行与持久化
├── infra/               # 配置、数据库、日志、任务管理
├── rag/                 # 分块器、向量检索与重排序
├── tools/               # 搜索、抓取、配方知识库检索工具（保留）
├── knowledge_base/      # Markdown 知识库源文件
├── scripts/             # 数据导入与初始化脚本
├── docs/                # 设计 / 实现说明
├── main.py              # CLI 入口
├── requirements.txt     # Python 依赖
└── docker-compose.yml   # PostgreSQL + pgvector
```

## API 路由

当前 `backend/api/server.py` 实际注册的路由有：

| 路由前缀 | 功能 |
|---------|------|
| `/api/session` | 会话管理 |
| `/api/chat` | 对话与流式响应 |
| `/api/events` | 事件推送 |
| `/api/materials` | 原药 / 助剂管理 |
| `/health` | 健康检查 |

说明：

- 旧的 `/api/knowledge`、`/api/recipe-kb`、`/api/upload` 已不在当前主链路中
- 若文档、脚本或前端代码再次出现这些接口，应先以 `backend/api/server.py` 为准

## 工作流与检索

### Agent 主链

- `agent.graph.PesticideAgent` 负责封装 LangGraph 图
- `api.dependencies` 负责资源初始化与生命周期，不再使用旧的 `infra/container.py`
- `agent/workflow` 提供状态、节点、日志与图构建
- 聊天请求当前由前端显式选择 `generation` / `optimization`；不再保留自动路由分支
- 当 `enable_web_search=true` 且本地检索无法确认时，子图会调用 `tools/web_search.py` 与 `tools/content_scraper.py` 补充真实网页资料；若仍不足，则直接返回失败提示而不是猜测

### RAG / 工具链

以下模块虽然当前没有对应的前端管理页面，但仍然属于保留能力：

- `rag/chunker/markdown_chunker.py`：Markdown 分块
- `rag/retrieval/hybrid_retriever.py`：向量检索 + Rerank
- `tools/recipe_kb_retriever.py`：对外统一的配方知识库检索封装
- `tools/web_search.py` / `tools/content_scraper.py`：联网搜索与网页抓取
- `scripts/data_import/recipe_chunks.py`：知识库切分、元数据提取、入库

## 配置项

复制环境模板：

```powershell
Copy-Item .env.example .env
```

关键配置分组如下：

| 类别 | 变量 | 用途 |
|------|------|------|
| LLM | `OPENROUTER_API_KEY` / `LLM_MODEL_NAME` | 主对话模型 |
| Embedding | `EMBEDDING_*` | 向量化模型 |
| Rerank | `RERANK_*` | 重排序模型 |
| 数据库 | `POSTGRES_*` | PostgreSQL + pgvector |
| 检索 | `VECTOR_SEARCH_TOP_N` | 向量初筛召回数量 |
| 检索 | `RETRIEVAL_FINAL_TOP_K` | 最终返回数量（Rerank 成功或降级时统一生效） |
| 分块 | `RECIPE_KB_MAX_CHUNK_WORDS` / `RECIPE_KB_MIN_CHUNK_WORDS` | 文档分块阈值 |
| 工具 | `SERPER_KEY_ID` / `TAVILY_API_KEY` / `JINA_API_KEYS` | 搜索与抓取 |

## 真实导入约定

```python
from infra.config import get_config
from infra.database import get_db_manager
from api.dependencies import get_agent, get_database

from agent.graph import get_pesticide_agent
from agent.workflow.state import AgentState

from rag.retrieval.hybrid_retriever import get_hybrid_retriever
from tools.recipe_kb_retriever import get_recipe_kb_retriever_tool
```

## 验证建议

常用轻量验证：

```powershell
Set-Location backend
python -B -m py_compile infra/config.py rag/chunker/markdown_chunker.py rag/retrieval/hybrid_retriever.py tools/recipe_kb_retriever.py
pytest -q scripts/data_import/test_recipe_chunks.py
```

说明：

- `pytest` 当前主要覆盖导入 / 分块相关示例
- 若只改文档、配置模板或注释，通常用 `rg`、`git diff`、`py_compile` 即可

## Windows 注意事项

- `api/server.py` 已显式设置 `WindowsSelectorEventLoopPolicy`
- 路径与文件读写示例优先按 PowerShell 书写
- 文档或配置发生变化时，`README.md`、`backend/README.md`、`CLAUDE.md`、`AGENTS.md` 应同步更新

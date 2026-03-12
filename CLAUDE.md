# CLAUDE.md

本文件用于说明 Claude Code / Codex 类代理在本仓库中的协作边界与当前真实状态。若代码与文档冲突，**始终以代码为准**。

## 项目概览

农药智能体（Pesticide Agent）当前是一套：

- **后端**：FastAPI + LangGraph 的聊天 / 会话 / 事件推送 / 原药助剂管理服务
- **前端**：React + Vite 的聊天界面，附带原药 / 助剂数据管理弹层
- **检索能力**：保留 Markdown 分块、向量检索、Rerank、检索工具封装和数据导入脚本

当前主功能以聊天、配方生成/优化、检索，以及原药 / 助剂数据管理为主，但仍不暴露旧的知识库管理与上传接口。

## 真实入口

### 后端

```powershell
Set-Location backend
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### CLI

```powershell
Set-Location backend
python main.py
python main.py --query "帮我设计一个吡唑醚菌酯 25% SC 配方"
```

### 前端

```powershell
Set-Location frontend
npm install
npm run dev
npm run build
```

### 数据库

```powershell
Set-Location backend
docker-compose up -d
```

## 当前真实结构

```text
pesticide_agent/
├── backend/
│   ├── agent/              # LangGraph 工作流与子图
│   ├── api/                # FastAPI 服务、路由、SSE、执行与持久化
│   ├── infra/              # 配置、数据库、日志、任务管理
│   ├── rag/                # 分块与检索
│   ├── tools/              # 搜索/抓取/配方检索工具（保留）
│   ├── knowledge_base/     # Markdown 知识库
│   ├── scripts/            # 数据导入与初始化脚本
│   └── docs/               # 设计文档
├── frontend/
│   ├── src/components/
│   ├── src/hooks/
│   ├── src/api/
│   └── .env.example
├── README.md
├── backend/README.md
├── AGENTS.md
└── CLAUDE.md
```

说明：

- 旧的 `backend/infra/container.py` 已删除，资源生命周期由 `backend/api/dependencies.py` 管理
- `backend/tools` 必须保留；即使当前前端不直接使用，也不要把它当成可随手删除的死目录
- `dify-rag-reference/` 仍是参考目录，不属于当前主运行链路

## 当前真实 API

以 `backend/api/server.py` 为准，当前后端只注册：

| 路由前缀 | 用途 |
|---------|------|
| `/api/session` | 会话管理 |
| `/api/chat` | 对话与 SSE |
| `/api/events` | 事件推送 |
| `/api/materials` | 原药 / 助剂管理 |
| `/health` | 健康检查 |

下列旧接口已不在主链路：

- `/api/knowledge`
- `/api/recipe-kb`
- `/api/upload`

如果未来再次恢复这些接口，必须同步更新 README、CLAUDE、AGENTS 与前端说明。

## 前端现状

- 当前前端聚焦聊天、会话和右侧辅助面板
- 右侧知识库框已新增原药 / 助剂数据管理入口，支持分页查询、增删改查和 JSON 自动填充
- 旧的知识库文档管理 / 配方知识库管理 / 上传页面仍未恢复
- `useKnowledgeBase` 仍只保留知识库选择的本地状态壳层，不负责文档管理接口

因此，凡是涉及前端功能说明，都不要再写“可在 UI 中管理知识库文档/上传文件”，除非相关代码和路由已恢复

## 检索与数据导入

当前仍然保留、且文档中应明确的能力：

- `rag/chunker/markdown_chunker.py`：Markdown 分块
- `rag/retrieval/hybrid_retriever.py`：向量检索 + Rerank
- `tools/recipe_kb_retriever.py`：对外统一的检索封装
- `scripts/data_import/recipe_chunks.py`：切分、元数据提取、入库
- `tools/web_search.py` / `tools/content_scraper.py`：联网搜索与网页抓取

## 配置纪律

### 后端配置

后端所有真实可配置项以 `backend/.env` 和 `backend/.env.example` 为准。当前重要项包括：

- `VECTOR_SEARCH_TOP_N`：向量检索初筛召回数
- `RETRIEVAL_FINAL_TOP_K`：最终返回数量（Rerank 成功或降级时统一使用）
- `RECIPE_KB_MAX_CHUNK_WORDS` / `RECIPE_KB_MIN_CHUNK_WORDS`：Markdown 分块阈值

### 维护要求

- 修改 `backend/.env` 的键时，必须同步更新 `backend/.env.example`
- `backend/.env.example` 与 `backend/.env` 要保持**键名与顺序一致**
- 不要把真实密钥写入示例文件、README、CLAUDE、AGENTS

## 修改文档时的同步要求

以下内容一旦变化，应同步更新：

- 根 README：用户视角的启动方式、API、配置与前端现状
- `backend/README.md`：后端目录、真实路由、导入约定、RAG / 工具链
- `CLAUDE.md`：代理协作说明
- `AGENTS.md`：通用仓库规范

高频需要同步的变更包括：

- 新增 / 删除 API 路由
- 配置键改名或新增
- 目录结构变化（尤其是 `infra/`、`tools/`、`frontend/src/api/`）
- 前端功能页被删除或恢复

## 建议验证

如果改动涉及配置、检索或后端导入链，优先执行：

```powershell
Set-Location backend
python -B -m py_compile infra/config.py rag/chunker/markdown_chunker.py rag/retrieval/hybrid_retriever.py tools/recipe_kb_retriever.py
```

如果改动涉及前端说明或接口接线，优先执行：

```powershell
Set-Location frontend
npm run build
```

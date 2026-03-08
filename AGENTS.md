# Repository Guidelines

## Project Structure & Current State
仓库采用前后端分离结构。`backend/` 是当前真实主链路，包含 `agent/`（LangGraph 工作流与子图）、`api/`（FastAPI 路由、SSE、执行与持久化）、`infra/`（配置、数据库、日志、任务管理）、`rag/`（文档分块、向量检索与重排序）、`tools/`（搜索、抓取、配方检索工具）和 `scripts/`（数据导入与初始化 SQL）。`frontend/` 为 React 19 + Vite + TypeScript 聊天界面。`dify-rag-reference/` 仅作参考，不参与当前主运行链路。

当前后端实际只注册 `/api/session`、`/api/chat`、`/api/events` 与 `/health`；旧的 `/api/knowledge`、`/api/recipe-kb`、`/api/upload` 已移出主链路。前端也不再提供知识库管理 / 上传页面。`backend/tools`、`backend/rag/retrieval/hybrid_retriever.py` 和 `backend/tools/recipe_kb_retriever.py` 需要保留，不要因为前端未直连就误删。

## Build, Test, and Development Commands
- `cd backend && pip install -r requirements.txt`：安装后端依赖。
- `cd backend && docker-compose up -d`：启动 PostgreSQL + pgvector。
- `cd backend && python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000`：启动后端 API。
- `cd backend && python main.py`：启动 CLI 交互模式。
- `cd backend && python main.py --query "..."`：执行单次查询。
- `cd frontend && npm install`：安装前端依赖。
- `cd frontend && npm run dev`：启动前端开发服务。
- `cd frontend && npm run build && npm run preview`：构建并本地预览生产包。

## Coding Style & Naming Conventions
Python 使用 4 空格缩进，模块/函数采用 `snake_case`，建议为对外接口补充类型标注。TypeScript/React 使用函数组件，组件文件采用 `PascalCase`，Hook 使用 `useXxx` 命名并放在 `frontend/src/hooks`。前端优先使用 `@/` 路径别名；不要恢复已经删除的 `recipe-kb` / `knowledge` 旧接口封装，除非后端对应路由已先恢复。

## Configuration Discipline
后端环境变量模板位于 `backend/.env.example`，真实本地配置位于 `backend/.env`。两者必须保持**键名与顺序一致**，新增、删除或改名配置项时要同步两边。当前检索相关关键配置包括：
- `VECTOR_SEARCH_TOP_N`：向量初筛召回数
- `RETRIEVAL_FINAL_TOP_K`：最终返回数量（Rerank 成功或降级时都生效）
- `RECIPE_KB_MAX_CHUNK_WORDS` / `RECIPE_KB_MIN_CHUNK_WORDS`：Markdown 分块阈值

前端可选环境变量模板位于 `frontend/.env.example`，当前只包含 `VITE_API_BASE_URL`。

## Testing Guidelines
后端依赖中已包含 `pytest`，当前自动化测试主要集中在 `backend/scripts/data_import/test_recipe_chunks.py`。新增后端测试建议统一放在 `backend/tests/` 并命名为 `test_*.py`。涉及配置、检索、工具链调整时，优先使用 `python -B -m py_compile ...` 做轻量验证；涉及前端接线和文档同步时，优先执行 `cd frontend && npm run build`。前端目前未配置测试框架，不要在文档中虚构 `npm test`。

## Documentation Sync Rules
当以下内容变化时，必须同步更新 `README.md`、`backend/README.md`、`CLAUDE.md`、`AGENTS.md`：
- 后端路由新增/删除
- 目录结构变化（尤其是 `infra/`、`tools/`、`frontend/src/api/`）
- 配置项新增、删除、改名或默认值变化
- 前端功能页删除、恢复或主链路切换

如果文档内容与代码冲突，始终以 `backend/api/server.py`、`backend/infra/config.py`、`frontend/src/App.tsx` 和当前真实文件树为准。

## Commit & Pull Request Guidelines
现有提交历史以简洁中文主题为主。建议提交信息使用 `<scope>: <简短动作说明>`，例如 `backend-rag: 新增最终返回数量配置`。PR 至少包含：变更摘要、影响目录、执行过的命令与结果、配置项变更说明；涉及接口变更时应明确写出新增/移除的路由，涉及文档修订时说明与代码对齐的依据。

## Security & Windows Notes
禁止把真实密钥写入仓库文档、示例配置或记忆文件。Windows 开发环境下优先使用 PowerShell 命令示例；路径包含空格时必须加引号。`api/server.py` 已处理 `WindowsSelectorEventLoopPolicy`，涉及异步数据库或 SSE 问题时先确认这一层，而不是先怀疑前端。

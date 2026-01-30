# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

农药智能体 (Pesticide Agent) - 一个基于 LangGraph 的农药配方生成与优化系统。

**技术栈**:
- 后端: Python 3.10+ / FastAPI / LangGraph / LangChain
- 前端: React 19 / Vite / TypeScript / TailwindCSS
- 数据库: PostgreSQL 16 + pgvector (向量存储)
- LLM: OpenAI 兼容接口 (支持 OpenRouter/VLLM)

## 常用命令

### 后端

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 启动 API 服务器
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

# CLI 交互模式
python main.py

# 单次查询模式
python main.py --query "帮我设计一个吡唑醚菌酯 25% SC 配方"
```

### 前端

```bash
cd frontend
npm install
npm run dev      # 开发服务器 (http://localhost:5173)
npm run build    # 生产构建
```

### 数据库

```bash
cd backend
docker-compose up -d   # 启动 PostgreSQL + pgvector
```

## 架构概览

```
pesticide_agent/
├── backend/
│   ├── agent/                    # LangGraph Agent 模块
│   │   ├── workflow/             # Agent 工作流内核
│   │   │   ├── state.py          # AgentState 定义
│   │   │   ├── nodes.py          # 节点实现
│   │   │   ├── builder.py        # 图构建器
│   │   │   └── prompts.py        # Prompt 模板
│   │   └── subgraphs/            # 子图（配方生成/优化）
│   │
│   ├── api/                      # FastAPI 服务
│   │   ├── server.py             # 应用入口
│   │   ├── routers/              # API 路由
│   │   ├── streaming/            # SSE 流式响应
│   │   ├── execution/            # 图执行器
│   │   └── persistence/          # 消息持久化
│   │
│   ├── infra/                    # 基础设施层
│   │   ├── config.py             # 统一配置 (AppConfig)
│   │   ├── database.py           # PostgreSQL + pgvector
│   │   ├── container.py          # 依赖注入容器
│   │   └── logger.py             # 日志配置
│   │
│   ├── rag/                      # RAG 模块
│   │   ├── chunker/              # 文档分块
│   │   └── retriever/            # 向量检索与重排序
│   │
│   ├── tools/                    # Agent 工具层
│   │   ├── web_search.py         # 联网搜索
│   │   └── web_scraper.py        # 网页抓取
│   │
│   ├── knowledge_base/           # 知识库 (Markdown)
│   │   ├── 01-原药信息/
│   │   ├── 02-助剂信息/
│   │   ├── 03-制剂配方/
│   │   └── 04-配方实验/
│   │
│   └── scripts/                  # 脚本
│       ├── data_import/          # 数据导入
│       └── docker-init/          # Docker 初始化
│
└── frontend/                     # React 前端
    └── src/
        ├── components/           # UI 组件
        ├── hooks/                # React Hooks
        └── api/                  # API 调用
```

## Agent 工作流

采用 LangGraph 状态机架构，两种主要模式:

1. **generation** (配方生成): 根据用户需求生成新配方
2. **optimization** (配方优化): 对现有配方进行优化

流程: `START → dispatcher → recipe (子图) → END`

- `dispatcher`: 路由分发，支持 auto 模式自动判断意图
- `recipe`: 配方生成/优化子图，包含多轮 ReAct 推理

## 关键状态定义

`AgentState` (backend/agent/workflow/state.py):
- `messages`: 消息历史
- `intent`: 意图 (generation/optimization)
- `route_mode`: 路由模式 (auto/generation/optimization)
- `original_recipe`: 原始配方文本 (优化模式必填)
- `optimization_targets`: 优化目标列表
- `steps`: 执行步骤日志 (用于前端展示)
- `kb_ids`: 知识库文档 ID 列表

## 配置管理

所有配置集中在 `infra/config.py`，通过环境变量覆盖:

```python
from infra.config import get_config
config = get_config()

# 主要配置项
config.server.port           # API 端口
config.database.host         # 数据库地址
config.agent.max_iterations  # Agent 最大迭代次数
```

环境变量示例 (`.env`):
```
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=pesticide123
API_PORT=8000
AGENT_MAX_ITERATIONS=5
```

## API 路由

| 路由前缀 | 功能 |
|---------|------|
| `/api/chat` | 对话接口 (SSE 流式响应) |
| `/api/session` | 会话管理 |
| `/api/knowledge` | 知识库管理 |
| `/api/recipe-kb` | 配方知识库管理 |
| `/api/events` | 事件推送 |
| `/api/upload` | 文件上传 |

## Windows 开发注意事项

- psycopg3 异步模式需要 `WindowsSelectorEventLoopPolicy`（已在 `api/server.py` 中配置）
- 确保 PostgreSQL 已安装 pgvector 扩展

# Backend 目录结构说明

## 概述

农药智能体后端服务，基于 FastAPI + LangGraph 构建。

## 目录职责

```
backend/
├── agent/              # LangGraph Agent 模块
│   ├── workflow/       # Agent 工作流内核（状态/节点/图构建/提示词）
│   └── subgraphs/      # 子图实现（配方生成/优化等）
│
├── api/                # FastAPI 接口层
│   ├── routers/        # API 路由定义
│   ├── streaming/      # SSE 流式响应
│   ├── execution/      # 图执行器
│   └── persistence/    # 消息持久化
│
├── infra/              # 基础设施层
│   ├── config.py       # 统一配置管理
│   ├── database.py     # PostgreSQL + pgvector
│   ├── container.py    # 依赖注入容器
│   └── logger.py       # 日志配置
│
├── rag/                # RAG 分块与检索
│   ├── chunker/        # 文档分块策略
│   └── retriever/      # 向量检索与重排序
│
├── tools/              # Agent 工具层
│   ├── web_search.py   # 联网搜索
│   ├── web_scraper.py  # 网页抓取
│   └── ...
│
├── knowledge_base/     # 知识库文件
│   ├── 01-原药信息/    # 原药信息文档
│   ├── 02-助剂信息/    # 助剂信息文档
│   ├── 03-制剂配方/    # 制剂配方文档
│   └── 04-配方实验/    # 配方实验记录
│
├── scripts/            # 脚本
│   ├── data_import/    # 数据导入脚本
│   └── docker-init/    # Docker 初始化 SQL
│
├── docs/               # 开发文档与对话记录
├── main.py             # CLI 入口
├── requirements.txt    # Python 依赖
└── docker-compose.yml  # 数据库 Docker 配置
```

## 运行方式

### CLI 交互模式

```bash
python main.py
```

### Web API 服务

```bash
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### 数据库

```bash
docker-compose up -d
```

## 导入路径约定

```python
# 基础设施
from infra.config import get_config
from infra.database import get_db_manager

# Agent
from agent.workflow.state import AgentState
from agent.graph import create_agent_graph

# 工具
from tools import get_web_search_tool

# RAG
from rag.retriever import retrieve_documents
```

## 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

主要配置项：

| 类别 | 变量 | 说明 |
|------|------|------|
| LLM | `OPENROUTER_API_KEY` | API 密钥 |
| LLM | `LLM_MODEL_NAME` | 模型名称 |
| 数据库 | `POSTGRES_HOST` | 数据库地址 |
| 数据库 | `POSTGRES_PORT` | 数据库端口 |
| 数据库 | `POSTGRES_PASSWORD` | 数据库密码 |
| Embedding | `EMBEDDING_API_KEY` | Embedding API 密钥 |
| Rerank | `RERANK_API_KEY` | Rerank API 密钥 |

## Windows 开发注意事项

- psycopg3 异步模式需要 `WindowsSelectorEventLoopPolicy`（已在 `api/server.py` 中配置）
- 确保 PostgreSQL 已安装 pgvector 扩展

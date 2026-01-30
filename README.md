# 农药智能体（Pesticide Agent）

基于 LangGraph 的农药配方生成与优化系统，支持知识问答、配方设计和知识库检索（RAG）。

## 功能特性

- **配方生成**：根据用户需求自动生成农药配方
- **配方优化**：对现有配方进行分析和优化
- **知识问答**：基于知识库的智能问答
- **RAG 检索**：支持向量检索和重排序

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / LangGraph / LangChain |
| 前端 | React 19 / Vite / TypeScript / TailwindCSS |
| 数据库 | PostgreSQL 16 + pgvector |
| LLM | OpenAI 兼容接口（支持 OpenRouter/VLLM） |

## 目录结构

```
pesticide_agent/
├── backend/                 # Python 后端
│   ├── agent/              # LangGraph Agent 模块
│   ├── api/                # FastAPI 接口层
│   ├── infra/              # 基础设施（配置、数据库、日志）
│   ├── rag/                # RAG 分块与检索
│   ├── tools/              # Agent 工具（搜索、抓取等）
│   ├── knowledge_base/     # 知识库文件（Markdown）
│   └── scripts/            # 部署与数据导入脚本
├── frontend/               # React 前端
│   └── src/
│       ├── components/     # UI 组件
│       ├── hooks/          # React Hooks
│       └── api/            # API 调用
├── dify-rag-reference/     # Dify RAG 参考实现
└── CLAUDE.md               # AI 协作开发说明
```

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/pesticide_agent.git
cd pesticide_agent

# 复制环境变量配置
cp backend/.env.example backend/.env
# 编辑 .env 文件，填入 API 密钥
```

### 2. 启动数据库

```bash
cd backend
docker-compose up -d
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 开始使用。

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 Swagger 文档。

| 路由前缀 | 功能 |
|---------|------|
| `/api/chat` | 对话接口（SSE 流式响应） |
| `/api/session` | 会话管理 |
| `/api/knowledge` | 知识库管理 |
| `/api/recipe-kb` | 配方知识库管理 |
| `/api/upload` | 文件上传 |

## 环境变量

主要配置项（详见 `backend/.env.example`）：

| 变量 | 说明 |
|------|------|
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 |
| `LLM_MODEL_NAME` | LLM 模型名称 |
| `POSTGRES_*` | 数据库连接配置 |
| `EMBEDDING_*` | Embedding 模型配置 |
| `RERANK_*` | Rerank 模型配置 |

## 开发说明

- 后端详细说明：[backend/README.md](backend/README.md)
- AI 协作约定：[CLAUDE.md](CLAUDE.md)

## 许可证

MIT License

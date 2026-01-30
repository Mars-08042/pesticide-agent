"""
FastAPI 应用入口
农药智能体后端 API 服务

修改：
- P2-10: 使用统一日志配置模块
- P2-12: CORS 根据环境变量配置不同策略
"""

import os
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from functools import partialmethod

# Windows 事件循环兼容性修复
# psycopg (v3) 的异步模式不支持 ProactorEventLoop，需要使用 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 在导入任何可能使用 tqdm 的模块之前禁用 tqdm
os.environ["TQDM_DISABLE"] = "1"

# Monkey-patch tqdm 以完全禁用进度条
# FlagEmbedding 等库内部使用的 tqdm 不会检查 TQDM_DISABLE 环境变量
import tqdm
tqdm.tqdm.__init__ = partialmethod(tqdm.tqdm.__init__, disable=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

# 使用统一配置和日志模块
from infra.config import get_config
from infra.logging_config import setup_logging, get_logger

# 在导入其他模块前初始化日志
setup_logging()
logger = get_logger("api")

from api.routers import chat_router, session_router, events_router
from api.dependencies import init_resources, cleanup_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化资源
    await init_resources()
    yield
    # 关闭时清理资源
    await cleanup_resources()


# 创建 FastAPI 应用
app = FastAPI(
    title="农药智能体 API",
    description="农药知识问答与配方推荐智能体后端服务",
    version="1.0.0",
    lifespan=lifespan,
)


# 添加请求日志中间件（只记录关键请求）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 跳过频繁的轮询请求和静态资源
    skip_paths = ["/api/chat/history", "/health", "/api/session/list"]
    should_log = not any(request.url.path.startswith(p) for p in skip_paths)

    if should_log:
        logger.info(f"请求: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        # 只记录非 2xx 状态码的响应
        if should_log and response.status_code >= 400:
            logger.warning(f"响应: {request.method} {request.url.path} - {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"请求失败: {request.method} {request.url.path} - {str(e)}")
        raise e


# 配置 CORS (P2-12: 根据环境配置不同策略)
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=config.server.cors_allow_credentials,
    allow_methods=config.server.cors_allow_methods,
    allow_headers=config.server.cors_allow_headers,
)

# 记录 CORS 配置信息
if config.is_production():
    logger.info(f"生产环境 CORS 配置: {config.server.cors_origins}")
else:
    logger.info("开发环境 CORS 配置: 允许所有来源")


# 注册路由
app.include_router(session_router, prefix="/api/session", tags=["会话管理"])
app.include_router(chat_router, prefix="/api/chat", tags=["对话"])
app.include_router(events_router, prefix="/api/events", tags=["事件推送"])


@app.get("/", tags=["健康检查"])
async def root():
    """API 根路径 - 健康检查"""
    return {
        "status": "ok",
        "service": "农药智能体 API",
        "version": "1.0.0",
        "environment": config.environment.value,
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
    )

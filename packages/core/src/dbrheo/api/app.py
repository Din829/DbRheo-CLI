"""
FastAPI应用创建和配置
提供完整的Web API服务
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from ..config.base import DatabaseConfig
from ..core.client import DatabaseClient
from .dependencies import set_app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 确保环境变量已加载
    if not os.getenv("GOOGLE_API_KEY"):
        # 尝试加载.env文件
        env_paths = [
            Path.cwd() / '.env',
            Path(__file__).parent.parent.parent.parent.parent / '.env',
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                logging.info(f"Loading environment from: {env_path}")
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if key not in os.environ:
                                os.environ[key] = value
                break
    
    # 启动时初始化
    config = DatabaseConfig()
    client = DatabaseClient(config)
    
    set_app_state("config", config)
    set_app_state("client", client)
    
    logging.info("DbRheo API server started")
    logging.info(f"GOOGLE_API_KEY configured: {'Yes' if os.getenv('GOOGLE_API_KEY') else 'No'}")
    
    yield
    
    # 关闭时清理
    # TODO: 实现客户端清理逻辑
    pass
        
    logging.info("DbRheo API server stopped")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    
    app = FastAPI(
        title="DbRheo API",
        description="智能数据库Agent API - 基于Gemini CLI架构",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Web界面地址
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 延迟导入路由以避免循环导入
    from .routes.chat import chat_router
    from .routes.database import database_router
    from .routes.websocket import websocket_router
    
    # 注册路由
    app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
    app.include_router(database_router, prefix="/api/database", tags=["database"])
    app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "DbRheo API"}
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "message": "DbRheo - 智能数据库Agent API",
            "version": "1.0.0",
            "docs": "/docs"
        }
    
    return app


# 创建应用实例供导入使用
app = create_app()

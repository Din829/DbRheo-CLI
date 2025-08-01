"""
API路由模块 - 组织不同功能的路由
"""

from .chat import chat_router
from .database import database_router
from .websocket import websocket_router

__all__ = [
    "chat_router",
    "database_router", 
    "websocket_router"
]

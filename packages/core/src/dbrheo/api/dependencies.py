"""
API依赖项 - 提供依赖注入的函数
避免循环导入问题
"""

from typing import Dict, Any
from fastapi import HTTPException

from ..config.base import DatabaseConfig
from ..core.client import DatabaseClient

# 全局应用状态存储
app_state: Dict[str, Any] = {}


def get_client() -> DatabaseClient:
    """获取数据库客户端实例"""
    if "client" not in app_state:
        raise HTTPException(status_code=500, detail="Database client not initialized")
    return app_state["client"]


def get_config() -> DatabaseConfig:
    """获取配置实例"""
    if "config" not in app_state:
        raise HTTPException(status_code=500, detail="Configuration not initialized")
    return app_state["config"]


def set_app_state(key: str, value: Any):
    """设置应用状态"""
    app_state[key] = value


def get_app_state(key: str) -> Any:
    """获取应用状态"""
    return app_state.get(key)
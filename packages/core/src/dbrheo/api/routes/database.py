"""
数据库API路由 - 提供数据库操作和管理功能
包括连接管理、结构查询、SQL执行等
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from ...adapters.connection_manager import DatabaseConnectionManager
from ..dependencies import get_config

database_router = APIRouter()


class DatabaseConnection(BaseModel):
    """数据库连接模型"""
    name: str
    connection_string: str
    dialect: str
    description: Optional[str] = None


class SQLRequest(BaseModel):
    """SQL执行请求"""
    sql: str
    database: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class SchemaRequest(BaseModel):
    """结构查询请求"""
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: Optional[str] = None


@database_router.get("/connections")
async def list_connections(config = Depends(get_config)):
    """获取所有数据库连接"""
    try:
        # TODO: 实现从配置中获取连接列表
        connections = [
            {
                "name": "default",
                "dialect": "sqlite",
                "description": "默认SQLite数据库",
                "status": "connected"
            }
        ]
        
        return {
            "connections": connections,
            "total": len(connections)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@database_router.post("/connections/test")
async def test_connection(
    connection: DatabaseConnection,
    config = Depends(get_config)
):
    """测试数据库连接"""
    try:
        # 创建连接管理器
        manager = DatabaseConnectionManager(config)
        
        # TODO: 实现连接测试逻辑
        # 这里需要根据连接信息创建适配器并测试连接
        
        return {
            "success": True,
            "message": "Connection successful",
            "connection_info": {
                "name": connection.name,
                "dialect": connection.dialect
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}"
        }


@database_router.post("/execute")
async def execute_sql(
    request: SQLRequest,
    config = Depends(get_config)
):
    """执行SQL语句"""
    try:
        # 创建连接管理器
        manager = DatabaseConnectionManager(config)
        adapter = await manager.get_connection(request.database)
        
        # 解析SQL类型
        sql_info = await adapter.parse_sql(request.sql)
        
        # 根据SQL类型选择执行方法
        if sql_info["sql_type"] == "SELECT":
            result = await adapter.execute_query(
                request.sql, 
                request.params
            )
        else:
            result = await adapter.execute_command(
                request.sql, 
                request.params
            )
            
        return {
            "success": result["success"],
            "data": result.get("data", []),
            "columns": result.get("columns", []),
            "row_count": result.get("row_count", 0),
            "affected_rows": result.get("affected_rows", 0),
            "sql_info": sql_info,
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@database_router.get("/schema")
async def get_schema_info(
    database: Optional[str] = None,
    schema_name: Optional[str] = None,
    config = Depends(get_config)
):
    """获取数据库结构信息"""
    try:
        manager = DatabaseConnectionManager(config)
        adapter = await manager.get_connection(database)
        
        result = await adapter.get_schema_info(schema_name)
        
        if result["success"]:
            return {
                "success": True,
                "schema": result["schema"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@database_router.get("/tables/{table_name}")
async def get_table_info(
    table_name: str,
    database: Optional[str] = None,
    config = Depends(get_config)
):
    """获取表结构信息"""
    try:
        manager = DatabaseConnectionManager(config)
        adapter = await manager.get_connection(database)
        
        table_info = await adapter.get_table_info(table_name)
        
        if "error" in table_info:
            raise HTTPException(status_code=404, detail=table_info["error"])
            
        return {
            "success": True,
            "table": table_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@database_router.get("/tables")
async def list_tables(
    database: Optional[str] = None,
    config = Depends(get_config)
):
    """获取所有表列表"""
    try:
        manager = DatabaseConnectionManager(config)
        adapter = await manager.get_connection(database)
        
        schema_result = await adapter.get_schema_info()
        
        if schema_result["success"]:
            schema = schema_result["schema"]
            tables = list(schema.get("tables", {}).keys())
            views = list(schema.get("views", {}).keys())
            
            return {
                "success": True,
                "tables": tables,
                "views": views,
                "total_tables": len(tables),
                "total_views": len(views)
            }
        else:
            raise HTTPException(status_code=500, detail=schema_result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@database_router.post("/analyze")
async def analyze_sql(
    request: SQLRequest,
    config = Depends(get_config)
):
    """分析SQL语句"""
    try:
        manager = DatabaseConnectionManager(config)
        adapter = await manager.get_connection(request.database)
        
        # 解析SQL
        sql_info = await adapter.parse_sql(request.sql)
        
        return {
            "success": True,
            "analysis": sql_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

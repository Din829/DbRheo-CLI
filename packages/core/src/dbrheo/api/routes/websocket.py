"""
WebSocket路由 - 提供实时通信功能
支持流式对话、工具执行状态更新等
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
import asyncio
from typing import Dict, Set

from ...types.core_types import SimpleAbortSignal
from ..dependencies import get_client

websocket_router = APIRouter()

# 活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}
session_connections: Dict[str, Set[str]] = {}


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, connection_id: str):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
    def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            
    async def send_message(self, connection_id: str, message: dict):
        """发送消息到指定连接"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except:
                # 连接已断开，清理
                self.disconnect(connection_id)
                
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection_id in list(self.active_connections.keys()):
            await self.send_message(connection_id, message)


manager = ConnectionManager()


@websocket_router.websocket("/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    client = Depends(get_client)
):
    """
    WebSocket聊天接口
    提供实时的对话交互和工具执行状态更新
    """
    connection_id = f"{session_id}_{id(websocket)}"
    
    await manager.connect(websocket, connection_id)
    
    try:
        # 发送连接确认
        await manager.send_message(connection_id, {
            "type": "connection",
            "status": "connected",
            "session_id": session_id,
            "message": "WebSocket连接已建立"
        })
        
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type", "chat")
            
            if message_type == "chat":
                # 处理聊天消息
                await handle_chat_message(
                    connection_id, 
                    session_id, 
                    message_data, 
                    client
                )
            elif message_type == "ping":
                # 心跳检测
                await manager.send_message(connection_id, {
                    "type": "pong",
                    "timestamp": message_data.get("timestamp")
                })
            elif message_type == "abort":
                # 中止当前操作
                await manager.send_message(connection_id, {
                    "type": "aborted",
                    "message": "操作已中止"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        await manager.send_message(connection_id, {
            "type": "error",
            "error": str(e)
        })
        manager.disconnect(connection_id)


async def handle_chat_message(
    connection_id: str,
    session_id: str,
    message_data: dict,
    client
):
    """处理聊天消息"""
    try:
        message = message_data.get("message", "")
        
        # 发送开始处理的通知
        await manager.send_message(connection_id, {
            "type": "processing",
            "message": "正在处理您的请求..."
        })
        
        # 创建中止信号
        signal = SimpleAbortSignal()
        
        # 发送消息并获取流式响应
        response_stream = client.send_message_stream(
            request=message,
            signal=signal,
            prompt_id=session_id,
            turns=100
        )
        
        # 流式发送响应
        async for chunk in response_stream:
            await manager.send_message(connection_id, {
                "type": "stream",
                "chunk": chunk
            })
            
        # 发送完成通知
        await manager.send_message(connection_id, {
            "type": "complete",
            "message": "响应完成"
        })
        
    except Exception as e:
        await manager.send_message(connection_id, {
            "type": "error",
            "error": str(e)
        })


@websocket_router.websocket("/tools/{session_id}")
async def websocket_tools(
    websocket: WebSocket,
    session_id: str
):
    """
    工具执行状态WebSocket
    实时更新工具执行状态和结果
    """
    connection_id = f"tools_{session_id}_{id(websocket)}"
    
    await manager.connect(websocket, connection_id)
    
    try:
        await manager.send_message(connection_id, {
            "type": "connection",
            "status": "connected",
            "message": "工具状态监听已建立"
        })
        
        # 保持连接活跃
        while True:
            data = await websocket.receive_text()
            # 这里可以处理工具相关的命令
            
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        await manager.send_message(connection_id, {
            "type": "error",
            "error": str(e)
        })
        manager.disconnect(connection_id)

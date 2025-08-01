"""
聊天API路由 - 处理与数据库Agent的对话交互
提供流式对话、历史管理等功能
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio

from ...types.core_types import SimpleAbortSignal
from ..dependencies import get_client, get_config

chat_router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息模型"""
    content: str
    role: str = "user"


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    session_id: str
    turn_count: int
    next_speaker: Optional[str] = None


@chat_router.post("/send")
async def send_message(
    request: ChatRequest,
    client = Depends(get_client)
):
    """
    发送消息给数据库Agent
    支持流式响应和工具调用
    """
    try:
        # 创建中止信号
        signal = SimpleAbortSignal()
        
        # 生成会话ID
        session_id = request.session_id or f"session_{int(asyncio.get_event_loop().time())}"
        
        # 发送消息并获取流式响应
        response_stream = client.send_message_stream(
            request=request.message,
            signal=signal,
            prompt_id=session_id,
            turns=100
        )
        
        # 收集响应
        response_parts = []
        chunk_count = 0
        async for chunk in response_stream:
            chunk_count += 1
            print(f"[DEBUG] Chunk #{chunk_count}: {chunk}")  # 调试信息
            
            if chunk.get("type") == "Content":
                response_parts.append(chunk.get("value", ""))
            elif chunk.get("type") == "ToolCallRequest":
                # 工具调用请求
                tool_value = chunk.get('value')
                if hasattr(tool_value, 'name'):
                    tool_name = tool_value.name
                elif isinstance(tool_value, dict):
                    tool_name = tool_value.get('name', 'unknown')
                else:
                    tool_name = 'unknown'
                response_parts.append(f"[工具调用: {tool_name}]")
                
        response_text = "".join(response_parts)
        print(f"[DEBUG] Total chunks: {chunk_count}, Response text: {response_text}")
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            turn_count=client.session_turn_count,
            next_speaker="user"  # TODO: 实现实际的next_speaker判断
        )
        
    except Exception as e:
        print(f"[ERROR] send_message exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.get("/stream/{session_id}")
async def stream_chat(
    session_id: str,
    message: str,
    client = Depends(get_client)
):
    """
    流式聊天接口
    返回Server-Sent Events格式的流式响应
    """
    async def generate_stream():
        try:
            signal = SimpleAbortSignal()
            
            response_stream = client.send_message_stream(
                request=message,
                signal=signal,
                prompt_id=session_id,
                turns=100
            )
            
            async for chunk in response_stream:
                # 转换为SSE格式
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {data}\n\n"
                
            # 发送结束标记
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@chat_router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    curated: bool = True,
    client = Depends(get_client)
):
    """获取聊天历史"""
    try:
        # TODO: 实现从客户端获取历史的逻辑
        history = client.chat.get_history(curated=curated)
        
        return {
            "session_id": session_id,
            "history": history,
            "total_messages": len(history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    client = Depends(get_client)
):
    """清除聊天历史"""
    try:
        # TODO: 实现清除历史的逻辑
        client.chat.set_history([])
        
        return {
            "message": "Chat history cleared",
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/compress/{session_id}")
async def compress_chat_history(
    session_id: str,
    force: bool = False,
    client = Depends(get_client)
):
    """压缩聊天历史"""
    try:
        # TODO: 实现历史压缩逻辑
        result = await client.try_compress_chat(session_id, force=force)
        
        if result:
            return {
                "message": "Chat history compressed",
                "session_id": session_id,
                "compression_stats": result
            }
        else:
            return {
                "message": "No compression needed",
                "session_id": session_id
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

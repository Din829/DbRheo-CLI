"""
OpenAI API 服务 - 处理与 OpenAI API 的通信
支持 GPT-3.5、GPT-4、o1 等模型，保持与 GeminiService 相同的接口
"""

import os
import json
from typing import List, Dict, Any, Optional, Iterator
from ..types.core_types import Content, AbortSignal
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info, log_error
from ..utils.retry_with_backoff import retry_with_backoff_sync, RetryOptions


class OpenAIService:
    """
    OpenAI API 服务
    - 与 OpenAI API 的通信
    - 消息格式转换（Gemini ↔ OpenAI）
    - 函数调用处理
    - 流式响应处理
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._setup_api()
        
    def _setup_api(self):
        """设置 OpenAI API"""
        # 获取 API 密钥 - 支持多种配置方式
        api_key = (
            self.config.get("openai_api_key") or
            os.getenv("OPENAI_API_KEY")
        )
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        # 支持自定义 API 基础 URL（兼容 API）
        api_base = (
            self.config.get("openai_api_base") or
            os.getenv("OPENAI_API_BASE") or
            "https://api.openai.com/v1"
        )
        
        # 延迟导入，避免未安装时报错
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is not installed. "
                "Please install it with: pip install openai>=1.0"
            )
            
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        # 配置模型 - 支持多种 OpenAI 模型
        model_name = self.config.get_model()
        # 映射简短名称到完整模型名（只保留核心模型）
        model_mappings = {
            # 默认别名
            "gpt": "gpt-4.1",  # 默认使用 GPT-4.1
            "openai": "gpt-4.1",
            
            # GPT-4.1 系列 (2025年4月发布)
            "gpt-4.1": "gpt-4.1",
            "gpt4.1": "gpt-4.1",
            
            # GPT-4.1 Mini
            "gpt-mini": "gpt-4.1-mini",
            "gpt-4.1-mini": "gpt-4.1-mini",
            "mini": "gpt-4.1-mini"
        }
        
        # 如果是简短名称，转换为完整名称
        for short_name, full_name in model_mappings.items():
            if model_name.lower().startswith(short_name):
                self.model_name = full_name
                break
        else:
            # 使用原始名称
            self.model_name = model_name
            
        log_info("OpenAI", f"Using model: {self.model_name}")
        
        # 默认生成配置
        self.default_generation_config = {
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.8,
        }
        
    def send_message_stream(
        self,
        contents: List[Content],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        signal: Optional[AbortSignal] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        发送消息并返回流式响应（同步生成器）
        保持与 GeminiService 相同的接口
        """
        try:
            # 转换消息格式
            messages = self._gemini_to_openai_messages(contents, system_instruction)
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                **self.default_generation_config
            }
            
            # 处理函数调用
            if tools:
                openai_tools = self._convert_tools_to_openai_format(tools)
                if openai_tools:
                    request_params["tools"] = openai_tools
                    request_params["tool_choice"] = "auto"
            
            # 使用重试机制
            def api_call():
                return self.client.chat.completions.create(**request_params)
                
            retry_options = RetryOptions(
                max_attempts=3,
                initial_delay_ms=2000,
                max_delay_ms=10000
            )
            
            stream = retry_with_backoff_sync(api_call, retry_options)
            
            # 处理流式响应
            chunk_count = 0
            current_function_call = None
            
            for chunk in stream:
                chunk_count += 1
                
                if signal and signal.aborted:
                    break
                    
                # 先跟踪函数调用状态
                if chunk.choices and chunk.choices[0].delta.tool_calls:
                    for tool_call in chunk.choices[0].delta.tool_calls:
                        if tool_call.function:
                            if not current_function_call:
                                current_function_call = {
                                    "id": tool_call.id or f"call_{chunk_count}",
                                    "name": tool_call.function.name or "",
                                    "arguments": ""
                                }
                            if tool_call.function.arguments:
                                current_function_call["arguments"] += tool_call.function.arguments
                
                # 然后处理 chunk
                processed = self._process_openai_chunk(chunk, current_function_call)
                
                if processed:
                    DebugLogger.log_gemini_chunk(chunk_count, chunk, processed)
                    yield processed
                    
                    # 如果已经生成了函数调用，重置状态
                    if processed.get("function_calls"):
                        current_function_call = None
                    
        except Exception as e:
            log_error("OpenAI", f"API error: {type(e).__name__}: {str(e)}")
            
            if DebugLogger.should_log("DEBUG"):
                error_message = f"OpenAI API error: {type(e).__name__}: {str(e)}"
            else:
                error_message = "OpenAI API is temporarily unavailable. Please try again."
                
            yield self._create_error_chunk(error_message)
            
    async def generate_json(
        self,
        contents: List[Content],
        schema: Dict[str, Any],
        signal: Optional[AbortSignal] = None,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成 JSON 响应 - 使用 OpenAI 的 JSON 模式
        """
        try:
            # 转换消息格式
            messages = self._gemini_to_openai_messages(contents, system_instruction)
            
            # 添加 JSON 指令
            json_instruction = f"Respond with valid JSON matching this schema: {json.dumps(schema, indent=2)}"
            messages.append({"role": "user", "content": json_instruction})
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.1,  # 低温度以提高一致性
                "max_tokens": 4096,
                "response_format": {"type": "json_object"}  # JSON 模式
            }
            
            # 同步调用（注意：这是 async 方法但使用同步 API）
            import asyncio
            loop = asyncio.get_event_loop()
            
            def sync_call():
                response = self.client.chat.completions.create(**request_params)
                return response.choices[0].message.content
                
            response_text = await loop.run_in_executor(None, sync_call)
            
            # 解析 JSON
            return json.loads(response_text)
                
        except Exception as e:
            log_error("OpenAI", f"JSON generation error: {str(e)}")
            # 返回默认响应
            return {
                "next_speaker": "user",
                "reasoning": f"Error in JSON generation: {str(e)}"
            }
            
    def _gemini_to_openai_messages(
        self, 
        contents: List[Content], 
        system_instruction: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        将 Gemini 格式的消息转换为 OpenAI 格式
        Gemini: {"role": "user/model", "parts": [{"text": "..."}]}
        OpenAI: {"role": "user/assistant/system", "content": "..."}
        """
        messages = []
        
        # 添加系统消息
        if system_instruction:
            messages.append({
                "role": "system",
                "content": system_instruction
            })
        
        for content in contents:
            # 转换角色
            role = "assistant" if content.get("role") == "model" else content.get("role", "user")
            
            # 提取内容
            text_parts = []
            tool_calls = []
            
            parts = content.get("parts", [])
            for part in parts:
                if isinstance(part, dict):
                    if "text" in part:
                        text_parts.append(part["text"])
                    elif "function_call" in part:
                        # 转换函数调用
                        fc = part["function_call"]
                        tool_calls.append({
                            "id": fc.get("id", f"call_{len(tool_calls)}"),
                            "type": "function",
                            "function": {
                                "name": fc.get("name", ""),
                                "arguments": json.dumps(fc.get("args", {}))
                            }
                        })
                    elif "function_response" in part or "functionResponse" in part:
                        # 函数响应 - OpenAI 使用 tool role
                        fr = part.get("function_response") or part.get("functionResponse")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": fr.get("id", ""),
                            "content": json.dumps(fr.get("response", {}))
                        })
                        continue
            
            # 构建消息
            if text_parts or tool_calls:
                message = {"role": role}
                
                if text_parts:
                    message["content"] = "\n".join(text_parts)
                else:
                    message["content"] = ""  # OpenAI 要求 content 字段
                    
                if tool_calls and role == "assistant":
                    message["tool_calls"] = tool_calls
                    
                messages.append(message)
                
        return messages
        
    def _convert_tools_to_openai_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 Gemini 工具格式转换为 OpenAI 格式"""
        openai_tools = []
        
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            }
            openai_tools.append(openai_tool)
            
        return openai_tools
        
    def _process_openai_chunk(
        self, 
        chunk, 
        current_function_call: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """处理 OpenAI 流式 chunk，转换为 Gemini 格式"""
        result = {}
        
        if not chunk.choices:
            return None
            
        choice = chunk.choices[0]
        delta = choice.delta
        
        # 处理文本内容
        if delta.content:
            result["text"] = delta.content
            
        # 处理函数调用完成
        if choice.finish_reason == "tool_calls" and current_function_call:
            # 解析参数
            try:
                args = json.loads(current_function_call["arguments"])
            except:
                args = {}
                
            result["function_calls"] = [{
                "id": current_function_call["id"],
                "name": current_function_call["name"],
                "args": args
            }]
            
        return result if result else None
        
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应块"""
        return {
            "type": "error",
            "error": error_message,
            "text": f"Error: {error_message}"
        }
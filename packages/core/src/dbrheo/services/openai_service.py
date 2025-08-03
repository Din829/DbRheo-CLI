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
                "stream_options": {"include_usage": True},  # 启用流式响应中的 token 统计
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
                
                # 调试：检查每个 chunk 的结构
                if DebugLogger.should_log("DEBUG"):
                    log_info("OpenAI", f"Chunk #{chunk_count}: has_usage={hasattr(chunk, 'usage')}, has_choices={bool(chunk.choices)}")
                
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
        
        # 先收集所有消息，包括tool响应
        tool_responses_pending = []  # 待处理的tool响应
        
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
                        # 收集函数响应，稍后处理
                        fr = part.get("function_response") or part.get("functionResponse")
                        tool_responses_pending.append({
                            "role": "tool",
                            "tool_call_id": fr.get("id", ""),
                            "content": json.dumps(fr.get("response", {}))
                        })
            
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
        
        # 处理剩余的tool响应（如果有）
        if tool_responses_pending:
            messages.extend(tool_responses_pending)
        
        # 修复tool_calls和tool响应的配对问题
        # 移除打断配对的用户消息
        fixed_messages = []
        if system_instruction:
            # 保留系统消息
            fixed_messages.append(messages[0])
            start_idx = 1
        else:
            start_idx = 0
            
        # 调试：打印修复前的消息
        if DebugLogger.should_log("DEBUG"):
            log_info("OpenAI", f"修复前的消息数量: {len(messages)}")
            for idx, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                if "tool_calls" in msg:
                    log_info("OpenAI", f"  [{idx}] {role} - has tool_calls: {[tc['id'] for tc in msg['tool_calls']]}")
                elif role == "tool":
                    log_info("OpenAI", f"  [{idx}] {role} - tool_call_id: {msg.get('tool_call_id', 'none')}")
                else:
                    content_preview = str(msg.get("content", ""))[:50]
                    log_info("OpenAI", f"  [{idx}] {role} - {content_preview}")
            
        # 先收集所有的tool响应，建立ID到响应的映射
        tool_responses_map = {}
        for msg in messages[start_idx:]:
            if msg["role"] == "tool" and "tool_call_id" in msg:
                tool_responses_map[msg["tool_call_id"]] = msg
        
        # 记录已使用的tool响应
        used_tool_ids = set()
        
        i = start_idx
        while i < len(messages):
            msg = messages[i]
            # 检查是否是包含tool_calls的assistant消息
            if msg["role"] == "assistant" and "tool_calls" in msg:
                # 添加当前消息
                fixed_messages.append(msg)
                
                # 立即添加对应的tool响应（如果存在）
                for tool_call in msg["tool_calls"]:
                    tool_id = tool_call["id"]
                    if tool_id in tool_responses_map and tool_id not in used_tool_ids:
                        fixed_messages.append(tool_responses_map[tool_id])
                        used_tool_ids.add(tool_id)
                
                i += 1
            elif msg["role"] == "tool":
                # 跳过已经添加的tool响应
                if msg.get("tool_call_id") in used_tool_ids:
                    i += 1
                    continue
                else:
                    # 孤立的tool响应，保留它
                    fixed_messages.append(msg)
                    i += 1
            else:
                # 其他消息：跳过打断tool配对的"Please continue"
                if (msg["role"] == "user" and 
                    msg.get("content", "").strip() in ["Please continue.", "Continue the conversation."] and
                    i > start_idx and 
                    len(fixed_messages) > 0):
                    # 检查前一条消息是否是未配对的assistant with tool_calls
                    prev_msg = fixed_messages[-1]
                    if prev_msg["role"] == "assistant" and "tool_calls" in prev_msg:
                        # 检查是否所有tool_calls都有响应
                        all_paired = all(
                            tc["id"] in used_tool_ids 
                            for tc in prev_msg["tool_calls"]
                        )
                        if not all_paired:
                            # 跳过这个"Please continue"，因为它打断了配对
                            i += 1
                            continue
                
                # 添加其他正常消息
                fixed_messages.append(msg)
                i += 1
                
        # 检查是否有未配对的tool_calls，为它们生成占位响应
        # 这解决了工具等待确认时的配对问题
        final_messages = []
        for i, msg in enumerate(fixed_messages):
            final_messages.append(msg)
            
            # 如果是包含tool_calls的assistant消息
            if msg["role"] == "assistant" and "tool_calls" in msg:
                # 检查每个tool_call是否有对应的响应
                for tool_call in msg["tool_calls"]:
                    tool_id = tool_call["id"]
                    # 检查下一条消息是否是对应的tool响应
                    has_response = False
                    if i + 1 < len(fixed_messages):
                        next_msg = fixed_messages[i + 1]
                        if next_msg["role"] == "tool" and next_msg.get("tool_call_id") == tool_id:
                            has_response = True
                    
                    # 如果没有响应，生成占位响应
                    if not has_response:
                        placeholder_response = {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": "Tool execution pending or awaiting confirmation"
                        }
                        final_messages.append(placeholder_response)
                        # 记录这个占位响应
                        if DebugLogger.should_log("DEBUG"):
                            log_info("OpenAI", f"Generated placeholder response for tool_call_id: {tool_id}")
        
        # 调试：打印修复后的消息
        if DebugLogger.should_log("DEBUG"):
            log_info("OpenAI", f"修复后的消息数量: {len(final_messages)}")
            for idx, msg in enumerate(final_messages):
                role = msg.get("role", "unknown")
                if "tool_calls" in msg:
                    log_info("OpenAI", f"  [{idx}] {role} - has tool_calls: {[tc['id'] for tc in msg['tool_calls']]}")
                elif role == "tool":
                    log_info("OpenAI", f"  [{idx}] {role} - tool_call_id: {msg.get('tool_call_id', 'none')}")
                else:
                    content_preview = str(msg.get("content", ""))[:50]
                    log_info("OpenAI", f"  [{idx}] {role} - {content_preview}")
                
        return final_messages
        
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
        
        # 首先检查是否有 usage 信息（可能在最后一个没有 choices 的 chunk 中）
        if hasattr(chunk, 'usage') and chunk.usage:
            usage = chunk.usage
            token_info = {
                "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(usage, 'completion_tokens', 0),
                "total_tokens": getattr(usage, 'total_tokens', 0)
            }
            
            # OpenAI的cached_tokens在prompt_tokens_details中
            cached_tokens = 0
            if hasattr(usage, 'prompt_tokens_details'):
                details = usage.prompt_tokens_details
                if hasattr(details, 'cached_tokens'):
                    cached_tokens = getattr(details, 'cached_tokens', 0)
                # 调试：查看details的所有属性
                from ..utils.debug_logger import log_info
                if DebugLogger.should_log("DEBUG"):
                    attrs = [attr for attr in dir(details) if not attr.startswith('_')] if details else []
                    log_info("OpenAI", f"prompt_tokens_details attributes: {attrs}")
            
            token_info["cached_tokens"] = cached_tokens
            result["token_usage"] = token_info
            
            # 调试日志
            log_info("OpenAI", f"Token usage detected: {token_info}")
            if cached_tokens > 0:
                log_info("OpenAI", f"Prompt caching active - Cached tokens: {cached_tokens}")
            # 如果只有 usage 信息，直接返回
            if not chunk.choices:
                return result
        
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
                from ..utils.debug_logger import log_info
                log_info("OpenAI", f"✅ Function call parsed successfully:")
                log_info("OpenAI", f"  Function: {current_function_call.get('name', 'unknown')}")
                log_info("OpenAI", f"  Raw arguments: {repr(current_function_call.get('arguments', ''))}")
                log_info("OpenAI", f"  Parsed args: {repr(args)}")
            except Exception as e:
                from ..utils.debug_logger import log_info
                log_info("OpenAI", f"🚨 Failed to parse function arguments:")
                log_info("OpenAI", f"  Function: {current_function_call.get('name', 'unknown')}")
                log_info("OpenAI", f"  Raw arguments: {repr(current_function_call.get('arguments', ''))}")
                log_info("OpenAI", f"  Parse error: {e}")
                
                # 尝试从第一个有效的JSON对象中提取参数
                args = self._extract_first_valid_json(current_function_call["arguments"])
                if args:
                    log_info("OpenAI", f"✅ Recovered from malformed JSON: {repr(args)}")
                else:
                    log_info("OpenAI", f"❌ Could not recover from malformed JSON")
                    args = {}
                
            result["function_calls"] = [{
                "id": current_function_call["id"],
                "name": current_function_call["name"],
                "args": args
            }]
            
        return result if result else None
    
    def _extract_first_valid_json(self, text: str) -> Dict[str, Any]:
        """
        智能处理多个JSON对象的情况，保持Agent灵活性
        """
        if not text or not text.strip():
            return {}
            
        # 提取所有有效的JSON对象
        json_objects = self._extract_all_json_objects(text)
        
        if not json_objects:
            return {}
            
        if len(json_objects) == 1:
            return json_objects[0]
            
        # 多个JSON对象的情况 - 智能处理
        first_obj = json_objects[0]
        
        # 收集其他对象的信息，让Agent了解情况
        other_info = []
        for obj in json_objects[1:]:
            if 'table_name' in obj:
                other_info.append(obj['table_name'])
            else:
                other_info.append('unnamed_table')
        
        # 在第一个对象中添加Agent反馈信息
        first_obj['_agent_feedback'] = f"Multiple table requests detected. Currently processing '{first_obj.get('table_name', 'unknown')}'. Other tables found: {', '.join(other_info)}. Consider separate calls for each table."
        
        return first_obj
    
    def _extract_all_json_objects(self, text: str) -> list:
        """提取所有有效的JSON对象"""
        objects = []
        brace_count = 0
        start_pos = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if start_pos == -1:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    json_str = text[start_pos:i+1]
                    try:
                        obj = json.loads(json_str)
                        objects.append(obj)
                    except:
                        pass
                    start_pos = -1
        
        return objects
        
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应块"""
        return {
            "type": "error",
            "error": error_message,
            "text": f"Error: {error_message}"
        }
"""
Claude API 服务 - 处理与 Anthropic Claude API 的通信
保持与 GeminiService 相同的接口，实现格式转换
"""

import os
import json
from typing import List, Dict, Any, Optional, Iterator
from ..types.core_types import Content, AbortSignal
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info, log_error
from ..utils.retry_with_backoff import retry_with_backoff_sync, RetryOptions

# 延迟导入，避免阻止模块加载
anthropic = None


class ClaudeService:
    """
    Claude API 服务
    - 与 Anthropic Claude API 的通信
    - 消息格式转换（Gemini ↔ Claude）
    - 工具调用适配
    - 流式响应处理
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._setup_api()
        self._current_tool_use = None  # 跟踪当前的工具调用
        
    def _setup_api(self):
        """设置 Claude API"""
        # 延迟导入 anthropic
        global anthropic
        if anthropic is None:
            try:
                import anthropic as _anthropic
                anthropic = _anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package is not installed. "
                    "Please install it with: pip install anthropic"
                )
        
        # 获取 API 密钥 - 支持多种配置方式
        api_key = (
            self.config.get("anthropic_api_key") or 
            self.config.get("claude_api_key") or
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("CLAUDE_API_KEY")
        )
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # 配置模型 - 支持多种 Claude 模型
        model_name = self.config.get_model()
        # 映射简短名称到完整模型名（只保留核心模型）
        model_mappings = {
            # 默认别名
            "claude": "claude-sonnet-4-20250514",  # 默认使用最新 Sonnet 4
            "sonnet": "claude-sonnet-4-20250514",  # 默认到 Sonnet 4
            
            # Claude 4 系列 (2025年5月发布)
            "sonnet4": "claude-sonnet-4-20250514",
            "claude-sonnet-4": "claude-sonnet-4-20250514",
            
            # Claude 3.7 系列 (混合推理模型)
            "sonnet3.7": "claude-3-7-sonnet-20250219",
            "claude-3.7": "claude-3-7-sonnet-20250219",
            "claude-3-7-sonnet": "claude-3-7-sonnet-20250219"
        }
        
        # 如果是简短名称，转换为完整名称
        for short_name, full_name in model_mappings.items():
            if model_name.lower().startswith(short_name):
                self.model_name = full_name
                break
        else:
            # 使用原始名称
            self.model_name = model_name
            
        log_info("Claude", f"Using model: {self.model_name}")
        
        # 默认生成配置
        self.default_generation_config = {
            "max_tokens": 8192,
            "temperature": 0.7,
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
            messages = self._gemini_to_claude_messages(contents)
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                **self.default_generation_config
            }
            
            # 添加系统指令
            if system_instruction:
                request_params["system"] = system_instruction
                
            # 处理工具调用
            if tools:
                # 转换 Gemini 工具格式到 Claude 格式
                claude_tools = []
                for tool in tools:
                    claude_tools.append({
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool["parameters"]
                    })
                request_params["tools"] = claude_tools
                log_info("Claude", f"Registered {len(claude_tools)} tools")
            
            # 使用重试机制
            def api_call():
                return self.client.messages.create(**request_params)
                
            retry_options = RetryOptions(
                max_attempts=3,
                initial_delay_ms=2000,
                max_delay_ms=10000
            )
            
            stream = retry_with_backoff_sync(api_call, retry_options)
            
            # 处理流式响应
            chunk_count = 0
            for event in stream:
                chunk_count += 1
                
                # 调试：检查每个事件的类型
                if DebugLogger.should_log("DEBUG"):
                    event_type = getattr(event, 'type', 'unknown')
                    has_usage = hasattr(event, 'usage') or (hasattr(event, 'message') and hasattr(event.message, 'usage'))
                    log_info("Claude", f"Event #{chunk_count}: type={event_type}, has_usage={has_usage}")
                
                if signal and signal.aborted:
                    break
                    
                processed = self._process_claude_event(event)
                if processed:
                    DebugLogger.log_gemini_chunk(chunk_count, event, processed)
                    yield processed
                    
        except Exception as e:
            log_error("Claude", f"API error: {type(e).__name__}: {str(e)}")
            
            if DebugLogger.should_log("DEBUG"):
                error_message = f"Claude API error: {type(e).__name__}: {str(e)}"
            else:
                error_message = "Claude API is temporarily unavailable. Please try again."
                
            yield self._create_error_chunk(error_message)
            
    async def generate_json(
        self,
        contents: List[Content],
        schema: Dict[str, Any],
        signal: Optional[AbortSignal] = None,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成 JSON 响应 - 用于结构化输出
        Claude 没有原生 JSON 模式，使用提示词引导
        """
        try:
            # 转换消息格式
            messages = self._gemini_to_claude_messages(contents)
            
            # 添加 JSON 指令
            json_instruction = f"\nPlease respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\nRespond ONLY with the JSON, no other text."
            
            # 将 JSON 指令添加到最后一条消息
            if messages:
                messages[-1]["content"] += json_instruction
            else:
                messages.append({"role": "user", "content": json_instruction})
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.1,  # 低温度以提高一致性
            }
            
            # 添加系统指令
            if system_instruction:
                request_params["system"] = system_instruction + "\nYou must respond with valid JSON."
            else:
                request_params["system"] = "You must respond with valid JSON."
            
            # 同步调用（注意：这是 async 方法但使用同步 API）
            import asyncio
            loop = asyncio.get_event_loop()
            
            def sync_call():
                response = self.client.messages.create(**request_params)
                return response.content[0].text
                
            response_text = await loop.run_in_executor(None, sync_call)
            
            # 解析 JSON
            # Claude 可能会在 JSON 前后添加一些文本，需要提取
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                # 尝试直接解析
                return json.loads(response_text)
                
        except Exception as e:
            log_error("Claude", f"JSON generation error: {str(e)}")
            # 返回默认响应
            return {
                "next_speaker": "user",
                "reasoning": f"Error in JSON generation: {str(e)}"
            }
            
    def _gemini_to_claude_messages(self, contents: List[Content]) -> List[Dict[str, Any]]:
        """
        将 Gemini 格式的消息转换为 Claude 格式
        Gemini: {"role": "user/model", "parts": [{"text": "..."}]}
        Claude: {"role": "user/assistant", "content": "..."}
        """
        messages = []
        
        for content in contents:
            # 转换角色
            role = "assistant" if content.get("role") == "model" else content.get("role", "user")
            
            # 收集不同类型的内容
            text_parts = []
            tool_use_parts = []
            tool_result_parts = []
            parts = content.get("parts", [])
            
            for part in parts:
                if isinstance(part, dict):
                    if "text" in part:
                        text_parts.append(part["text"])
                    elif "function_call" in part:
                        # 转换为 Claude 的 tool_use 格式
                        fc = part["function_call"]
                        tool_use_parts.append({
                            "type": "tool_use",
                            "id": fc.get("id", f"call_{fc.get('name', 'unknown')}"),
                            "name": fc.get("name", "unknown"),
                            "input": fc.get("args", {})
                        })
                    elif "function_response" in part or "functionResponse" in part:
                        # 转换为 Claude 的 tool_result 格式
                        fr = part.get("function_response") or part.get("functionResponse")
                        response_data = fr.get("response", {}) if isinstance(fr, dict) else fr
                        tool_result_parts.append({
                            "type": "tool_result",
                            "tool_use_id": fr.get("id", ""),
                            "content": json.dumps(response_data)
                        })
            
            # 构建消息内容
            if role == "assistant" and (text_parts or tool_use_parts):
                # Assistant 消息可以包含混合内容
                content_list = []
                if text_parts:
                    content_list.append({
                        "type": "text",
                        "text": "\n".join(text_parts)
                    })
                content_list.extend(tool_use_parts)
                
                messages.append({
                    "role": "assistant",
                    "content": content_list
                })
            elif role == "user" and tool_result_parts:
                # 工具结果作为 user 消息
                for tool_result in tool_result_parts:
                    messages.append({
                        "role": "user",
                        "content": [tool_result]
                    })
            elif text_parts:
                # 纯文本消息
                messages.append({
                    "role": role,
                    "content": "\n".join(text_parts)
                })
        
        # 修复tool_use和tool_result的配对问题
        # 先收集所有的tool_result，建立ID到响应的映射
        tool_results_map = {}
        for msg in messages:
            if (msg["role"] == "user" and 
                isinstance(msg.get("content"), list) and
                len(msg["content"]) == 1 and
                msg["content"][0].get("type") == "tool_result"):
                tool_use_id = msg["content"][0].get("tool_use_id")
                if tool_use_id:
                    tool_results_map[tool_use_id] = msg
        
        # 记录已使用的tool_result
        used_tool_ids = set()
        
        fixed_messages = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            # 检查是否是包含tool_use的assistant消息
            if (msg["role"] == "assistant" and 
                isinstance(msg.get("content"), list)):
                # 提取所有tool_use
                tool_uses = [item for item in msg["content"] if item.get("type") == "tool_use"]
                
                if tool_uses:
                    # 添加当前消息
                    fixed_messages.append(msg)
                    
                    # 立即添加对应的tool_result（如果存在）
                    for tool_use in tool_uses:
                        tool_id = tool_use.get("id")
                        if tool_id and tool_id in tool_results_map and tool_id not in used_tool_ids:
                            fixed_messages.append(tool_results_map[tool_id])
                            used_tool_ids.add(tool_id)
                    
                    i += 1
                else:
                    # 没有tool_use的assistant消息
                    fixed_messages.append(msg)
                    i += 1
            elif (msg["role"] == "user" and 
                  isinstance(msg.get("content"), list) and
                  len(msg["content"]) == 1 and
                  msg["content"][0].get("type") == "tool_result"):
                # 跳过已经添加的tool_result
                tool_use_id = msg["content"][0].get("tool_use_id")
                if tool_use_id in used_tool_ids:
                    i += 1
                    continue
                else:
                    # 孤立的tool_result，保留它
                    fixed_messages.append(msg)
                    i += 1
            else:
                # 其他消息：跳过打断tool配对的"Please continue"
                if (msg["role"] == "user" and 
                    isinstance(msg.get("content"), str) and
                    msg["content"] in ["Please continue.", "Continue the conversation."] and
                    len(fixed_messages) > 0):
                    # 检查前一条消息是否是未配对的assistant with tool_use
                    prev_msg = fixed_messages[-1]
                    if (prev_msg["role"] == "assistant" and 
                        isinstance(prev_msg.get("content"), list)):
                        # 检查是否有未配对的tool_use
                        tool_uses = [item for item in prev_msg["content"] if item.get("type") == "tool_use"]
                        unpaired = any(
                            tool_use.get("id") not in used_tool_ids 
                            for tool_use in tool_uses
                        )
                        if unpaired:
                            # 跳过这个"Please continue"，因为它打断了配对
                            i += 1
                            continue
                
                # 添加其他正常消息
                fixed_messages.append(msg)
                i += 1
        
        # 检查是否有未配对的tool_use，为它们生成占位响应
        # 这解决了工具等待确认时的配对问题
        final_messages = []
        for i, msg in enumerate(fixed_messages):
            final_messages.append(msg)
            
            # 如果是包含tool_use的assistant消息
            if (msg["role"] == "assistant" and 
                isinstance(msg.get("content"), list)):
                # 提取所有tool_use
                tool_uses = [item for item in msg["content"] if item.get("type") == "tool_use"]
                
                if tool_uses:
                    # 检查每个tool_use是否有对应的响应
                    for tool_use in tool_uses:
                        tool_id = tool_use.get("id")
                        if not tool_id:
                            continue
                            
                        # 检查下一条消息是否是对应的tool_result
                        has_response = False
                        if i + 1 < len(fixed_messages):
                            next_msg = fixed_messages[i + 1]
                            if (next_msg["role"] == "user" and 
                                isinstance(next_msg.get("content"), list) and
                                len(next_msg["content"]) == 1 and
                                next_msg["content"][0].get("type") == "tool_result" and
                                next_msg["content"][0].get("tool_use_id") == tool_id):
                                has_response = True
                        
                        # 如果没有响应，生成占位响应
                        if not has_response:
                            placeholder_response = {
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": "Tool execution pending or awaiting confirmation"
                                }]
                            }
                            final_messages.append(placeholder_response)
                            # 记录这个占位响应
                            if DebugLogger.should_log("DEBUG"):
                                log_info("Claude", f"Generated placeholder response for tool_use_id: {tool_id}")
        
        # Claude 要求消息必须是 user/assistant 交替
        # 确保第一条消息是 user
        if final_messages and final_messages[0]["role"] != "user":
            final_messages.insert(0, {"role": "user", "content": "Continue the conversation."})
            
        # 确保最后一条消息是 user（如果不是）
        if final_messages and final_messages[-1]["role"] != "user":
            final_messages.append({"role": "user", "content": "Please continue."})
            
        return final_messages
        
    def _process_claude_event(self, event) -> Optional[Dict[str, Any]]:
        """处理 Claude 流式事件，转换为 Gemini 格式"""
        result = {}
        
        # Claude 流式事件类型
        if hasattr(event, 'type'):
            if event.type == 'message_start':
                # 消息开始 - Claude 在这里提供 usage 信息
                if hasattr(event, 'message') and hasattr(event.message, 'usage'):
                    usage = event.message.usage
                    token_info = {
                        "prompt_tokens": getattr(usage, 'input_tokens', 0),
                        "completion_tokens": 0,  # 输出 tokens 在 message_delta 中更新
                        "total_tokens": getattr(usage, 'input_tokens', 0)
                    }
                    result["token_usage"] = token_info
                    # 调试日志
                    from ..utils.debug_logger import log_info
                    log_info("Claude", f"Token usage in message_start: {token_info}")
                    return result if result else None
                return None
            elif event.type == 'content_block_start':
                # 内容块开始 - 检查是否是工具调用
                if hasattr(event, 'content_block') and hasattr(event.content_block, 'type'):
                    if event.content_block.type == 'tool_use':
                        # 开始一个新的工具调用
                        self._current_tool_use = {
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": ""
                        }
                return None
            elif event.type == 'content_block_delta':
                # 内容增量
                if hasattr(event, 'delta'):
                    if hasattr(event.delta, 'text'):
                        # 文本内容
                        result["text"] = event.delta.text
                    elif hasattr(event.delta, 'partial_json') and self._current_tool_use:
                        # 工具调用的参数增量
                        self._current_tool_use["input"] += event.delta.partial_json
            elif event.type == 'content_block_stop':
                # 内容块结束 - 检查是否完成了工具调用
                if self._current_tool_use:
                    try:
                        # 解析完整的工具参数
                        args = json.loads(self._current_tool_use["input"])
                    except Exception as e:
                        from ..utils.debug_logger import log_info
                        log_info("Claude", f"🚨 Failed to parse tool arguments:")
                        log_info("Claude", f"  Tool: {self._current_tool_use.get('name', 'unknown')}")
                        log_info("Claude", f"  Raw input: {repr(self._current_tool_use.get('input', ''))}")
                        log_info("Claude", f"  Parse error: {e}")
                        
                        # 尝试提取第一个有效的JSON对象
                        args = self._extract_first_valid_json(self._current_tool_use["input"])
                        if args:
                            log_info("Claude", f"✅ Recovered from malformed JSON: {repr(args)}")
                        else:
                            log_info("Claude", f"❌ Could not recover from malformed JSON")
                            args = {}
                    
                    result["function_calls"] = [{
                        "id": self._current_tool_use["id"],
                        "name": self._current_tool_use["name"],
                        "args": args
                    }]
                    self._current_tool_use = None
                return result if result else None
            elif event.type == 'message_delta':
                # 消息增量 - Claude 在这里更新累积的 token 使用情况
                if hasattr(event, 'usage'):
                    usage = event.usage
                    input_tokens = getattr(usage, 'input_tokens', None)
                    output_tokens = getattr(usage, 'output_tokens', None)
                    token_info = {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": (input_tokens or 0) + (output_tokens or 0)  # Claude 需要手动计算总数
                    }
                    result["token_usage"] = token_info
                    # 调试日志
                    from ..utils.debug_logger import log_info
                    log_info("Claude", f"Token usage in message_delta: {token_info}")
                    return result if result else None
                    
                if hasattr(event, 'delta') and hasattr(event.delta, 'stop_reason'):
                    # 消息结束
                    return None
            elif event.type == 'message_stop':
                # 消息结束
                return None
                
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
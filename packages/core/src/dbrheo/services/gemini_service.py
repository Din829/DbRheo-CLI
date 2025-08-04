"""
已经过时, 已经迁移至 gemini_service_new.py
Gemini API服务 - 处理与Google Gemini API的通信
完全对齐Gemini CLI的API调用方式
"""

import os
from typing import List, Dict, Any, Optional, AsyncIterator
import google.generativeai as genai
from ..types.core_types import Content, PartListUnion, AbortSignal
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger
from ..utils.retry_with_backoff import retry_with_backoff, RetryOptions


class GeminiService:
    """
    Gemini API服务
    - 与Google Gemini API的通信
    - 流式响应处理
    - 错误处理和重试
    - 模型配置管理
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._setup_api()
        # 缓存的模型实例（避免重复创建）
        self._cached_model = None
        self._cached_model_config = None
        # Token去重机制
        self._stream_token_tracker = None
        
    def _setup_api(self):
        """设置Gemini API"""
        api_key = self.config.get("google_api_key") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
            
        genai.configure(api_key=api_key)
        
        # 配置模型
        model_name = self.config.get_model() or "gemini-2.5-flash"
        
        # 映射简短名称到完整模型名（只保留核心模型）
        model_mappings = {
            "gemini": "gemini-2.5-flash",  # 稳定版本的正式名称
            "flash": "gemini-2.5-flash",
            "gemini-flash": "gemini-2.5-flash",
            "gemini-2.5": "gemini-2.5-flash",
            "gemini-2.5-flash": "gemini-2.5-flash",
        }
        
        # 如果是简短名称，转换为完整名称
        for short_name, full_name in model_mappings.items():
            if model_name.lower() == short_name.lower():
                self.model_name = full_name
                break
        else:
            # 使用原始名称
            self.model_name = model_name
        
        # 默认生成配置
        self.default_generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
        # thinking功能目前不被Google AI SDK支持
        # self.thinking_config = {
        #     "thinking_budget": 0  # 设置为0关闭thinking
        # }
        
    def send_message_stream(
        self,
        contents: List[Content],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        signal: Optional[AbortSignal] = None
    ):
        """
        发送消息并返回流式响应（同步生成器）
        完全对齐Gemini CLI的API调用方式
        """
        try:
            # 调试：打印调用信息
            from ..utils.debug_logger import log_info
            log_info("Gemini", f"send_message_stream called")
            log_info("Gemini", f"History length: {len(contents)} messages")
            log_info("Gemini", f"System instruction length: {len(system_instruction) if system_instruction else 0} chars")
            log_info("Gemini", f"Tools count: {len(tools) if tools else 0}")
            
            # 计算历史内容的总字符数
            total_chars = sum(
                sum(len(part.get('text', '')) for part in msg.get('parts', []))
                for msg in contents
            )
            log_info("Gemini", f"Total history content: {total_chars} chars")
            
            # 准备请求参数
            request_contents = self._prepare_contents(contents)
            
            # 获取或创建缓存的模型实例
            model = self._get_or_create_model(system_instruction, tools)
            
            # 使用默认的生成配置
            generation_config = self.default_generation_config.copy()
            
            # 使用重试机制发送消息
            from ..utils.retry_with_backoff import retry_with_backoff_sync
            
            def api_call():
                return model.generate_content(
                    request_contents,
                    generation_config=generation_config,
                    stream=True
                )
            
            # 配置重试选项
            retry_options = RetryOptions(
                max_attempts=3,  # 对于流式响应，减少重试次数
                initial_delay_ms=2000,
                max_delay_ms=10000
            )
            
            response = retry_with_backoff_sync(api_call, retry_options)
            
            # 处理流式响应
            chunk_count = 0
            self._chunk_count = 0  # 重置chunk计数器
            self._stream_token_tracker = None  # 重置token跟踪器
            final_chunk = None  # 跟踪最后一个chunk
            
            for chunk in response:
                chunk_count += 1
                final_chunk = chunk  # 保存每个chunk，最后一个就是最终chunk
                
                if signal and signal.aborted:
                    break
                    
                processed = self._process_chunk(chunk)
                DebugLogger.log_gemini_chunk(chunk_count, chunk, processed)
                yield processed
                
            # 调试：流结束时的总结
            log_info("Gemini", f"🔍 TOKEN DEBUG - Stream ended. Total chunks: {chunk_count}")
            
            # 在流结束后，发送最终的token统计
            if self._stream_token_tracker and final_chunk:
                log_info("Gemini", f"🎯 FINAL TOKEN USAGE - Sending final token statistics")
                yield {
                    "token_usage": self._stream_token_tracker,
                    "_final_token_report": True  # 标记这是最终报告
                }
                
        except Exception as e:
            # 错误处理 - 记录完整错误信息
            from ..utils.debug_logger import log_error
            log_error("Gemini", f"API error: {type(e).__name__}: {str(e)}")
            
            # 在调试模式下显示完整错误，否则显示友好提示
            if DebugLogger.should_log("DEBUG"):
                error_message = f"Gemini API error: {type(e).__name__}: {str(e)}"
            else:
                error_message = "Gemini API is temporarily unstable. Please try again."
            
            yield self._create_error_chunk(error_message)
            
    async def generate_json(
        self,
        contents: List[Content],
        schema: Dict[str, Any],
        signal: Optional[AbortSignal] = None,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成JSON响应 - 用于next_speaker判断等结构化输出
        """
        try:
            # 准备请求
            request_contents = self._prepare_contents(contents)
            
            # 配置JSON模式
            generation_config = {
                "temperature": 0.1,  # 降低温度确保一致性
                "response_mime_type": "application/json",
                "response_schema": schema
            }
            
            # 创建模型实例
            model_config = {}
            if system_instruction:
                model_config['system_instruction'] = system_instruction
                
            model = genai.GenerativeModel(
                model_name=self.model_name,
                **model_config
            )
            
            # 使用重试机制发送请求
            from ..utils.retry_with_backoff import retry_with_backoff_sync
            
            def api_call():
                return model.generate_content(
                    request_contents,
                    generation_config=generation_config
                )
            
            # 配置重试选项
            retry_options = RetryOptions(
                max_attempts=5,
                initial_delay_ms=3000,
                max_delay_ms=20000
            )
            
            response = retry_with_backoff_sync(api_call, retry_options)
            
            # 解析JSON响应
            import json
            return json.loads(response.text)
            
        except Exception as e:
            # 返回默认响应
            return {
                "next_speaker": "user",
                "reasoning": f"Error in JSON generation: {str(e)}"
            }
            
    def _prepare_contents(self, contents: List[Content]) -> List[Dict[str, Any]]:
        """准备API请求的内容格式"""
        prepared = []
        for content in contents:
            # 防御性检查：如果是 protobuf 对象，先转换为字典
            if hasattr(content, '_pb'):
                content_dict = {
                    'role': content.role,
                    'parts': []
                }
                for part in content.parts:
                    if hasattr(part, 'text'):
                        content_dict['parts'].append({'text': part.text})
                    elif hasattr(part, 'function_call'):
                        # 递归转换嵌套的 protobuf 对象
                        fc_dict = {}
                        if hasattr(part.function_call, '__dict__'):
                            for key, value in part.function_call.__dict__.items():
                                if not key.startswith('_'):
                                    fc_dict[key] = value
                        content_dict['parts'].append({'function_call': fc_dict})
                    elif hasattr(part, 'function_response'):
                        fr_dict = {}
                        if hasattr(part.function_response, '__dict__'):
                            for key, value in part.function_response.__dict__.items():
                                if not key.startswith('_'):
                                    fr_dict[key] = value
                        content_dict['parts'].append({'function_response': fr_dict})
                content = content_dict
            
            prepared_content = {
                "role": content["role"],
                "parts": []
            }
            
            for part in content.get("parts", []):
                if part.get("text"):
                    prepared_content["parts"].append({"text": part["text"]})
                elif part.get("function_call"):
                    prepared_content["parts"].append({"function_call": part["function_call"]})
                elif part.get("function_response"):
                    prepared_content["parts"].append({"function_response": part["function_response"]})
                elif part.get("functionResponse"):
                    # 转换驼峰式到下划线格式（Python SDK 使用 function_response）
                    prepared_content["parts"].append({"function_response": part["functionResponse"]})
                elif part.get("functionCall"):
                    # 转换驼峰式到下划线格式
                    prepared_content["parts"].append({"function_call": part["functionCall"]})
            
            # 只有当parts不为空时才添加到prepared列表
            # Gemini API 不允许空的 parts 数组
            if prepared_content["parts"]:
                prepared.append(prepared_content)
            
        return prepared
        
    def _process_chunk(self, chunk) -> Dict[str, Any]:
        """处理流式响应块"""
        result = {}
        
        # 调试：记录chunk序号（需要在调用处传入）
        if not hasattr(self, '_chunk_count'):
            self._chunk_count = 0
        self._chunk_count += 1
        
        # 安全地尝试获取文本内容
        # 注意：当响应包含 function_call 时，访问 chunk.text 会抛出异常
        try:
            if hasattr(chunk, 'text'):
                result["text"] = chunk.text
        except ValueError:
            # 忽略 "Could not convert part.function_call to text" 错误
            pass
            
        # 处理函数调用 - 从 candidates[0].content.parts 中提取
        if hasattr(chunk, 'candidates') and chunk.candidates:
            candidate = chunk.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                content = candidate.content
                if hasattr(content, 'parts') and content.parts:
                    function_calls = []
                    text_parts = []
                    
                    for part in content.parts:
                        # 处理函数调用
                        if hasattr(part, 'function_call') and part.function_call:
                            call = part.function_call
                            function_calls.append({
                                "id": getattr(call, 'id', f"call_{len(function_calls)}"),
                                "name": call.name,
                                "args": dict(call.args) if hasattr(call, 'args') else {}
                            })
                        # 处理文本（如果没有从 chunk.text 获取到）
                        elif hasattr(part, 'text') and part.text and not result.get("text"):
                            text_parts.append(part.text)
                    
                    # 合并文本部分
                    if text_parts and not result.get("text"):
                        result["text"] = "".join(text_parts)
                    
                    # 只在有函数调用时添加function_calls字段
                    if function_calls:
                        result["function_calls"] = function_calls
        
        # 检查 token 使用信息 - 最小侵入性添加
        # Gemini API 的 usage_metadata 通常在最后一个 chunk 中
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            usage = chunk.usage_metadata
            token_info = {
                "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                "completion_tokens": getattr(usage, 'candidates_token_count', 0),
                "total_tokens": getattr(usage, 'total_token_count', 0),
                "cached_tokens": getattr(usage, 'cached_content_token_count', 0)  # 新增：Gemini 2.5的缓存token
            }
            
            # 更新跟踪器（总是保存最新的值）
            self._stream_token_tracker = token_info
            
            # 详细调试信息
            from ..utils.debug_logger import log_info
            log_info("Gemini", f"🔍 TOKEN DEBUG - Chunk #{self._chunk_count} has usage_metadata:")
            log_info("Gemini", f"   - prompt_tokens: {token_info['prompt_tokens']}")
            log_info("Gemini", f"   - completion_tokens: {token_info['completion_tokens']}")
            log_info("Gemini", f"   - total_tokens: {token_info['total_tokens']}")
            log_info("Gemini", f"   - cached_tokens: {token_info['cached_tokens']}")
            if token_info['cached_tokens'] > 0:
                log_info("Gemini", f"   - Cache hit: {token_info['cached_tokens']} tokens cached")
            # 调试：列出usage_metadata的所有属性和值
            if DebugLogger.should_log("DEBUG"):
                attrs = [attr for attr in dir(usage) if not attr.startswith('_')]
                log_info("Gemini", f"   - usage_metadata attributes: {attrs}")
                # 尝试直接访问cached_content_token_count
                try:
                    cached_raw = usage.cached_content_token_count
                    log_info("Gemini", f"   - Raw cached_content_token_count: {cached_raw}")
                except:
                    log_info("Gemini", "   - cached_content_token_count not accessible")
            log_info("Gemini", f"   - From chunk.usage_metadata directly")
            log_info("Gemini", f"   - 🚫 NOT sending token event (will send at stream end)")
            
            # 不再在这里返回token_usage，等待流结束
        # 也检查 candidates 中的 usage_metadata
        elif hasattr(chunk, 'candidates') and chunk.candidates:
            for idx, candidate in enumerate(chunk.candidates):
                if hasattr(candidate, 'usage_metadata') and candidate.usage_metadata:
                    usage = candidate.usage_metadata
                    token_info = {
                        "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                        "completion_tokens": getattr(usage, 'candidates_token_count', 0),
                        "total_tokens": getattr(usage, 'total_token_count', 0),
                        "cached_tokens": getattr(usage, 'cached_content_token_count', 0)  # 新增
                    }
                    
                    # 更新跟踪器
                    self._stream_token_tracker = token_info
                    
                    # 详细调试信息
                    from ..utils.debug_logger import log_info
                    log_info("Gemini", f"🔍 TOKEN DEBUG - Chunk #{self._chunk_count} has usage_metadata in candidate[{idx}]:")
                    log_info("Gemini", f"   - prompt_tokens: {token_info['prompt_tokens']}")
                    log_info("Gemini", f"   - completion_tokens: {token_info['completion_tokens']}")
                    log_info("Gemini", f"   - total_tokens: {token_info['total_tokens']}")
                    log_info("Gemini", f"   - From chunk.candidates[{idx}].usage_metadata")
                    log_info("Gemini", f"   - 🚫 NOT sending token event (will send at stream end)")
                    
                    # 不再在这里返回token_usage
                    break
            
        return result
        
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应块"""
        return {
            "type": "error",
            "error": error_message,
            "text": f"Error: {error_message}"
        }
    
    def _get_or_create_model(
        self, 
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> genai.GenerativeModel:
        """
        获取或创建缓存的模型实例
        只有在配置改变时才重新创建
        """
        # 构建当前配置
        model_config = {}
        if system_instruction:
            model_config['system_instruction'] = system_instruction
            
        # 准备工具配置
        enable_code_execution = self.config.get("enable_code_execution", False)
        
        if enable_code_execution and tools:
            # 如果同时启用了代码执行和函数工具，优先使用函数工具
            print("[INFO Gemini] Code execution enabled but using function tools - code will be executed in conversation")
            model_config['tools'] = [{
                "function_declarations": tools
            }]
        elif enable_code_execution and not tools:
            # 只有代码执行，没有函数工具
            model_config['tools'] = [{
                "code_execution": {}
            }]
        elif tools:
            # 只有函数工具
            model_config['tools'] = [{
                "function_declarations": tools
            }]
        
        # 检查配置是否改变
        config_changed = (
            self._cached_model is None or 
            self._cached_model_config != model_config
        )
        
        # 如果配置改变或没有缓存的模型，创建新的
        if config_changed:
            self._cached_model = genai.GenerativeModel(
                model_name=self.model_name,
                **model_config
            )
            self._cached_model_config = model_config.copy()
            from ..utils.debug_logger import log_info
            log_info("Gemini", "Created new GenerativeModel instance with cached config")
        
        return self._cached_model
    

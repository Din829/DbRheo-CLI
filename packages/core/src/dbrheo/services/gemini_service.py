"""
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
            "gemini": "gemini-2.5-flash",  # 默认且唯一的 Gemini 模型
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
            # 准备请求参数
            request_contents = self._prepare_contents(contents)
            
            # 创建模型实例（每次调用都创建新的）
            model_config = {}
            if system_instruction:
                model_config['system_instruction'] = system_instruction
            
            # 准备工具配置
            # 注意：Gemini API 不支持同时使用 code_execution 和 function_declarations
            enable_code_execution = self.config.get("enable_code_execution", False)
            
            if enable_code_execution and tools:
                # 如果同时启用了代码执行和函数工具，优先使用函数工具
                # 代码执行将通过对话中的代码块实现
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
                
            model = genai.GenerativeModel(
                model_name=self.model_name,
                **model_config
            )
            
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
            for chunk in response:
                chunk_count += 1
                
                if signal and signal.aborted:
                    break
                    
                processed = self._process_chunk(chunk)
                DebugLogger.log_gemini_chunk(chunk_count, chunk, processed)
                yield processed
                
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
            
        return result
        
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应块"""
        return {
            "type": "error",
            "error": error_message,
            "text": f"Error: {error_message}"
        }

"""
Gemini API服务 - 使用新版google-genai SDK
保持与原有接口完全兼容，最小侵入性迁移
"""

import os
import warnings
from typing import List, Dict, Any, Optional, AsyncIterator
try:
    from google import genai
    from google.genai import types
except ImportError as e:
    raise ImportError(
        "请安装新版Gemini SDK: pip install google-genai>=1.0.0"
    ) from e

from ..types.core_types import Content, PartListUnion, AbortSignal
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger
from ..utils.retry_with_backoff import retry_with_backoff, RetryOptions


class GeminiService:
    """
    Gemini API服务 - 使用新版google-genai SDK
    - 与Google Gemini API的通信
    - 流式响应处理
    - 错误处理和重试
    - 模型配置管理
    - 保持与旧版接口完全兼容
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        # 缓存的配置（用于检测是否需要重新生成）
        self._cached_model_config = None
        # Token去重机制
        self._stream_token_tracker = None
        # Client实例
        self._client = None
        # 显式缓存相关
        self._explicit_cache = None  # 缓存对象
        self._cache_key = None  # 缓存内容的标识
        # 初始化API
        self._setup_api()
        
    def _setup_api(self):
        """设置Gemini API - 使用新SDK"""
        # 获取API密钥 - 新SDK支持两个环境变量
        api_key = (
            self.config.get("google_api_key") or 
            os.getenv("GOOGLE_API_KEY") or
            os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required")
        
        # 创建客户端
        self._client = genai.Client(api_key=api_key)
        
        # 配置模型
        model_name = self.config.get_model() or "gemini-2.5-flash"
        
        # 调试
        from ..utils.debug_logger import log_info
        log_info("Gemini", f"config.get_model()返回: {self.config.get_model()}")
        log_info("Gemini", f"使用的model_name: {model_name}")
        
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
                log_info("Gemini", f"映射 {model_name} -> {self.model_name}")
                break
        else:
            # 使用原始名称
            self.model_name = model_name
            log_info("Gemini", f"使用原始名称: {self.model_name}")
        
        # 默认生成配置
        self.default_generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
    def _get_cache_key(self, system_instruction: Optional[str], tools: Optional[List[Dict[str, Any]]]) -> str:
        """
        生成缓存键 - 基于系统指令和工具的哈希
        """
        import hashlib
        import json
        
        # 组合系统指令和工具生成唯一标识
        cache_content = {
            "system_instruction": system_instruction or "",
            "tools": tools or []
        }
        
        # 生成稳定的哈希值
        content_str = json.dumps(cache_content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
        
    def _ensure_explicit_cache(self, system_instruction: Optional[str], tools: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        """
        确保显式缓存存在并返回缓存名称
        如果缓存创建失败，返回 None（回退到普通请求）
        """
        # 检查是否启用显式缓存
        enable_cache = self.config.get("enable_explicit_cache", True)
        from ..utils.debug_logger import log_info
        log_info("Gemini", f"Explicit cache enabled: {enable_cache}")
        
        if not enable_cache:
            log_info("Gemini", "Explicit cache is disabled")
            return None
            
        # 计算当前内容的缓存键
        current_key = self._get_cache_key(system_instruction, tools)
        log_info("Gemini", f"Cache key: {current_key}")
        log_info("Gemini", f"Previous cache key: {self._cache_key}")
        log_info("Gemini", f"Existing cache: {self._explicit_cache}")
        
        # 如果缓存键没变且缓存存在，直接返回
        if current_key == self._cache_key and self._explicit_cache:
            log_info("Gemini", f"Using existing explicit cache: {self._explicit_cache}")
            return self._explicit_cache
            
        # 需要创建新缓存
        try:
            from ..utils.debug_logger import log_info
            log_info("Gemini", "Creating new explicit cache...")
            
            # 准备缓存配置
            cache_config_dict = {
                'display_name': f'dbrheo_cache_{current_key}',
                'system_instruction': system_instruction,
                'ttl': "3600s"  # 1小时 TTL
            }
            
            # 如果有工具，需要转换格式
            if tools:
                # 尝试直接使用工具声明
                # 如果失败，可能需要转换为 Tool 对象
                try:
                    # 首先尝试创建 Tool 对象
                    # 所有函数声明应该在一个 Tool 对象中
                    function_declarations = []
                    for tool_dict in tools:
                        # 创建函数声明
                        function_declaration = types.FunctionDeclaration(
                            name=tool_dict['name'],
                            description=tool_dict['description'],
                            parameters=tool_dict['parameters']
                        )
                        function_declarations.append(function_declaration)
                    
                    # 创建单个 Tool 对象包含所有函数
                    tool_object = types.Tool(function_declarations=function_declarations)
                    cache_config_dict['tools'] = [tool_object]
                except:
                    # 如果失败，尝试直接使用原始格式
                    cache_config_dict['tools'] = tools
                
            cache_config = types.CreateCachedContentConfig(**cache_config_dict)
            
            # 创建缓存
            cache = self._client.caches.create(
                model=self.model_name,
                config=cache_config
            )
            
            # 更新缓存信息
            self._explicit_cache = cache.name
            self._cache_key = current_key
            
            log_info("Gemini", f"✓ Explicit cache created: {cache.name}")
            return cache.name
            
        except Exception as e:
            # 缓存创建失败，记录但不影响正常功能
            from ..utils.debug_logger import log_error
            log_error("Gemini", f"Failed to create explicit cache: {e}")
            return None
        
    def send_message_stream(
        self,
        contents: List[Content],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        signal: Optional[AbortSignal] = None
    ):
        """
        发送消息并返回流式响应（同步生成器）
        完全保持原有接口不变
        """
        try:
            # 调试：打印调用信息
            from ..utils.debug_logger import log_info
            log_info("Gemini", f"send_message_stream called (new SDK)")
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
            
            # 尝试使用显式缓存
            cached_content_name = self._ensure_explicit_cache(system_instruction, tools)
            
            # 构建配置
            config = self._build_generate_config(
                system_instruction=system_instruction,
                tools=tools,
                generation_config=self.default_generation_config.copy(),
                cached_content=cached_content_name  # 传递缓存名称
            )
            
            # 使用重试机制发送消息
            from ..utils.retry_with_backoff import retry_with_backoff_sync
            
            def api_call():
                # 新SDK的流式API
                return self._client.models.generate_content_stream(
                    model=self.model_name,
                    contents=request_contents,
                    config=config
                )
            
            # 配置重试选项
            retry_options = RetryOptions(
                max_attempts=3,  # 对于流式响应，减少重试次数
                initial_delay_ms=2000,
                max_delay_ms=10000
            )
            
            response_stream = retry_with_backoff_sync(api_call, retry_options)
            
            # 处理流式响应
            chunk_count = 0
            self._chunk_count = 0  # 重置chunk计数器
            self._stream_token_tracker = None  # 重置token跟踪器
            final_chunk = None  # 跟踪最后一个chunk
            
            for chunk in response_stream:
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
            if self._stream_token_tracker:
                log_info("Gemini", f"🎯 FINAL TOKEN USAGE - Sending final token statistics")
                log_info("Gemini", f"   - Final stats: {self._stream_token_tracker}")
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
        保持原有接口不变
        """
        try:
            # 准备请求
            request_contents = self._prepare_contents(contents)
            
            # 配置JSON模式
            generation_config = types.GenerateContentConfig(
                temperature=0.1,  # 降低温度确保一致性
                response_mime_type="application/json",
                response_schema=schema,
                system_instruction=system_instruction
            )
            
            # 使用重试机制发送请求
            from ..utils.retry_with_backoff import retry_with_backoff_sync
            
            def api_call():
                # 新SDK的同步API
                return self._client.models.generate_content(
                    model=self.model_name,
                    contents=request_contents,
                    config=generation_config
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
        """准备API请求的内容格式 - 与原版保持一致"""
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
        """处理流式响应块 - 适配新SDK的响应格式"""
        result = {}
        
        # 调试：记录chunk序号
        if not hasattr(self, '_chunk_count'):
            self._chunk_count = 0
        self._chunk_count += 1
        
        # 新SDK中，文本直接在chunk.text属性
        if hasattr(chunk, 'text') and chunk.text:
            result["text"] = chunk.text
            
        # 处理函数调用 - 新SDK可能有不同的结构
        if hasattr(chunk, 'candidates') and chunk.candidates:
            candidate = chunk.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                content = candidate.content
                if hasattr(content, 'parts') and content.parts:
                    function_calls = []
                    
                    for part in content.parts:
                        # 处理函数调用
                        if hasattr(part, 'function_call') and part.function_call:
                            call = part.function_call
                            
                            # 更仔细地提取参数
                            args = {}
                            if hasattr(call, 'args') and call.args is not None:
                                from ..utils.debug_logger import log_info
                                log_info("Gemini", f"Function call args type: {type(call.args)}")
                                log_info("Gemini", f"Function call args value: {call.args}")
                                
                                # 新SDK中 args 已经是 dict，直接使用
                                if isinstance(call.args, dict):
                                    args = call.args
                                else:
                                    # 兼容性处理
                                    try:
                                        args = dict(call.args)
                                    except Exception as e:
                                        from ..utils.debug_logger import log_error
                                        log_error("Gemini", f"Failed to convert args to dict: {e}")
                                        log_error("Gemini", f"Args type: {type(call.args)}, value: {call.args}")
                            else:
                                from ..utils.debug_logger import log_info
                                log_info("Gemini", f"Function call has no args or args is None")
                            
                            # 调试：打印提取的参数
                            from ..utils.debug_logger import log_info
                            log_info("Gemini", f"Extracted function call: {call.name}, args: {args}")
                            
                            function_calls.append({
                                "id": getattr(call, 'id', f"call_{len(function_calls)}"),
                                "name": call.name,
                                "args": args
                            })
                    
                    # 只在有函数调用时添加function_calls字段
                    if function_calls:
                        result["function_calls"] = function_calls
        
        # 检查 token 使用信息 - 适配新SDK
        usage_metadata = None
        
        # 尝试从chunk直接获取
        if hasattr(chunk, 'usage_metadata'):
            usage_metadata = chunk.usage_metadata
        # 尝试从candidates获取
        elif hasattr(chunk, 'candidates') and chunk.candidates:
            for candidate in chunk.candidates:
                if hasattr(candidate, 'usage_metadata') and candidate.usage_metadata:
                    usage_metadata = candidate.usage_metadata
                    break
                    
        if usage_metadata:
            # 新SDK中，cached_content_token_count可能是None而不是0
            cached_count = getattr(usage_metadata, 'cached_content_token_count', None)
            
            # 调试：直接访问属性
            from ..utils.debug_logger import log_info
            log_info("Gemini", f"📊 CACHE DEBUG - Direct access:")
            log_info("Gemini", f"   - usage_metadata type: {type(usage_metadata)}")
            log_info("Gemini", f"   - cached_content_token_count: {usage_metadata.cached_content_token_count}")
            log_info("Gemini", f"   - getattr result: {cached_count}")
            
            # 正确获取缓存值
            # 注意：新SDK中cached_content_token_count可能是实际值，不一定是None
            if cached_count is None:
                cached_count = 0
            else:
                # 确保是整数
                cached_count = int(cached_count)
                
            token_info = {
                "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                "cached_tokens": cached_count
            }
            
            # 更新跟踪器（总是保存最新的值）
            self._stream_token_tracker = token_info
            
            # 详细调试信息
            from ..utils.debug_logger import log_info
            log_info("Gemini", f"🔍 TOKEN DEBUG - Chunk #{self._chunk_count} has usage_metadata:")
            log_info("Gemini", f"   - prompt_tokens: {token_info['prompt_tokens']}")
            log_info("Gemini", f"   - completion_tokens: {token_info['completion_tokens']}")
            log_info("Gemini", f"   - total_tokens: {token_info['total_tokens']}")
            log_info("Gemini", f"   - cached_tokens: {token_info['cached_tokens']} (raw: {cached_count})")
            if token_info['cached_tokens'] > 0:
                log_info("Gemini", f"   - ✅ Cache hit: {token_info['cached_tokens']} tokens cached")
            elif cached_count is None:
                log_info("Gemini", f"   - ⚠️  cached_content_token_count is None (新SDK的已知问题)")
            log_info("Gemini", f"   - 🚫 NOT sending token event (will send at stream end)")
            
        return result
        
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应块"""
        return {
            "type": "error",
            "error": error_message,
            "text": f"Error: {error_message}"
        }
    
    def _build_generate_config(
        self, 
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None
    ) -> types.GenerateContentConfig:
        """
        构建生成配置 - 新SDK使用config参数
        """
        config_dict = {}
        
        # 如果有缓存，使用缓存而不是系统指令
        if cached_content:
            config_dict['cached_content'] = cached_content
            # 使用缓存时不需要再传system_instruction
        elif system_instruction:
            # 没有缓存时才使用系统指令
            config_dict['system_instruction'] = system_instruction
            
        # 生成参数
        if generation_config:
            for key, value in generation_config.items():
                config_dict[key] = value
                
        # 工具配置 - 只有在不使用缓存时才添加工具
        if not cached_content:
            enable_code_execution = self.config.get("enable_code_execution", False)
            
            if enable_code_execution and tools:
                # 如果同时启用了代码执行和函数工具，优先使用函数工具
                from ..utils.debug_logger import log_info
                log_info("Gemini", "Code execution enabled but using function tools")
                # 转换工具格式
                try:
                    function_declarations = []
                    for tool_dict in tools:
                        function_declaration = types.FunctionDeclaration(
                            name=tool_dict['name'],
                            description=tool_dict['description'],
                            parameters=tool_dict['parameters']
                        )
                        function_declarations.append(function_declaration)
                    tool_object = types.Tool(function_declarations=function_declarations)
                    config_dict['tools'] = [tool_object]
                except:
                    config_dict['tools'] = tools
            elif enable_code_execution and not tools:
                # 只有代码执行，没有函数工具
                # 新SDK中代码执行的配置方式可能不同，需要查看文档
                from ..utils.debug_logger import log_info
                log_info("Gemini", "Code execution enabled (new SDK)")
                # config_dict['tools'] = [{"code_execution": {}}]  # 待确认格式
            elif tools:
                # 只有函数工具
                # 转换工具格式
                try:
                    function_declarations = []
                    for tool_dict in tools:
                        function_declaration = types.FunctionDeclaration(
                            name=tool_dict['name'],
                            description=tool_dict['description'],
                            parameters=tool_dict['parameters']
                        )
                        function_declarations.append(function_declaration)
                    tool_object = types.Tool(function_declarations=function_declarations)
                    config_dict['tools'] = [tool_object]
                except:
                    config_dict['tools'] = tools
        
        # 返回配置对象
        return types.GenerateContentConfig(**config_dict)
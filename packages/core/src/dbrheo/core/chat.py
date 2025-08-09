"""
DatabaseChat - 对话管理
实现双历史机制、历史过滤和验证，完全对齐Gemini CLI的GeminiChat
"""

from typing import List, Dict, Any, Optional, AsyncIterator
from ..types.core_types import Content, PartListUnion
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info
from .prompts import DatabasePromptManager
from ..tools.registry import DatabaseToolRegistry

# 导入实时日志系统（如果启用）
import os
if os.getenv('DBRHEO_ENABLE_REALTIME_LOG') == 'true':
    try:
        from ..utils.realtime_logger import log_conversation, log_system
        REALTIME_LOG_ENABLED = True
    except ImportError:
        REALTIME_LOG_ENABLED = False
else:
    REALTIME_LOG_ENABLED = False


class DatabaseChat:
    """
    数据库Agent的对话管理
    - 双历史机制（get_history(curated=True/False)）
    - 历史过滤和验证（_extract_curated_history）
    - 与Gemini API的通信
    - 表结构缓存管理（discovered_schemas）
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        # 完整历史（comprehensive history）- 包含所有对话
        self.history: List[Content] = []
        # 已发现的表结构缓存
        self.discovered_schemas: Dict[str, Any] = {}
        # 工具注册表（每个Chat实例都有自己的工具上下文）
        self.tool_registry = None
        
        # 缓存的LLM服务（最小侵入性优化）
        self._llm_service = None
        self._tools = None  # 缓存工具声明
        self._system_prompt = None  # 缓存系统提示词
        
    def get_history(self, curated: bool = False) -> List[Content]:
        """
        获取历史记录 - 与Gemini CLI完全一致
        curated=True时返回过滤后的历史，False时返回完整历史
        """
        if curated:
            return self._extract_curated_history(self.history)
        return self._deep_clone(self.history)
        
    def _extract_curated_history(self, comprehensive_history: List[Content]) -> List[Content]:
        """
        智能历史过滤 - 完全参考Gemini CLI的extractCuratedHistory
        移除无效的模型响应，保持完整的交互对
        """
        if not comprehensive_history:
            return []
            
        curated_history = []
        i = 0
        
        while i < len(comprehensive_history):
            if comprehensive_history[i]['role'] == 'user':
                # 用户消息总是被保留
                curated_history.append(comprehensive_history[i])
                i += 1
            else:
                # 收集连续的模型响应
                model_output = []
                is_valid = True
                
                while i < len(comprehensive_history) and comprehensive_history[i]['role'] == 'model':
                    model_output.append(comprehensive_history[i])
                    if is_valid and not self._is_valid_content(comprehensive_history[i]):
                        is_valid = False
                    i += 1
                    
                if is_valid:
                    curated_history.extend(model_output)
                else:
                    # 如果模型响应无效，移除前面的用户输入（保持完整交互对）
                    if curated_history:
                        curated_history.pop()
                        
        return curated_history
        
    def _is_valid_content(self, content: Content) -> bool:
        """
        内容有效性检查 - 完全参考Gemini CLI的isValidContent
        """
        if not content.get('parts') or len(content['parts']) == 0:
            return False
            
        for part in content['parts']:
            if not part or len(part) == 0:
                return False
            # 空文本无效（除非是thought）
            if not part.get('thought') and part.get('text') == '':
                return False
                
        return True
        
    def add_history(self, content: Content):
        """添加历史记录"""
        # 确保添加的内容是普通字典，而非 protobuf 对象
        # 使用更全面的检测方法
        is_protobuf = (
            hasattr(content, '_pb') or
            'google' in str(type(content).__module__) or
            hasattr(content, 'SerializeToString') or
            hasattr(content, 'DESCRIPTOR')
        )
        
        if is_protobuf:
            # 转换 protobuf 为字典
            content_dict = {
                'role': content.role,
                'parts': []
            }
            for part in content.parts:
                if hasattr(part, 'text'):
                    content_dict['parts'].append({'text': part.text})
                elif hasattr(part, 'function_call'):
                    content_dict['parts'].append({'function_call': self._safe_clone(part.function_call)})
                elif hasattr(part, 'function_response'):
                    content_dict['parts'].append({'function_response': self._safe_clone(part.function_response)})
            content = content_dict
        else:
            # 使用深度克隆确保不会有引用问题
            content = self._safe_clone(content)
        
        self.history.append(content)
        
    def set_history(self, history: List[Content]):
        """设置历史记录（用于压缩后更新）"""
        self.history = history
        
    def _deep_clone(self, obj):
        """深度克隆对象 - 灵活处理各种数据类型，避免序列化问题"""
        return self._safe_clone(obj)
    
    def _safe_clone(self, obj, _seen=None):
        """
        安全的深度克隆实现
        - 递归处理各种数据结构
        - 智能处理不可序列化的对象（如 protobuf）
        - 保持灵活性，自动适应新的数据类型
        """
        # 处理循环引用
        if _seen is None:
            _seen = {}
        
        # 获取对象的唯一标识
        obj_id = id(obj)
        if obj_id in _seen:
            return _seen[obj_id]
        
        # 基本类型 - 直接返回（不可变）
        if obj is None or isinstance(obj, (str, int, float, bool, bytes)):
            return obj
        
        # 列表 - 递归克隆每个元素
        if isinstance(obj, list):
            cloned = []
            _seen[obj_id] = cloned
            for item in obj:
                cloned.append(self._safe_clone(item, _seen))
            return cloned
        
        # 字典 - 递归克隆键值对
        if isinstance(obj, dict):
            cloned = {}
            _seen[obj_id] = cloned
            for key, value in obj.items():
                # 键通常是简单类型，但也要安全处理
                cloned_key = self._safe_clone(key, _seen)
                cloned_value = self._safe_clone(value, _seen)
                cloned[cloned_key] = cloned_value
            return cloned
        
        # 元组 - 转换为列表处理后再转回
        if isinstance(obj, tuple):
            cloned_list = []
            for item in obj:
                cloned_list.append(self._safe_clone(item, _seen))
            cloned = tuple(cloned_list)
            _seen[obj_id] = cloned
            return cloned
        
        # 集合
        if isinstance(obj, set):
            cloned = set()
            _seen[obj_id] = cloned
            for item in obj:
                cloned.add(self._safe_clone(item, _seen))
            return cloned
        
        # 尝试处理其他对象类型
        try:
            # 检查是否是 protobuf 或其他特殊对象
            obj_type = type(obj).__name__
            obj_module = str(type(obj).__module__)
            
            # 更全面地检测 protobuf 对象
            is_protobuf = any([
                'google' in obj_module,
                'protobuf' in obj_module,
                'MessageMapContainer' in obj_type,
                'Marshal' in obj_type,
                hasattr(obj, '_pb'),
                hasattr(obj, 'SerializeToString'),  # protobuf 特有方法
                hasattr(obj, 'DESCRIPTOR')  # protobuf 描述符
            ])
            
            if is_protobuf:
                # 尝试将其转换为普通字典
                if hasattr(obj, 'items'):
                    return {k: self._safe_clone(v, _seen) for k, v in obj.items()}
                elif hasattr(obj, '__iter__'):
                    return [self._safe_clone(item, _seen) for item in obj]
                else:
                    # 无法处理，返回字符串表示
                    return str(obj)
            
            # 对于有 __dict__ 属性的普通对象
            if hasattr(obj, '__dict__'):
                cloned = type(obj).__new__(type(obj))
                _seen[obj_id] = cloned
                for key, value in obj.__dict__.items():
                    setattr(cloned, key, self._safe_clone(value, _seen))
                return cloned
            
            # 尝试使用 copy 模块
            import copy
            return copy.copy(obj)
            
        except Exception as e:
            # 如果所有方法都失败，返回字符串表示
            # 这确保不会因为无法克隆某个对象而导致整个流程失败
            log_info("Chat", f"无法克隆对象 {type(obj).__name__}: {str(e)}, 使用字符串表示")
            return f"<{type(obj).__name__}: {str(obj)[:100]}...>"
        
    async def send_message_stream(self, request: PartListUnion, prompt_id: str):
        """
        发送消息到Gemini API并返回流式响应
        完全对齐Gemini CLI：让AI基于工具描述自主选择工具
        """
        from ..services.llm_factory import create_llm_service
        from ..tools.registry import DatabaseToolRegistry
        
        # 首次调用时初始化缓存的服务和工具（最小侵入性优化）
        if self._llm_service is None:
            log_info("Chat", "Initializing LLM service and tools (first time only)")
            # 创建 LLM 服务（根据配置自动选择）
            self._llm_service = create_llm_service(self.config)
            
            # 获取所有可用工具的函数声明
            # 优先使用共享的 tool_registry（最小侵入性）
            tool_registry = self.config.get_test_config('tool_registry')
            if not tool_registry:
                # 兼容性：如果没有共享的，创建新的
                tool_registry = DatabaseToolRegistry(self.config)
            self._tools = tool_registry.get_function_declarations()
            log_info("Chat", f"Loaded {len(self._tools)} tools")
            
            # 获取系统提示词
            prompt_manager = DatabasePromptManager()
            self._system_prompt = prompt_manager.get_core_system_prompt()
            log_info("Chat", f"System prompt length: {len(self._system_prompt)} chars")
        else:
            log_info("Chat", "Using cached LLM service")
        
        # 准备请求内容
        if isinstance(request, str):
            request_content = [{'text': request}]
        elif isinstance(request, list):
            request_content = request
        else:
            request_content = [request]
            
        # 只有当有实际内容时才添加到历史记录
        if request_content:
            user_content = {
                'role': 'user',
                'parts': request_content
            }
            self.add_history(user_content)
            
            # 实时日志记录用户输入
            if REALTIME_LOG_ENABLED:
                user_text = ""
                for part in request_content:
                    if isinstance(part, dict) and 'text' in part:
                        user_text += part['text']
                if user_text:
                    log_conversation("User", user_text)
        
        # 发送消息并获取流式响应
        full_history = self.get_history()
        
        # 调试：显示历史总体信息
        total_history_chars = sum(
            sum(len(part.get('text', '')) for part in msg.get('parts', []))
            for msg in full_history
        )
        log_info("Chat", f"📋 HISTORY ANALYSIS:")
        log_info("Chat", f"   - Total messages: {len(full_history)}")
        log_info("Chat", f"   - Total characters: {total_history_chars}")
        log_info("Chat", f"   - Message breakdown:")
        for i, msg in enumerate(full_history):
            msg_chars = sum(len(part.get('text', '')) for part in msg.get('parts', []))
            msg_preview = ''
            if msg.get('parts') and len(msg['parts']) > 0:
                first_part = msg['parts'][0]
                if 'text' in first_part:
                    msg_preview = first_part['text'][:30].replace('\n', ' ')
                elif 'function_call' in first_part:
                    msg_preview = f"[function_call: {first_part['function_call'].get('name', 'unknown')}]"
                elif 'function_response' in first_part or 'functionResponse' in first_part:
                    msg_preview = "[function_response]"
            log_info("Chat", f"     [{i}] {msg['role']}: {msg_chars} chars - {msg_preview}...")
        
        # 使用服务发送消息，包含工具声明
        response_parts = []
        
        # 获取同步生成器
        log_info("Chat", f"Calling send_message_stream with history: {len(full_history)} messages")
        sync_generator = self._llm_service.send_message_stream(
            full_history,
            tools=self._tools,  # 提供工具给AI自主选择
            system_instruction=self._system_prompt  # 使用DbRheo系统提示词
        )
        
        # 将同步生成器转换为异步生成器
        # 使用简单的yield来逐个处理chunk，保持异步特性
        chunk_count = 0
        try:
            for chunk in sync_generator:
                chunk_count += 1
                # 使用优化的日志记录
                if DebugLogger.get_rules()["show_chunk_details"]:
                    # 只在需要时显示块详情
                    if 'text' in chunk:
                        DebugLogger.log_turn_event("chunk_received", chunk)
                # 异步yield chunk
                yield chunk
                
                # 收集响应内容用于保存到历史
                if chunk.get('text'):
                    response_parts.append({'text': chunk['text']})
                if chunk.get('function_calls'):
                    for call in chunk['function_calls']:
                        response_parts.append({
                            'function_call': {
                                'id': call['id'],
                                'name': call['name'],
                                'args': call['args']
                            }
                        })
        finally:
            # 使用finally确保历史记录总是被更新，即使生成器被提前中断
            # 将模型响应添加到历史
            # 使用优化的日志总结
            DebugLogger.log_chat_summary(chunk_count, response_parts)
            if response_parts:
                model_content = {
                    'role': 'model',
                    'parts': response_parts
                }
                self.add_history(model_content)
                if DebugLogger.get_rules()["show_history_length"]:
                    log_info("Chat", "Model response added to history")
                
                # 实时日志记录模型响应
                if REALTIME_LOG_ENABLED:
                    model_text = ""
                    for part in response_parts:
                        if isinstance(part, dict) and 'text' in part:
                            model_text += part['text']
                    if model_text:
                        log_conversation("Agent", model_text)

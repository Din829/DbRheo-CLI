"""
调试日志优化工具
提供精简的DEBUG日志输出，保留关键信息同时减少冗余
"""

import os
from typing import Any, Optional, Dict
from functools import wraps

# 从环境变量控制日志级别
DEBUG_LEVEL = os.getenv("DBRHEO_DEBUG_LEVEL", "INFO").upper()
# 控制详细程度：MINIMAL, NORMAL, VERBOSE  
# 注意：使用get_verbosity()获取最新值，而不是直接使用DEBUG_VERBOSITY
DEBUG_VERBOSITY = os.getenv("DBRHEO_DEBUG_VERBOSITY", "NORMAL").upper()

def get_verbosity():
    """动态获取当前详细程度"""
    return os.getenv("DBRHEO_DEBUG_VERBOSITY", "NORMAL").upper()

class DebugLogger:
    """优化的调试日志器"""
    
    # 定义哪些信息在不同详细程度下显示
    VERBOSITY_RULES = {
        "MINIMAL": {
            # 最精简：只显示关键动作和错误
            "show_raw_chunks": False,
            "show_processed_chunks": False,
            "show_chunk_details": False,
            "show_history_length": True,
            "show_tool_calls": True,
            "show_errors": True,
            "truncate_content": 30,
        },
        "NORMAL": {
            # 正常：显示主要流程但隐藏原始数据
            "show_raw_chunks": False,
            "show_processed_chunks": True,
            "show_chunk_details": True,
            "show_history_length": True,
            "show_tool_calls": True,
            "show_errors": True,
            "truncate_content": 50,
        },
        "VERBOSE": {
            # 详细：显示所有信息（当前状态）
            "show_raw_chunks": True,
            "show_processed_chunks": True,
            "show_chunk_details": True,
            "show_history_length": True,
            "show_tool_calls": True,
            "show_errors": True,
            "truncate_content": None,  # 不截断
        }
    }
    
    @classmethod
    def get_rules(cls) -> Dict[str, Any]:
        """获取当前详细程度的规则"""
        current_verbosity = get_verbosity()
        return cls.VERBOSITY_RULES.get(current_verbosity, cls.VERBOSITY_RULES["NORMAL"])
    
    @classmethod
    def should_log(cls, level: str = "DEBUG") -> bool:
        """判断是否应该记录日志"""
        if DEBUG_LEVEL == "ERROR" and level != "ERROR":
            return False
        if DEBUG_LEVEL == "INFO" and level == "DEBUG":
            return False
        return True
    
    @classmethod
    def truncate_content(cls, content: str, max_length: Optional[int] = None) -> str:
        """截断内容到指定长度"""
        if max_length is None:
            max_length = cls.get_rules()["truncate_content"]
        
        if max_length is None or len(content) <= max_length:
            return content
            
        return f"{content[:max_length]}..."
    
    @classmethod
    def log_gemini_chunk(cls, chunk_count: int, chunk: Any, processed: Optional[Dict] = None):
        """记录Gemini响应块"""
        if not cls.should_log("DEBUG"):
            return
            
        rules = cls.get_rules()
        
        # 原始块（仅在VERBOSE模式）
        if rules["show_raw_chunks"]:
            print(f"[DEBUG Gemini] Raw chunk #{chunk_count}: {chunk}")
        
        # 处理后的块
        if rules["show_processed_chunks"] and processed:
            # 智能格式化：根据内容类型选择显示方式
            if "text" in processed:
                content = cls.truncate_content(processed["text"])
                print(f"[DEBUG Gemini] Chunk #{chunk_count}: text='{content}'")
            elif "function_calls" in processed:
                # 简化函数调用显示
                calls = processed["function_calls"]
                call_names = [call.get("name", "Unknown") for call in calls]
                print(f"[DEBUG Gemini] Chunk #{chunk_count}: tools={call_names}")
            else:
                print(f"[DEBUG Gemini] Chunk #{chunk_count}: {list(processed.keys())}")
    
    @classmethod
    def log_turn_event(cls, event_type: str, data: Any):
        """记录Turn事件"""
        if not cls.should_log("DEBUG"):
            return
            
        rules = cls.get_rules()
        
        if event_type == "chunk_received" and rules["show_chunk_details"]:
            # 只在NORMAL以上显示
            if "text" in data:
                content = cls.truncate_content(data.get("text", ""))
                print(f"[DEBUG Turn] Text: '{content}'")
            elif "function_calls" in data:
                print(f"[DEBUG Turn] Tool call detected")
        
        elif event_type == "tool_request" and rules["show_tool_calls"]:
            # 工具调用总是显示（重要信息）
            tool_name = data.name if hasattr(data, 'name') else 'Unknown'
            print(f"[DEBUG Turn] Tool request: {tool_name}")
        
        elif event_type == "summary":
            # 总结信息在MINIMAL以上显示
            print(f"[DEBUG Turn] Completed: {data} chunks")
    
    @classmethod
    def log_client_event(cls, event_type: str, data: Any):
        """记录Client事件"""
        if not cls.should_log("DEBUG"):
            return
            
        rules = cls.get_rules()
        
        if event_type == "tools_found" and rules["show_tool_calls"]:
            print(f"[DEBUG Client] Tools to execute: {data}")
        
        elif event_type == "execution_complete":
            # 执行完成信息
            if DEBUG_VERBOSITY == "MINIMAL":
                print(f"[DEBUG Client] Tools completed: {data['count']}")
            else:
                print(f"[DEBUG Client] Execution complete: {data}")
        
        elif event_type == "history_update" and rules["show_history_length"]:
            print(f"[DEBUG Client] History length: {data}")
        
        elif event_type == "recursion_start":
            # 递归调用在所有级别显示
            print(f"[DEBUG Client] Starting recursion...")
    
    @classmethod
    def log_scheduler_event(cls, event_type: str, data: Any):
        """记录Scheduler事件"""
        if not cls.should_log("DEBUG"):
            return
            
        rules = cls.get_rules()
        
        if event_type == "execution_start" and rules["show_tool_calls"]:
            print(f"[DEBUG Scheduler] Executing {data} tools")
        
        elif event_type == "tool_complete":
            tool_name = data.get("name", "Unknown")
            current_verbosity = get_verbosity()
            if current_verbosity == "MINIMAL":
                print(f"[DEBUG Scheduler] ✓ {tool_name}")
            else:
                # 在NORMAL和VERBOSE模式下显示工具响应
                response = data.get("response", {})
                if current_verbosity == "VERBOSE":
                    # VERBOSE模式：显示完整响应
                    print(f"[DEBUG Scheduler] {tool_name} completed with response: {response}")
                elif isinstance(response, dict):
                    # NORMAL模式：显示functionResponse内容
                    if "functionResponse" in response:
                        func_resp = response["functionResponse"]
                        resp_content = func_resp.get("response", {}).get("output", "No output")
                        output = cls.truncate_content(str(resp_content), 100)
                        print(f"[DEBUG Scheduler] {tool_name} returned: {output}")
                    elif "output" in response:
                        output = cls.truncate_content(str(response["output"]), 100)
                        print(f"[DEBUG Scheduler] {tool_name} returned: {output}")
                    else:
                        print(f"[DEBUG Scheduler] {tool_name} completed")
                else:
                    print(f"[DEBUG Scheduler] {tool_name} completed")
    
    @classmethod
    def log_chat_summary(cls, total_chunks: int, response_parts: list):
        """记录Chat总结信息"""
        if not cls.should_log("DEBUG"):
            return
            
        current_verbosity = get_verbosity()
        if current_verbosity == "MINIMAL":
            # 最精简模式：只显示块数
            print(f"[DEBUG Chat] Response: {total_chunks} chunks")
        elif current_verbosity == "NORMAL":
            # 正常模式：显示响应类型统计
            text_chunks = sum(1 for p in response_parts if "text" in p)
            tool_chunks = sum(1 for p in response_parts if "function_call" in p)
            print(f"[DEBUG Chat] Response: {text_chunks} text, {tool_chunks} tools")
        else:
            # 详细模式：显示完整信息
            print(f"[DEBUG Chat] Total chunks: {total_chunks}")
            print(f"[DEBUG Chat] Response parts: {response_parts}")


def debug_log(component: str):
    """装饰器：自动为函数添加调试日志"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_verbosity = get_verbosity()
            if DebugLogger.should_log("DEBUG") and current_verbosity == "VERBOSE":
                print(f"[DEBUG {component}] Calling {func.__name__}")
            
            result = func(*args, **kwargs)
            
            if DebugLogger.should_log("DEBUG") and current_verbosity == "VERBOSE":
                print(f"[DEBUG {component}] {func.__name__} completed")
            
            return result
        return wrapper
    return decorator


# 便捷函数
def log_error(component: str, error: Exception):
    """记录错误（总是显示）"""
    print(f"[ERROR {component}] {type(error).__name__}: {error}")


def log_info(component: str, message: str):
    """记录信息级别日志"""
    if DebugLogger.should_log("INFO"):
        print(f"[INFO {component}] {message}")
"""
DatabaseMemoryManager - 分层记忆管理系统
完全对齐Gemini CLI的MemoryTool设计，支持全局、项目、会话级记忆
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from enum import Enum

from ..config.base import DatabaseConfig
from ..types.core_types import Part
from ..tools.base import DatabaseTool
from ..types.tool_types import ToolResult


class MemoryScope(Enum):
    """记忆范围枚举"""
    GLOBAL = "global"      # 全局记忆
    PROJECT = "project"    # 项目记忆
    SESSION = "session"    # 会话记忆


class DatabaseMemoryManager:
    """
    数据库Agent记忆管理系统 - 完全对齐Gemini CLI
    支持分层记忆存储和检索
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.memory_files = {
            MemoryScope.GLOBAL: Path.home() / ".database_agent" / "MEMORY.md",
            MemoryScope.PROJECT: Path("./DATABASE_AGENT.md"),
            MemoryScope.SESSION: Path("./.database_agent/session.md"),
        }
        
        # 确保全局记忆目录存在
        global_dir = self.memory_files[MemoryScope.GLOBAL].parent
        global_dir.mkdir(parents=True, exist_ok=True)
        
    async def load_hierarchical_memory(self) -> str:
        """
        加载分层记忆 - 参考Gemini CLI的loadServerHierarchicalMemory
        返回所有层级的记忆内容，用于初始化Agent时的上下文
        """
        memories = []
        
        # 按优先级顺序加载（全局 → 项目 → 会话）
        for scope in [MemoryScope.GLOBAL, MemoryScope.PROJECT, MemoryScope.SESSION]:
            memory_file = self.memory_files[scope]
            
            if memory_file.exists():
                try:
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            # 添加文件路径标识（与Gemini CLI一致）
                            relative_path = self._get_relative_path(memory_file)
                            memories.append(f"# {relative_path}\n{content}")
                except Exception:
                    # 静默处理读取错误（与Gemini CLI一致）
                    continue
                    
        return "\n\n".join(memories) if memories else ""
        
    async def save_memory(
        self, 
        information: str, 
        category: str = "general",
        scope: MemoryScope = MemoryScope.PROJECT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存记忆到指定范围
        
        Args:
            information: 要保存的信息
            category: 信息类别
            scope: 记忆范围
            metadata: 额外的元数据
            
        Returns:
            是否保存成功
        """
        try:
            memory_file = self.memory_files[scope]
            
            # 确保目录存在
            memory_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有记忆
            existing_memory = ""
            if memory_file.exists():
                with open(memory_file, 'r', encoding='utf-8') as f:
                    existing_memory = f.read()
                    
            # 构建新的记忆条目
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_entry = f"\n## {category} ({timestamp})\n"
            
            # 添加元数据（如果有）
            if metadata:
                # 安全地序列化元数据，处理不可序列化的对象
                try:
                    metadata_str = json.dumps(metadata, ensure_ascii=False, indent=2)
                except (TypeError, ValueError):
                    # 如果无法直接序列化，尝试转换为可序列化的格式
                    safe_metadata = self._make_json_serializable(metadata)
                    metadata_str = json.dumps(safe_metadata, ensure_ascii=False, indent=2)
                new_entry += f"<!-- metadata: {metadata_str} -->\n"
                
            new_entry += f"{information}\n"
            
            # 保存更新的记忆
            with open(memory_file, 'w', encoding='utf-8') as f:
                f.write(existing_memory + new_entry)
                
            return True
            
        except Exception as e:
            # 记录错误但不抛出异常
            print(f"Failed to save memory: {str(e)}")
            return False
            
    async def search_memory(
        self, 
        query: str, 
        scope: Optional[MemoryScope] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆内容
        
        Args:
            query: 搜索关键词
            scope: 限定搜索范围（None表示搜索所有范围）
            category: 限定类别（None表示不限制）
            
        Returns:
            匹配的记忆条目列表
        """
        results = []
        
        # 确定要搜索的范围
        scopes_to_search = [scope] if scope else list(MemoryScope)
        
        for search_scope in scopes_to_search:
            memory_file = self.memory_files[search_scope]
            
            if not memory_file.exists():
                continue
                
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 简单的基于行的搜索（可以后续优化为更智能的搜索）
                entries = self._parse_memory_entries(content)
                
                for entry in entries:
                    # 检查类别匹配
                    if category and entry.get("category") != category:
                        continue
                        
                    # 检查内容匹配
                    if query.lower() in entry.get("content", "").lower():
                        entry["scope"] = search_scope.value
                        entry["file"] = str(memory_file)
                        results.append(entry)
                        
            except Exception:
                continue
                
        return results
        
    def _parse_memory_entries(self, content: str) -> List[Dict[str, Any]]:
        """解析记忆文件内容为结构化条目"""
        entries = []
        current_entry = None
        
        lines = content.split('\n')
        for line in lines:
            # 检测新条目开始
            if line.startswith("## "):
                if current_entry:
                    entries.append(current_entry)
                    
                # 解析标题行
                title_match = line[3:].strip()
                if '(' in title_match and ')' in title_match:
                    category = title_match[:title_match.find('(')].strip()
                    timestamp = title_match[title_match.find('(')+1:title_match.find(')')].strip()
                else:
                    category = title_match
                    timestamp = None
                    
                current_entry = {
                    "category": category,
                    "timestamp": timestamp,
                    "content": "",
                    "metadata": None
                }
                
            elif current_entry:
                # 检测元数据
                if line.strip().startswith("<!-- metadata:") and line.strip().endswith("-->"):
                    try:
                        metadata_str = line.strip()[14:-3].strip()
                        current_entry["metadata"] = json.loads(metadata_str)
                    except (json.JSONDecodeError, ValueError):
                        # 如果解析失败，将原始字符串保存
                        current_entry["metadata"] = {"_raw": metadata_str}
                else:
                    # 添加到内容
                    current_entry["content"] += line + "\n"
                    
        # 添加最后一个条目
        if current_entry:
            entries.append(current_entry)
            
        return entries
        
    def _make_json_serializable(self, obj: Any, visited: Optional[set] = None) -> Any:
        """将对象转换为可JSON序列化的格式，避免循环引用"""
        if visited is None:
            visited = set()
            
        # 检查循环引用
        obj_id = id(obj)
        if obj_id in visited:
            return f"<CircularReference: {obj.__class__.__name__}>"
            
        # 基本类型直接返回
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
            
        # 记录已访问的对象
        visited.add(obj_id)
        
        try:
            if isinstance(obj, dict):
                return {k: self._make_json_serializable(v, visited) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [self._make_json_serializable(item, visited) for item in obj]
            elif hasattr(obj, '__dict__'):
                # 处理自定义对象，转换为字典
                return {
                    '_type': obj.__class__.__name__,
                    '_data': self._make_json_serializable(obj.__dict__, visited)
                }
            elif hasattr(obj, '__str__'):
                # 对于其他有字符串表示的对象，使用其字符串形式
                return str(obj)
            else:
                # 无法处理的类型
                return f"<Unserializable: {type(obj).__name__}>"
        finally:
            # 清理已访问记录
            visited.discard(obj_id)
    
    def _get_relative_path(self, file_path: Path) -> str:
        """获取相对路径用于显示"""
        try:
            return str(file_path.relative_to(self.config.get_working_dir()))
        except ValueError:
            # 如果不是相对路径，返回绝对路径
            return str(file_path)
            
    async def clear_session_memory(self):
        """清除会话级记忆（用于新会话开始时）"""
        session_file = self.memory_files[MemoryScope.SESSION]
        if session_file.exists():
            try:
                session_file.unlink()
            except Exception:
                pass
                
    def get_memory_summary(self) -> Dict[str, Dict[str, Any]]:
        """获取记忆系统的摘要信息"""
        summary = {}
        
        for scope in MemoryScope:
            memory_file = self.memory_files[scope]
            
            if memory_file.exists():
                try:
                    stat = memory_file.stat()
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        entries = self._parse_memory_entries(content)
                        
                    summary[scope.value] = {
                        "file": str(memory_file),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "entries": len(entries),
                        "categories": list(set(e["category"] for e in entries))
                    }
                except Exception:
                    summary[scope.value] = {"error": "Failed to read"}
            else:
                summary[scope.value] = {"exists": False}
                
        return summary


class DatabaseMemoryTool(DatabaseTool):
    """
    记忆保存工具 - 完全对齐Gemini CLI的MemoryTool
    让Agent能够主动保存重要信息到长期记忆中
    """
    
    def __init__(self, memory_manager: DatabaseMemoryManager):
        super().__init__(
            name="save_memory",
            display_name="保存记忆",
            description="保存重要信息到长期记忆中，用于未来会话参考。支持数据库结构、查询模式、用户偏好等信息的存储。",
            parameter_schema={
                "type": "object",
                "properties": {
                    "information": {
                        "type": "string",
                        "description": "要保存的重要信息"
                    },
                    "category": {
                        "type": "string",
                        "description": "信息类别（如：数据库结构、查询模式、用户偏好、性能优化、错误处理等）",
                        "default": "general"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["global", "project", "session"],
                        "description": "记忆范围：global（全局）、project（项目）、session（会话）",
                        "default": "project"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "额外的元数据（如：数据库名称、表名、查询类型等）",
                        "additionalProperties": True
                    }
                },
                "required": ["information"]
            }
        )
        self.memory_manager = memory_manager
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        if not params.get("information"):
            return "信息内容不能为空"
            
        scope = params.get("scope", "project")
        if scope not in ["global", "project", "session"]:
            return f"无效的记忆范围: {scope}"
            
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取执行描述"""
        category = params.get("category", "general")
        scope = params.get("scope", "project")
        return f"保存{category}信息到{scope}级记忆"
        
    async def should_confirm_execute(self, params: Dict[str, Any], signal) -> bool:
        """记忆保存通常不需要确认"""
        return False
        
    async def execute(
        self, 
        params: Dict[str, Any], 
        signal,
        update_output: Optional[callable] = None
    ) -> ToolResult:
        """执行记忆保存"""
        information = params["information"]
        category = params.get("category", "general")
        scope_str = params.get("scope", "project")
        metadata = params.get("metadata")
        
        try:
            # 转换范围字符串为枚举
            scope = MemoryScope(scope_str)
            
            # 保存记忆
            success = await self.memory_manager.save_memory(
                information=information,
                category=category,
                scope=scope,
                metadata=metadata
            )
            
            if success:
                return ToolResult(
                    summary=f"已保存{scope.value}级记忆",
                    llm_content=f"信息已成功保存到{scope.value}级记忆中，类别：{category}",
                    return_display=f"✅ 记忆已保存\n范围：{scope.value}\n类别：{category}"
                )
            else:
                return ToolResult(
                    summary="记忆保存失败",
                    llm_content="保存记忆时出现错误",
                    return_display="❌ 记忆保存失败",
                    error="Failed to save memory"
                )
                
        except Exception as e:
            return ToolResult(
                summary="记忆保存出错",
                llm_content=f"保存记忆时出错：{str(e)}",
                return_display=f"❌ 错误：{str(e)}",
                error=str(e)
            )
"""
DirectoryListTool - 文件目录浏览工具
严格参考Gemini CLI的list_directory实现，提供安全的目录浏览能力
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class DirectoryListTool(DatabaseTool):
    """
    文件目录浏览工具
    让Agent能够安全地浏览文件系统，找到SQL脚本、CSV文件等
    完全参考Gemini CLI的安全设计和用户体验
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        super().__init__(
            name="list_directory",
            display_name=self._('dir_list_tool_name', default="目录浏览") if i18n else "目录浏览",
            description="List directory contents with safety checks and permission validation. Filter by pattern/extension. Sort by: name, size, modified time. Includes file metadata and recursive listing with depth control.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (absolute or relative to working directory)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional file pattern filter (e.g., '*.sql', '*.csv')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list subdirectories recursively",
                        "default": False
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum recursion depth (only applies if recursive=true)",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 2
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["name", "size", "modified"],
                        "description": "Sort results by name, size, or modification time",
                        "default": "name"
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Whether to show hidden files (starting with .)",
                        "default": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100
                    }
                },
                "required": ["path"]
            },
            is_output_markdown=True,
            can_update_output=False,
            should_summarize_display=False,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 动态检测系统并设置灵活的访问权限（与FileReadTool保持一致）
        default_paths = self._get_system_paths(config)
        self.allowed_paths = config.get("directory_allowed_paths", default_paths)
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        path = params.get("path", "")
        if not path:
            return self._('dir_list_path_empty', default="Directory path cannot be empty")
            
        # 处理相对路径
        try:
            resolved_path = self._resolve_path(path)
            if not self._is_path_allowed(resolved_path):
                return self._('dir_list_access_denied', default="Access denied: {path} is outside allowed directories", path=path)
        except Exception as e:
            return self._('dir_list_invalid_path', default="Invalid path: {error}", error=str(e))
            
        # 验证pattern（如果提供）
        pattern = params.get("pattern")
        if pattern:
            # 基本的模式验证，防止恶意模式
            if '..' in pattern or '/' in pattern or '\\' in pattern:
                return self._('dir_list_invalid_pattern', default="Invalid pattern: must not contain path separators")
                
        return None
    
    def _get_system_paths(self, config) -> list:
        """动态检测系统并返回合适的访问路径 - 真正的灵活性"""
        paths = []
        
        # 智能检测项目根目录（往上找到包含packages的目录）
        working_dir = Path(config.get_working_dir())
        current_dir = working_dir
        
        # 向上查找到项目根目录
        while current_dir.parent != current_dir:  # 没到根目录
            if (current_dir / 'packages').exists() or (current_dir / 'pyproject.toml').exists():
                paths.append(str(current_dir))
                break
            current_dir = current_dir.parent
        
        # 如果没找到项目根目录，至少包含工作目录
        paths.append(config.get_working_dir())
        
        # 用户主目录 - 跨平台通用
        home_dir = os.path.expanduser("~")
        if home_dir and os.path.exists(home_dir):
            paths.append(home_dir)
        
        # 根据系统平台动态添加根路径
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            # Windows: 动态检测所有可用驱动器
            import string
            for drive in string.ascii_uppercase:
                drive_path = f"{drive}:\\"
                if os.path.exists(drive_path):
                    paths.append(drive_path)
        
        elif system == "darwin":  # macOS
            paths.extend([
                "/",              # 根目录
                "/Users",         # 用户目录
                "/Applications",  # 应用程序
                "/Volumes",       # 挂载点
            ])
        
        elif system == "linux":
            paths.extend([
                "/",              # 根目录
                "/home",          # 用户目录
                "/mnt",           # 挂载点 (WSL等)
                "/media",         # 媒体挂载
                "/opt",           # 可选软件
                "/tmp",           # 临时目录
            ])
        
        else:
            # 未知系统，使用通用路径
            if os.path.exists("/"):
                paths.append("/")
            # 尝试检测常见挂载点
            for mount_point in ["/mnt", "/media", "/Volumes"]:
                if os.path.exists(mount_point):
                    paths.append(mount_point)
        
        # 过滤掉不存在的路径，保留真实可访问的
        return [p for p in paths if os.path.exists(p)]
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        path = params.get("path", "")
        pattern = params.get("pattern")
        recursive = params.get("recursive", False)
        
        desc = self._('dir_list_description', default="列出目录: {path}", path=path)
        if pattern:
            desc += self._('dir_list_pattern_suffix', default=" (匹配: {pattern})", pattern=pattern)
        if recursive:
            desc += self._('dir_list_recursive_suffix', default=" [递归]")
            
        return desc
        
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Union[bool, Any]:
        """目录浏览是安全操作，不需要确认"""
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行目录列表"""
        path = params.get("path", "")
        pattern = params.get("pattern")
        recursive = params.get("recursive", False)
        max_depth = params.get("max_depth", 2)
        sort_by = params.get("sort_by", "name")
        show_hidden = params.get("show_hidden", False)
        limit = params.get("limit", 100)
        
        try:
            # 解析路径
            resolved_path = self._resolve_path(path)
            
            # 安全检查
            if not self._is_path_allowed(resolved_path):
                allowed_paths_str = '\n'.join([f"  - {p}" for p in self.allowed_paths])
                error_msg = self._('dir_list_access_denied_detail', default="Access denied: {path} is outside allowed directories.\n\nAllowed directories:\n{dirs}\n\nPlease check the directory path format and try again with a path within the allowed directories.", path=path, dirs=allowed_paths_str)
                
                return ToolResult(
                    error=error_msg,
                    llm_content=error_msg
                )
                
            # 检查路径是否存在
            if not resolved_path.exists():
                return ToolResult(
                    error=self._('dir_list_not_found', default="Directory not found: {path}", path=path)
                )
                
            if not resolved_path.is_dir():
                return ToolResult(
                    error=self._('dir_list_not_directory', default="Path is not a directory: {path}", path=path)
                )
                
            # 收集文件和目录
            items = []
            if recursive:
                items = self._list_recursive(
                    resolved_path, pattern, max_depth, show_hidden, 0
                )
            else:
                items = self._list_directory(
                    resolved_path, pattern, show_hidden
                )
                
            # 排序
            items = self._sort_items(items, sort_by)
            
            # 限制数量
            total_items = len(items)
            if total_items > limit:
                items = items[:limit]
                truncated = True
            else:
                truncated = False
                
            # 格式化输出
            return self._format_result(
                resolved_path, items, total_items, truncated, recursive
            )
            
        except Exception as e:
            return ToolResult(
                error=self._('dir_list_failed', default="Failed to list directory: {error}", error=str(e))
            )
            
    def _resolve_path(self, path: str) -> Path:
        """解析路径，支持相对路径和绝对路径"""
        p = Path(path)
        
        # 如果是相对路径，基于工作目录解析
        if not p.is_absolute():
            working_dir = Path(self.config.get_working_dir())
            p = working_dir / p
            
        # 规范化路径（解析 .. 和 . 等）
        return p.resolve()
        
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许的目录内"""
        for allowed_path in self.allowed_paths:
            allowed = Path(allowed_path).resolve()
            try:
                # 检查是否是子路径
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
        
    def _list_directory(
        self, 
        path: Path, 
        pattern: Optional[str],
        show_hidden: bool
    ) -> List[Dict[str, Any]]:
        """列出单个目录内容"""
        items = []
        
        try:
            for item in path.iterdir():
                # 跳过隐藏文件（如果需要）
                if not show_hidden and item.name.startswith('.'):
                    continue
                    
                # 应用模式过滤
                if pattern and not self._match_pattern(item.name, pattern):
                    continue
                    
                items.append(self._get_item_info(item, path))
        except PermissionError:
            # 权限不足，静默跳过
            pass
            
        return items
        
    def _list_recursive(
        self,
        path: Path,
        pattern: Optional[str],
        max_depth: int,
        show_hidden: bool,
        current_depth: int
    ) -> List[Dict[str, Any]]:
        """递归列出目录内容"""
        if current_depth >= max_depth:
            return []
            
        items = []
        
        # 首先添加当前目录的内容
        items.extend(self._list_directory(path, pattern, show_hidden))
        
        # 然后递归子目录
        try:
            for item in path.iterdir():
                if item.is_dir():
                    # 跳过隐藏目录（如果需要）
                    if not show_hidden and item.name.startswith('.'):
                        continue
                        
                    sub_items = self._list_recursive(
                        item, pattern, max_depth, show_hidden, current_depth + 1
                    )
                    items.extend(sub_items)
        except PermissionError:
            pass
            
        return items
        
    def _get_item_info(self, item: Path, base_path: Path) -> Dict[str, Any]:
        """获取文件/目录信息"""
        try:
            stat = item.stat()
            
            # 计算相对路径
            try:
                relative_path = item.relative_to(base_path)
            except ValueError:
                relative_path = item
                
            return {
                "name": item.name,
                "path": str(item),
                "relative_path": str(relative_path),
                "type": "directory" if item.is_dir() else "file",
                "size": stat.st_size if item.is_file() else 0,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": item.suffix.lower() if item.is_file() else ""
            }
        except (OSError, PermissionError):
            # 无法获取状态，返回基本信息
            return {
                "name": item.name,
                "path": str(item),
                "type": "unknown",
                "size": 0,
                "modified": None,
                "extension": ""
            }
            
    def _match_pattern(self, name: str, pattern: str) -> bool:
        """简单的模式匹配（支持 * 通配符）"""
        import fnmatch
        return fnmatch.fnmatch(name.lower(), pattern.lower())
        
    def _sort_items(self, items: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        """排序项目"""
        if sort_by == "name":
            # 目录优先，然后按名称排序
            return sorted(items, key=lambda x: (x["type"] != "directory", x["name"].lower()))
        elif sort_by == "size":
            # 按大小降序排序
            return sorted(items, key=lambda x: -x["size"])
        elif sort_by == "modified":
            # 按修改时间降序排序（最新的在前）
            return sorted(
                items, 
                key=lambda x: x["modified"] if x["modified"] else "",
                reverse=True
            )
        return items
        
    def _format_result(
        self,
        base_path: Path,
        items: List[Dict[str, Any]],
        total_items: int,
        truncated: bool,
        recursive: bool
    ) -> ToolResult:
        """格式化结果输出"""
        # 统计信息
        dirs = [i for i in items if i["type"] == "directory"]
        files = [i for i in items if i["type"] == "file"]
        
        # 为LLM准备结构化数据
        llm_content = {
            "base_path": str(base_path),
            "total_items": total_items,
            "directories": len(dirs),
            "files": len(files),
            "items": items,
            "truncated": truncated
        }
        
        # 为显示准备格式化输出
        display_lines = [
            self._('dir_list_base_path', default="📁 {path}", path=base_path),
            self._('dir_list_summary', default="📊 {dirs} directories, {files} files", dirs=len(dirs), files=len(files))
        ]
        
        if truncated:
            display_lines.append(self._('dir_list_truncated', default="⚠️ Showing first {showing} of {total} items", showing=len(items), total=total_items))
            
        display_lines.append("")  # 空行
        
        # 格式化项目列表
        for item in items:
            if item["type"] == "directory":
                icon = "📁"
                size_str = ""
            else:
                icon = self._get_file_icon(item["extension"])
                size_str = f" ({self._format_size(item['size'])})"
                
            # 使用相对路径显示（如果是递归模式）
            name = item["relative_path"] if recursive else item["name"]
            display_lines.append(f"{icon} {name}{size_str}")
            
        summary = self._('dir_list_result_summary', default="列出 {path} 中的 {count} 个项目", path=base_path, count=len(items))
        if truncated:
            summary += self._('dir_list_total_suffix', default=" (共 {total} 个)", total=total_items)
            
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display="\n".join(display_lines)
        )
        
    def _get_file_icon(self, extension: str) -> str:
        """根据文件扩展名返回图标"""
        icon_map = {
            ".sql": "🗄️",
            ".csv": "📊",
            ".json": "📋",
            ".yaml": "⚙️",
            ".yml": "⚙️",
            ".txt": "📄",
            ".md": "📝",
            ".py": "🐍",
            ".js": "🟨",
            ".log": "📜",
            ".env": "🔐",
            ".xlsx": "📊",
            ".xls": "📊"
        }
        return icon_map.get(extension, "📄")
        
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
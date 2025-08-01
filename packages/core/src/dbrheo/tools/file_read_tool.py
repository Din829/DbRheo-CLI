"""
文件读取工具 - 让Agent能够读取SQL脚本、配置文件等
借鉴Gemini CLI的分页读取、多媒体支持等设计
"""

import os
import json
import yaml
import base64
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from ..types.file_types import FileFormat, FileAnalysisResult
from .base import DatabaseTool
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info


class FileReadTool(DatabaseTool):
    """
    增强的文件读取工具，支持：
    - SQL脚本、配置文件、CSV数据等文本文件
    - 分页读取大文件（借鉴Gemini CLI）
    - 图片和二进制文件的智能处理
    - 文件内容分析和结构提取
    """
    
    # 支持的文本文件扩展名
    TEXT_EXTENSIONS = {
        '.sql', '.json', '.yaml', '.yml', '.md', '.txt', 
        '.csv', '.tsv', '.ini', '.conf', '.config', '.env',
        '.xml', '.html', '.log', '.sh', '.py', '.js'
    }
    
    # 图片格式（借鉴Gemini CLI）
    IMAGE_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'
    }
    
    # 最大文件大小 (50MB for text, 10MB for images)
    MAX_TEXT_FILE_SIZE = 50 * 1024 * 1024
    MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024
    
    # 默认行数限制（借鉴Gemini CLI的2000行）
    DEFAULT_LINE_LIMIT = 2000
    MAX_LINE_LENGTH = 2000
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="read_file",
            display_name=self._('file_read_tool_name', default="文件读取") if i18n else "文件读取",
            description="Reads files with intelligent format detection and pagination support. When file not found: automatically lists directory contents, searches for similar filenames, and attempts path corrections. Provides comprehensive file analysis capabilities.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (auto-detected if not specified). Common: utf-8, cp932 (Japanese Windows), gbk (Chinese)",
                        "default": "auto"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Start reading from line N (0-based, for pagination)",
                        "minimum": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (default: 2000)",
                        "minimum": 1,
                        "maximum": 10000
                    },
                    "analyze": {
                        "type": "boolean",
                        "description": "Analyze file structure and content (for CSV/JSON)",
                        "default": False
                    }
                },
                "required": ["path"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 动态检测系统并设置灵活的访问权限
        default_paths = self._get_system_paths(config)
        self.allowed_paths = config.get("file_allowed_paths", default_paths)
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        path = params.get("path", "")
        if not path:
            return self._('file_read_path_empty', default="File path cannot be empty")
        
        # 必须是绝对路径（借鉴Gemini CLI）
        if not os.path.isabs(path):
            return self._('file_read_path_not_absolute', default="Path must be absolute")
        
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
        path = Path(params.get("path", ""))
        offset = params.get("offset", 0)
        limit = params.get("limit", self.DEFAULT_LINE_LIMIT)
        
        desc = self._('file_read_description', default="Read file: {filename}", filename=path.name)
        if offset > 0:
            desc += self._('file_read_offset_suffix', default=" (from line {line})", line=offset + 1)
        if limit < self.DEFAULT_LINE_LIMIT:
            desc += self._('file_read_limit_suffix', default=" (limit {limit} lines)", limit=limit)
        
        return desc
    
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Optional[Any]:
        """读取文件通常不需要确认"""
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行文件读取"""
        file_path = params.get("path", "")
        encoding_param = params.get("encoding", "auto")
        # 确保 offset 和 limit 是整数（Gemini API 可能传递字符串）
        offset = int(params.get("offset", 0)) if params.get("offset") is not None else 0
        limit = int(params.get("limit", self.DEFAULT_LINE_LIMIT)) if params.get("limit") is not None else self.DEFAULT_LINE_LIMIT
        analyze = bool(params.get("analyze", False))
        
        # 处理编码 - 支持自动检测
        if encoding_param == "auto":
            encoding = await self._detect_encoding(file_path)
        else:
            encoding = encoding_param
        
        try:
            # 规范化路径
            path = Path(file_path).resolve()
            
            # 安全检查：确保文件在允许的路径内
            if not self._is_path_allowed(path):
                allowed_paths_str = '\n'.join([f"  - {p}" for p in self.allowed_paths])
                error_msg = self._('file_read_access_denied', default="Access denied: {path} is outside allowed directories.\n\nAllowed directories:\n{dirs}\n\nPlease check the file path format and try again with a path within the allowed directories.", path=path, dirs=allowed_paths_str)
                
                return ToolResult(
                    error=error_msg,
                    llm_content=error_msg
                )
            
            # 检查文件是否存在
            if not path.exists():
                return ToolResult(
                    error=self._('file_read_not_found', default="File not found: {path}", path=path)
                )
                
            if not path.is_file():
                return ToolResult(
                    error=self._('file_read_not_file', default="Path is not a file: {path}", path=path)
                )
            
            # 检查文件大小
            file_size = path.stat().st_size
            max_size = self.MAX_TEXT_FILE_SIZE if not self._is_image(path) else self.MAX_IMAGE_FILE_SIZE
            if file_size > max_size:
                return ToolResult(
                    error=self._('file_read_too_large', default="File too large: {size} bytes (max: {max} bytes)", size=file_size, max=max_size)
                )
            
            # 智能文件类型检测（借鉴Gemini CLI）
            if self._is_image(path):
                return await self._read_image(path)
            elif self._is_binary(path):
                return self._handle_binary_file(path)
            
            # 分析文件（如果需要）
            analysis = None
            if analyze:
                analysis = await self._analyze_file(path)
            
            # 读取文件内容（支持分页）
            try:
                content, lines_read, has_more = await self._read_file_content(
                    path, encoding, offset, limit
                )
            except Exception as read_error:
                # 更友好的错误处理
                return ToolResult(
                    error=self._('file_read_failed', default="Failed to read file: {error}", error=str(read_error)),
                    llm_content=self._('file_read_failed_llm', default="Error reading {path}: {error}", path=path, error=str(read_error)),
                    return_display=self._('file_read_failed_display', default="❌ Failed to read file: {error}", error=str(read_error))
                )
            
            # 根据文件类型进行特殊处理
            if path.suffix.lower() == '.sql':
                return self._handle_sql_file(content, path, lines_read, has_more, analysis)
            elif path.suffix.lower() in ['.json']:
                return self._handle_json_file(content, path, lines_read, has_more, analysis)
            elif path.suffix.lower() in ['.yaml', '.yml']:
                return self._handle_yaml_file(content, path, lines_read, has_more, analysis)
            elif path.suffix.lower() in ['.csv', '.tsv']:
                return self._handle_csv_file(content, path, lines_read, has_more, analysis)
            else:
                # 通用文本文件处理
                return self._handle_text_file(content, path, lines_read, has_more, analysis, offset)
                
        except Exception as e:
            return ToolResult(
                error=f"Failed to read file: {str(e)}"
            )
    
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许的目录内"""
        for allowed_path in self.allowed_paths:
            allowed = Path(allowed_path).resolve()
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
    
    async def _detect_encoding(self, file_path: str) -> str:
        """自动检测文件编码"""
        try:
            # 使用新的编码检测工具
            from ..utils.encoding_utils import get_file_encoding_candidates
            candidates = get_file_encoding_candidates()
            
            # 读取文件前几KB进行检测
            path = Path(file_path)
            if path.exists() and path.is_file():
                with open(path, 'rb') as f:
                    sample = f.read(10240)  # 读取前10KB
                    
                # 尝试使用chardet（如果可用）
                try:
                    import chardet
                    result = chardet.detect(sample)
                    if result and result['encoding'] and result['confidence'] > 0.7:
                        detected = result['encoding'].lower()
                        # 使用 encoding_utils 的标准化功能
                        try:
                            from ..utils.encoding_utils import EncodingDetector
                            return EncodingDetector.normalize_encoding(detected)
                        except:
                            # 后备方案：简单的标准化
                            if detected in ['shift_jis', 'shift-jis']:
                                return 'shift_jis'
                            elif detected in ['euc-jp', 'euc_jp']:
                                return 'euc_jp'
                            elif detected in ['gb2312', 'gb18030']:
                                return 'gbk'
                            return detected
                except ImportError:
                    pass
                    
                # 如果chardet不可用或不确定，尝试候选编码
                for encoding in candidates[:5]:  # 只尝试前5个最可能的
                    try:
                        sample.decode(encoding)
                        return encoding
                    except:
                        continue
                        
        except Exception as e:
            if DebugLogger.should_log("DEBUG"):
                log_info("FileReadTool", f"编码检测失败: {str(e)}")
                
        # 默认使用系统编码
        try:
            from ..utils.encoding_utils import get_system_encoding
            return get_system_encoding()
        except:
            return "utf-8"
    
    def _is_image(self, path: Path) -> bool:
        """检查是否为图片文件"""
        return path.suffix.lower() in self.IMAGE_EXTENSIONS
    
    def _is_binary(self, path: Path) -> bool:
        """检查是否为二进制文件（借鉴Gemini CLI）"""
        if path.suffix.lower() in self.TEXT_EXTENSIONS:
            return False
        
        # 通过MIME类型判断
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type and mime_type.startswith('text/'):
            return False
        
        # 读取前4KB检查内容
        try:
            with open(path, 'rb') as f:
                chunk = f.read(4096)
                # 检查是否包含空字节
                if b'\x00' in chunk:
                    return True
                # 尝试解码为UTF-8
                try:
                    chunk.decode('utf-8')
                    return False
                except UnicodeDecodeError:
                    return True
        except:
            return True
    
    async def _read_image(self, path: Path) -> ToolResult:
        """读取图片文件（借鉴Gemini CLI）"""
        try:
            # 检查文件大小
            if path.stat().st_size > self.MAX_IMAGE_FILE_SIZE:
                return ToolResult(
                    error=f"Image file too large: {self._format_size(path.stat().st_size)} (max: {self._format_size(self.MAX_IMAGE_FILE_SIZE)})"
                )
            
            # 读取并转换为base64
            with open(path, 'rb') as f:
                image_data = f.read()
            
            base64_data = base64.b64encode(image_data).decode('utf-8')
            mime_type, _ = mimetypes.guess_type(str(path))
            
            return ToolResult(
                summary=self._('file_read_image_summary', default="Read image file: {filename}", filename=path.name),
                llm_content=self._('file_read_image_llm', default="[Image file: {filename}, type: {type}, size: {size}]", filename=path.name, type=mime_type, size=self._format_size(len(image_data))),
                return_display=self._('file_read_image_display', default="🖼️ {filename}\n📊 Type: {type}\n💾 Size: {size}", filename=path.name, type=mime_type, size=self._format_size(len(image_data)))
            )
        except Exception as e:
            return ToolResult(
                error=self._('file_read_image_failed', default="Failed to read image: {error}", error=str(e))
            )
    
    def _handle_binary_file(self, path: Path) -> ToolResult:
        """处理二进制文件"""
        file_size = path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(path))
        
        return ToolResult(
            summary=self._('file_read_binary_summary', default="Binary file: {filename}", filename=path.name),
            llm_content=self._('file_read_binary_llm', default="[Binary file: {filename}, type: {type}, size: {size} bytes]", filename=path.name, type=mime_type or 'unknown', size=file_size),
            return_display=self._('file_read_binary_display', default="🔒 Binary file\n📄 {filename}\n📊 Type: {type}\n💾 Size: {size}", filename=path.name, type=mime_type or self._('file_read_unknown_type', default='unknown'), size=self._format_size(file_size))
        )
    
    async def _read_file_content(self, path: Path, encoding: str, offset: int, limit: int) -> tuple[str, int, bool]:
        """异步读取文件内容，支持分页（借鉴Gemini CLI）"""
        import aiofiles
        
        lines_output = []
        lines_read = 0
        has_more = False
        total_lines = 0
        
        async with aiofiles.open(path, mode='r', encoding=encoding) as f:
            # 首先读取所有行以获取总行数（参考Gemini CLI的做法）
            # 对于大文件，这可能不是最优的，但能保证正确性
            all_lines = await f.readlines()
            total_lines = len(all_lines)
            
            # 参考Gemini CLI：保护offset不超过文件总行数
            actual_offset = min(offset, total_lines)
            
            # 计算实际的结束行
            end_line = min(actual_offset + limit, total_lines)
            
            # 获取需要的行
            selected_lines = all_lines[actual_offset:end_line]
            
            # 处理每一行
            for i, line in enumerate(selected_lines):
                # 行长度限制（借鉴Gemini CLI）
                if len(line) > self.MAX_LINE_LENGTH:
                    line = line[:self.MAX_LINE_LENGTH] + self._('file_read_line_truncated', default='... [truncated]\n')
                
                # 添加行号（cat -n 风格，但使用实际的行号）
                line_number = actual_offset + i + 1
                # 格式化行号，保证对齐（最多6位数）
                lines_output.append(f"{line_number:6d}\t{line}")
                lines_read += 1
            
            # 检查是否还有更多内容
            has_more = end_line < total_lines
        
        # 如果没有读取到任何内容（可能是offset超出范围），返回友好提示
        if not lines_output and offset >= total_lines:
            return self._('file_read_offset_out_of_range', default="[File only has {total} lines, but requested to start from line {line}]\n", total=total_lines, line=offset + 1), 0, False
        
        return ''.join(lines_output), lines_read, has_more
    
    def _handle_sql_file(self, content: str, path: Path, lines_read: int, has_more: bool, analysis: Optional[FileAnalysisResult]) -> ToolResult:
        """处理SQL文件"""
        # 分析SQL内容
        statement_count = content.count(';')
        
        # 智能检测SQL类型 - 使用正则表达式而非简单包含
        sql_types = []
        content_upper = content.upper()
        
        # 使用正则表达式检测SQL语句类型，避免误判
        import re
        sql_patterns = {
            'SELECT': r'\bSELECT\s+',
            'INSERT': r'\bINSERT\s+INTO\s+',
            'UPDATE': r'\bUPDATE\s+',
            'DELETE': r'\bDELETE\s+FROM\s+',
            'CREATE': r'\bCREATE\s+(TABLE|INDEX|VIEW|DATABASE)\s+',
            'ALTER': r'\bALTER\s+(TABLE|INDEX|VIEW)\s+',
            'DROP': r'\bDROP\s+(TABLE|INDEX|VIEW|DATABASE)\s+'
        }
        
        for sql_type, pattern in sql_patterns.items():
            if re.search(pattern, content_upper):
                sql_types.append(sql_type)
        
        summary = self._('file_read_sql_summary', default="Read SQL script: {filename} ({lines} lines)", filename=path.name, lines=lines_read)
        if has_more:
            summary += self._('file_read_partial_suffix', default=" [partial content]")
        
        llm_content = self._('file_read_sql_content', default="SQL脚本内容:\n\n{content}", content=content)
        if has_more:
            llm_content += self._('file_read_more_content', default="\n\n[文件还有更多内容，使用offset和limit参数分页读取]")
        
        display_lines = [
            f"📄 {path.name}",
            self._('file_read_sql_statements', default="📊 Statements: ~{count}", count=statement_count),
            self._('file_read_sql_types', default="📝 Types: {types}", types=', '.join(sql_types) if sql_types else self._('file_read_unknown', default='unknown')),
            self._('file_read_lines_read', default="📏 Lines read: {lines}", lines=lines_read)
        ]
        
        if has_more:
            display_lines.append(self._('file_read_has_more', default="⚠️ File has more content"))
        
        if analysis:
            display_lines.append(self._('file_read_file_size', default="💾 File size: {size}", size=self._format_size(analysis.file_size)))
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display="\n".join(display_lines)
        )
    
    def _handle_json_file(self, content: str, path: Path, lines_read: int, has_more: bool, analysis: Optional[FileAnalysisResult]) -> ToolResult:
        """处理JSON文件"""
        try:
            # 如果内容被截断，不尝试解析
            if has_more:
                return ToolResult(
                    summary=self._('file_read_json_partial', default="Read JSON file: {filename} ({lines} lines) [partial content]", filename=path.name, lines=lines_read),
                    llm_content=self._('file_read_json_partial_llm', default="JSON file partial content:\n\n{content}\n\n[File truncated, complete parsing requires reading all content]", content=content),
                    return_display=self._('file_read_json_partial_display', default="📄 {filename}\n📏 Lines read: {lines}\n⚠️ Content truncated, cannot parse structure", filename=path.name, lines=lines_read)
                )
            
            # 清理行号前缀（更灵活的处理）
            clean_content = '\n'.join(
                line.split('\t', 1)[1] if '\t' in line else line 
                for line in content.split('\n') if line.strip()
            )
            data = json.loads(clean_content)
            
            # 生成结构摘要
            def get_structure(obj, level=0):
                if level > 2:  # 限制深度
                    return "..."
                if isinstance(obj, dict):
                    return {k: get_structure(v, level+1) for k, v in list(obj.items())[:5]}
                elif isinstance(obj, list) and obj:
                    return f"Array[{len(obj)}]" if len(obj) > 1 else [get_structure(obj[0], level+1)]
                else:
                    return type(obj).__name__
            
            structure = get_structure(data)
            
            return ToolResult(
                summary=self._('file_read_json_summary', default="Read JSON file: {filename}", filename=path.name),
                llm_content=self._('file_read_json_llm', default="JSON content:\n\n{content}", content=json.dumps(data, indent=2, ensure_ascii=False)),
                return_display=self._('file_read_json_display', default="📄 {filename}\n📊 Structure: {structure}...\n📏 Lines: {lines}", filename=path.name, structure=json.dumps(structure, indent=2, ensure_ascii=False)[:200], lines=lines_read)
            )
        except json.JSONDecodeError as e:
            return ToolResult(
                summary=self._('file_read_json_invalid', default="Invalid JSON file"),
                llm_content=self._('file_read_json_error_llm', default="JSON parse error {filename}: {error}\n\nContent:\n{content}", filename=path.name, error=str(e), content=content),
                return_display=self._('file_read_json_error_display', default="❌ JSON parse error: {error}", error=str(e))
            )
    
    def _handle_yaml_file(self, content: str, path: Path, lines_read: int, has_more: bool, analysis: Optional[FileAnalysisResult]) -> ToolResult:
        """处理YAML文件"""
        try:
            # 如果内容被截断，不尝试解析
            if has_more:
                return ToolResult(
                    summary=self._('file_read_yaml_partial', default="Read YAML file: {filename} ({lines} lines) [partial content]", filename=path.name, lines=lines_read),
                    llm_content=self._('file_read_yaml_partial_llm', default="YAML file partial content:\n\n{content}\n\n[File truncated, complete parsing requires reading all content]", content=content),
                    return_display=self._('file_read_yaml_partial_display', default="📄 {filename}\n📏 Lines read: {lines}\n⚠️ Content truncated, cannot parse structure", filename=path.name, lines=lines_read)
                )
            
            # 移除行号后解析（更健壮的处理）
            clean_content = '\n'.join(
                line.split('\t', 1)[1] if '\t' in line else line 
                for line in content.split('\n')
            )
            data = yaml.safe_load(clean_content)
            
            keys_info = self._('file_read_yaml_unknown_structure', default="Unknown structure")
            if isinstance(data, dict):
                keys_info = self._('file_read_yaml_top_keys', default="Top keys: {keys}", keys=', '.join(list(data.keys())[:10]))
                if len(data.keys()) > 10:
                    keys_info += self._('file_read_yaml_more_keys', default=" ... (total {count})", count=len(data.keys()))
            elif isinstance(data, list):
                keys_info = self._('file_read_yaml_array', default="Array with {count} elements", count=len(data))
            
            return ToolResult(
                summary=self._('file_read_yaml_summary', default="Read YAML config file: {filename}", filename=path.name),
                llm_content=self._('file_read_yaml_llm', default="YAML content:\n\n{content}", content=content),
                return_display=self._('file_read_yaml_display', default="📄 {filename}\n📊 {keys_info}\n📏 行数: {lines}", filename=path.name, keys_info=keys_info, lines=lines_read)
            )
        except yaml.YAMLError as e:
            return ToolResult(
                summary=self._('file_read_yaml_invalid', default="Invalid YAML file"),
                llm_content=self._('file_read_yaml_error_llm', default="YAML parse error {filename}: {error}\n\nContent:\n{content}", filename=path.name, error=str(e), content=content),
                return_display=self._('file_read_yaml_error_display', default="❌ YAML parse error: {error}", error=str(e))
            )
    
    def _handle_csv_file(self, content: str, path: Path, lines_read: int, has_more: bool, analysis: Optional[FileAnalysisResult]) -> ToolResult:
        """处理CSV文件"""
        lines = content.strip().split('\n')
        
        if lines:
            # 提取表头（第一行，去除行号）
            header_line = lines[0].split('\t', 1)[1] if '\t' in lines[0] else lines[0]
            # 智能检测分隔符
            delimiter = '\t' if '\t' in header_line else ','
            headers = [h.strip() for h in header_line.split(delimiter)]
            
            row_count = lines_read - 1  # 减去表头
            
            # 分析数据样本
            sample_rows = []
            for line in lines[1:6]:  # 最多5行样本
                if '\t' in line:
                    line = line.split('\t', 1)[1]
                sample_rows.append(line.split(delimiter))
            
            summary = self._('file_read_csv_summary', default="Read CSV file: {filename} ({rows} rows data)", filename=path.name, rows=row_count)
            if has_more:
                summary += self._('file_read_partial_suffix', default=" [partial content]")
            
            llm_content = self._('file_read_csv_llm', default="CSV file content:\n\n{content}", content=content)
            if has_more:
                llm_content += self._('file_read_more_data_hint', default="\n\n[File has more data, use offset and limit parameters for pagination]")
            
            display_lines = [
                f"📄 {path.name}",
                self._('file_read_csv_columns', default="📊 Columns: {count}", count=len(headers)),
                self._('file_read_csv_headers', default="📋 Headers: {headers}{more}", headers=', '.join(headers[:5]), more='...' if len(headers) > 5 else ''),
                self._('file_read_csv_rows', default="📏 Data rows: {count}", count=row_count)
            ]
            
            if has_more:
                display_lines.append(self._('file_read_more_data', default="⚠️ File has more data"))
            
            if analysis:
                display_lines.append(self._('file_read_file_size', default="💾 File size: {size}", size=self._format_size(analysis.file_size)))
            
            return ToolResult(
                summary=summary,
                llm_content=llm_content,
                return_display="\n".join(display_lines)
            )
        else:
            return ToolResult(
                summary=self._('file_read_csv_empty', default="Empty CSV file"),
                llm_content=self._('file_read_csv_empty_llm', default="Empty CSV file: {filename}", filename=path.name),
                return_display=self._('file_read_csv_empty_display', default="📄 Empty CSV file")
            )
    
    def _handle_text_file(self, content: str, path: Path, lines_read: int, has_more: bool, analysis: Optional[FileAnalysisResult], offset: int = 0) -> ToolResult:
        """处理通用文本文件"""
        # 更灵活的摘要生成
        summary_parts = [self._('file_read_text_read', default="Read {filename}", filename=path.name)]
        if offset > 0:
            summary_parts.append(self._('file_read_text_from_line', default="from line {line}", line=offset + 1))
        summary_parts.append(self._('file_read_text_lines', default="{lines} lines", lines=lines_read))
        if has_more:
            summary_parts.append(self._('file_read_text_partial', default="partial content"))
        summary = ", ".join(summary_parts)
        
        # 改进的LLM内容格式
        llm_content = content
        if offset > 0 or has_more:
            # 添加上下文信息
            context_info = []
            if offset > 0:
                context_info.append(self._('file_read_from_line_context', default="from line {line}", line=offset + 1))
            if has_more:
                context_info.append(self._('file_read_has_more_context', default="file has more content"))
            llm_content = self._('file_read_partial_content', default="[File partial content: {context}]\n\n{content}", context=', '.join(context_info), content=content)
            if has_more:
                llm_content += self._('file_read_use_pagination', default="\n[Use offset and limit parameters to read more content]")
        
        # 改进的显示内容
        display_lines = [
            f"📄 {path.name}"
        ]
        
        if offset > 0:
            display_lines.append(self._('file_read_start_from', default="📖 Start from line {line}", line=offset + 1))
        
        display_lines.append(self._('file_read_lines_count', default="📏 Read {lines} lines", lines=lines_read))
        
        if has_more:
            display_lines.append(self._('file_read_has_more', default="⚠️ File has more content"))
        
        if analysis:
            display_lines.append(self._('file_read_file_size', default="💾 File size: {size}", size=self._format_size(analysis.file_size)))
            if analysis.detected_encoding:
                display_lines.append(self._('file_read_encoding', default="🔤 Encoding: {encoding}", encoding=analysis.detected_encoding))
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display="\n".join(display_lines)
        )
    
    async def _analyze_file(self, path: Path) -> FileAnalysisResult:
        """分析文件结构和内容"""
        import aiofiles
        
        # chardet是可选依赖，优雅降级
        try:
            import chardet
        except ImportError:
            chardet = None
        
        result = FileAnalysisResult(
            file_path=str(path),
            file_size=path.stat().st_size
        )
        
        # 检测编码 - 只有chardet可用时才检测
        if chardet:
            try:
                with open(path, 'rb') as f:
                    raw_data = f.read(10000)  # 读取前10KB用于编码检测
                    detected = chardet.detect(raw_data)
                    result.detected_encoding = detected.get('encoding', 'unknown')
            except:
                pass
        else:
            result.detected_encoding = 'utf-8'  # 默认假设UTF-8
        
        # 检测格式
        ext = path.suffix.lower()
        if ext == '.csv':
            result.detected_format = FileFormat.CSV
            # TODO: 分析CSV结构
        elif ext == '.json':
            result.detected_format = FileFormat.JSON
        elif ext in ['.yaml', '.yml']:
            result.detected_format = FileFormat.YAML
        elif ext == '.sql':
            result.detected_format = FileFormat.SQL
        
        return result
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
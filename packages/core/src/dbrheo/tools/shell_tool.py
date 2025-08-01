"""
ShellTool - Shell命令执行工具
完全对标Gemini CLI实现，为数据库管理提供系统层操作能力
设计原则：最小侵入性、参考最佳实践、解决真实痛点、保持灵活性
"""

import os
import sys
import platform
import asyncio
import subprocess
import tempfile
import shutil
import re
import time
from typing import Dict, Any, Optional, Union, Set, List
from pathlib import Path
from ..types.tool_types import ToolResult, DatabaseConfirmationDetails
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info


class ShellExecuteConfirmationDetails(DatabaseConfirmationDetails):
    """Shell执行确认详情 - 扩展现有确认机制"""
    
    def __init__(
        self, 
        command: str, 
        root_command: str, 
        risk_level: str = "LOW",
        reason: Optional[str] = None,
        working_directory: Optional[str] = None
    ):
        super().__init__(
            type="shell_execute",
            title="确认执行Shell命令"
        )
        self.command = command
        self.root_command = root_command 
        self.risk_level = risk_level
        self.reason = reason
        self.working_directory = working_directory


class ShellTool(DatabaseTool):
    """
    Shell命令执行工具 - 数据库管理的系统层操作
    
    核心逻辑完全对标Gemini CLI的shell工具实现，提供：
    - 跨平台命令执行（Windows/Unix统一接口）
    - 多层安全防护（命令解析、白名单学习、黑名单过滤）
    - 流式输出和实时进度更新
    - 优雅的进程管理和信号处理
    - 数据库管理场景优化
    
    设计原则遵循：
    - 最小侵入性：继承DatabaseTool基类，复用现有架构
    - 参考最佳实践：完全对标Gemini CLI的成熟实现
    - 解决真实痛点：数据库配置、日志分析、备份操作、系统监控
    - 保持灵活性：避免硬编码，支持配置驱动的安全策略
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        # 从配置获取安全策略（避免硬编码）
        self.whitelist: Set[str] = set(config.get("shell_whitelist", []))
        self.blacklist: Set[str] = set(config.get("shell_blacklist", [
            "rm", "sudo", "chmod", "mkfs", "format", "fdisk", "dd"
        ]))
        
        # 数据库相关命令通常安全性较高（减少确认频率）
        self.db_commands: Set[str] = set(config.get("shell_db_commands", [
            "mysql", "psql", "sqlite3", "mysqldump", "pg_dump", "mongodump",
            "redis-cli", "influx", "cqlsh"
        ]))
        
        # 支持的语言配置（灵活扩展）
        supported_platforms = ["Windows", "Linux", "macOS"] if platform.system() in ["Windows", "Linux", "Darwin"] else [platform.system()]
        
        super().__init__(
            name="shell_execute", 
            display_name=self._('shell_tool_name', default="Shell执行器") if i18n else "Shell执行器",
            description=f"Executes shell commands with cross-platform compatibility and intelligent error handling. Automatically adapts Windows/Unix syntax differences, provides real-time output, and implements comprehensive security controls for safe system operations.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute. Supports complex commands with pipes, redirects, and chains."
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory (optional, relative to project root). For safety, absolute paths are not allowed."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30, max: 300)",
                        "minimum": 1,
                        "maximum": 300,
                        "default": 30
                    },
                    "description": {
                        "type": "string", 
                        "description": "Optional description of what this command does (user-friendly)"
                    }
                },
                "required": ["command"]
            },
            is_output_markdown=True,    # 支持代码块和格式化输出
            can_update_output=True,     # 支持流式输出
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 智能动态输出限制 - 不再硬编码，确保灵活性
        # 默认100MB，但可以通过多种方式动态调整
        default_limit = 100 * 1024 * 1024  # 100MB 
        
        # 支持环境变量覆盖
        env_limit = os.environ.get('DBRHEO_SHELL_MAX_OUTPUT')
        if env_limit:
            if env_limit.upper() == 'UNLIMITED':
                default_limit = float('inf')  # 无限制模式
            else:
                try:
                    default_limit = int(env_limit)
                except ValueError:
                    pass
        
        self.max_output_size = config.get("shell_max_output", default_limit)
        
        # 记录配置以便调试
        if DebugLogger.should_log("DEBUG"):
            limit_desc = "unlimited" if self.max_output_size == float('inf') else f"{self.max_output_size:,} bytes"
            log_info("ShellTool", f"Output limit set to: {limit_desc}")
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """参数验证 - 参考Gemini CLI的验证逻辑"""
        command = params.get("command", "").strip()
        if not command:
            return self._('shell_command_empty', default="命令不能为空")
            
        # 检查命令替换（安全防护）
        if "$(" in command:
            return self._('shell_command_substitution', default="出于安全考虑，不允许使用 $() 命令替换")
            
        # 验证工作目录
        working_dir = params.get("working_directory")
        if working_dir:
            if os.path.isabs(working_dir):
                return self._('shell_absolute_path', default="工作目录不能是绝对路径，必须相对于项目根目录")
                
            # 检查目录是否存在
            try:
                project_root = Path.cwd()
                target_dir = project_root / working_dir
                if not target_dir.exists():
                    return self._('shell_dir_not_exist', default="目录不存在: {dir}", dir=working_dir)
                if not target_dir.is_dir():
                    return self._('shell_path_not_dir', default="路径不是目录: {dir}", dir=working_dir)
            except Exception as e:
                return self._('shell_dir_validation_failed', default="目录验证失败: {error}", error=str(e))
                
        # 验证超时参数
        timeout = params.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 300:
            return self._('shell_invalid_timeout', default="超时时间必须在1-300秒之间")
            
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取执行描述"""
        command = params.get("command", "")
        description = params.get("description")
        
        if description:
            return self._('shell_desc_with_description', default="执行Shell命令: {desc}", desc=description)
        else:
            # 智能生成描述
            command_preview = command[:50]
            if len(command) > 50:
                command_preview += "..."
            return self._('shell_desc_with_command', default="执行Shell命令: {cmd}", cmd=command_preview)
    
    def _decode_output(self, byte_data: bytes) -> str:
        """智能编码检测和解码 - 适应各种环境"""
        if not byte_data:
            return ""
            
        # 使用新的智能编码检测
        try:
            from ..utils.encoding_utils import smart_decode
            decoded, encoding = smart_decode(byte_data, context='shell')
            if DebugLogger.should_log("DEBUG"):
                log_info("ShellTool", self._('shell_decode_success', default="使用编码 {encoding} 成功解码输出", encoding=encoding))
            return decoded
        except ImportError:
            # 如果新模块不可用，使用原有逻辑作为后备
            pass
            
        # 后备方案：原有的编码尝试逻辑
        encodings = ['utf-8', 'gbk', 'cp1252', 'latin-1', 'ascii']
        
        # Windows系统优先尝试GBK
        if platform.system() == "Windows":
            encodings = ['utf-8', 'gbk', 'cp936', 'cp1252', 'latin-1']
            
        for encoding in encodings:
            try:
                return byte_data.decode(encoding)
            except UnicodeDecodeError:
                continue
                
        # 如果所有编码都失败，使用utf-8并替换错误字符
        # 但保留尽可能多的信息
        try:
            return byte_data.decode('utf-8', errors='backslashreplace')
        except:
            # 最后的fallback：使用latin-1（永不失败）
            return byte_data.decode('latin-1')
            
    def _get_command_root(self, command: str) -> Optional[str]:
        """
        提取命令根 - 完全对标Gemini CLI的算法
        智能解析复杂命令字符串，提取核心命令用于安全检查
        """
        if not command:
            return None
            
        # 移除分组操作符和多余空白
        cleaned = command.strip().replace("()", "").replace("{}", "")
        
        # 按操作符分割链式命令，取第一个命令
        chain_parts = re.split(r'&&|\|\||\||;', cleaned)
        if not chain_parts or not chain_parts[0]:
            return None
            
        first_command = chain_parts[0].strip()
        
        # 从第一个命令中提取命令名（按空白符分割，取第一个单词）
        command_words = first_command.split()
        if not command_words:
            return None
            
        command_part = command_words[0]
        
        # 处理路径分隔符，取最后部分（命令名）
        if '/' in command_part:
            command_part = command_part.split('/')[-1]
        if '\\' in command_part:
            command_part = command_part.split('\\')[-1]
            
        return command_part if command_part else None
        
    def _is_command_allowed(self, command: str) -> Dict[str, Any]:
        """
        命令安全检查 - 参考Gemini CLI的多层验证逻辑
        返回检查结果和原因
        """
        # 1. 禁止命令替换（防注入）
        if "$(" in command:
            return {
                "allowed": False,
                "reason": self._('shell_command_substitution_reason', default="出于安全考虑，不允许使用 $() 命令替换")
            }
            
        # 2. 分割链式命令并逐一验证
        chain_commands = re.split(r'&&|\|\||\||;', command)
        
        for cmd in chain_commands:
            cmd = cmd.strip()
            if not cmd:
                continue
                
            root_command = self._get_command_root(cmd)
            if not root_command:
                continue
                
            # 3. 黑名单检查（优先级最高）
            if self._is_prefixed_by_any(root_command, self.blacklist):
                return {
                    "allowed": False,
                    "reason": self._('shell_command_blacklisted', default="命令 '{command}' 被配置禁止执行", command=root_command)
                }
                
            # 4. 检查是否需要严格白名单模式
            strict_mode = self.config.get("shell_strict_whitelist", False)
            if strict_mode:
                if not self._is_prefixed_by_any(root_command, self.whitelist):
                    return {
                        "allowed": False,
                        "reason": self._('shell_command_not_whitelisted', default="严格模式下，命令 '{command}' 不在允许列表中", command=root_command)
                    }
                    
        return {"allowed": True}
        
    def _is_prefixed_by_any(self, command: str, prefixes: Set[str]) -> bool:
        """检查命令是否匹配任一前缀 - 参考Gemini CLI的精确匹配"""
        for prefix in prefixes:
            if self._is_prefixed_by(command, prefix):
                return True
        return False
        
    def _is_prefixed_by(self, command: str, prefix: str) -> bool:
        """精确前缀匹配 - 避免部分匹配问题"""
        if not command.startswith(prefix):
            return False
        # 确保是完整词匹配（后面是空格或命令结束）
        return len(command) == len(prefix) or command[len(prefix)] == ' '
        
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """
        智能确认机制 - 参考Gemini CLI的学习策略
        基于用户偏好和命令类型的智能确认
        """
        command = params.get("command", "").strip()
        working_dir = params.get("working_directory")
        
        # 参数验证失败时跳过确认（执行时会立即失败）
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return False
            
        # 安全检查
        security_check = self._is_command_allowed(command)
        if not security_check["allowed"]:
            return ShellExecuteConfirmationDetails(
                command=command,
                root_command=self._get_command_root(command) or "unknown",
                risk_level="HIGH",
                reason=security_check["reason"],
                working_directory=working_dir
            )
            
        root_command = self._get_command_root(command)
        if not root_command:
            return False
            
        # 白名单检查（用户已信任的命令）
        if root_command in self.whitelist:
            return False
            
        # 数据库相关命令降低确认频率
        if root_command in self.db_commands:
            return ShellExecuteConfirmationDetails(
                command=command,
                root_command=root_command,
                risk_level="MEDIUM",
                reason=self._('shell_db_command_reason', default="数据库管理命令，通常安全"),
                working_directory=working_dir
            )
            
        # 常见安全命令
        safe_commands = {"ls", "pwd", "cat", "head", "tail", "grep", "find", "ps", "df", "du", "whoami"}
        if root_command in safe_commands:
            return ShellExecuteConfirmationDetails(
                command=command,
                root_command=root_command,
                risk_level="LOW",
                reason=self._('shell_safe_command_reason', default="常见的只读系统命令"),
                working_directory=working_dir
            )
            
        # 其他命令需要确认
        return ShellExecuteConfirmationDetails(
            command=command,
            root_command=root_command,
            risk_level="MEDIUM",
            reason=self._('shell_needs_confirmation_reason', default="需要用户确认的系统命令"),
            working_directory=working_dir
        )
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """
        执行Shell命令 - 核心逻辑完全对标Gemini CLI
        提供跨平台、安全、流式的命令执行体验
        """
        command = params.get("command", "").strip()
        working_dir = params.get("working_directory", ".")
        timeout = params.get("timeout", 30)
        description = params.get("description", "")
        
        if update_output:
            desc_text = f": {description}" if description else ""
            update_output(self._('shell_executing', default="🔧 执行Shell命令{desc}\n```bash\n{command}\n```", desc=desc_text, command=command))
            
        try:
            # 最终安全检查
            security_check = self._is_command_allowed(command)
            if not security_check["allowed"]:
                return ToolResult(
                    error=security_check["reason"],
                    summary=self._('shell_blocked_summary', default="命令被安全策略阻止"),
                    return_display=self._('shell_security_check_failed', default="❌ 安全检查失败: {reason}", reason=security_check['reason'])
                )
                
            # 准备执行环境
            project_root = Path.cwd()
            exec_dir = project_root / working_dir if working_dir != "." else project_root
            
            # 执行命令
            result = await self._execute_command(
                command, exec_dir, timeout, update_output, signal
            )
            
            # 格式化结果
            return self._format_result(command, working_dir, result)
            
        except Exception as e:
            error_msg = self._('shell_execution_exception', default="Shell命令执行异常: {error}", error=str(e))
            return ToolResult(
                error=error_msg,
                summary=self._('shell_failed_summary', default="执行失败"),
                return_display=self._('shell_failed_display', default="❌ 执行失败\n\n{error}", error=error_msg)
            )
            
    async def _execute_command(
        self, 
        command: str, 
        working_dir: Path, 
        timeout: int,
        update_output: Optional[Any],
        signal: AbortSignal
    ) -> Dict[str, Any]:
        """
        核心命令执行逻辑 - 完全对标Gemini CLI实现
        """
        # 跨平台命令包装
        is_windows = platform.system() == "Windows"
        if is_windows:
            cmd_args = ["cmd.exe", "/c", command]
        else:
            cmd_args = ["bash", "-c", command]
            
        stdout = ""
        stderr = ""
        start_time = time.time()
        process = None
        exited = False
        exit_code = None
        
        try:
            # 创建进程
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=str(working_dir)
            )
            
            # 流式输出处理
            async def stream_output():
                nonlocal stdout, stderr, exited
                last_update_time = time.time()
                
                while not exited and process and process.returncode is None:
                    try:
                        # 读取stdout
                        if process.stdout:
                            try:
                                chunk = await asyncio.wait_for(
                                    process.stdout.read(1024), 
                                    timeout=0.1
                                )
                                if chunk:
                                    # 智能编码检测 - 适应不同环境
                                    text = self._decode_output(chunk)
                                    stdout += text
                                    
                                    # 节流更新（1秒间隔）
                                    if update_output and time.time() - last_update_time > 1.0:
                                        update_output(self._('shell_stream_output', default="📤 输出:\n```\n{text}\n```", text=text))
                                        last_update_time = time.time()
                            except asyncio.TimeoutError:
                                pass
                                
                        # 读取stderr
                        if process.stderr:
                            try:
                                chunk = await asyncio.wait_for(
                                    process.stderr.read(1024), 
                                    timeout=0.1
                                )
                                if chunk:
                                    # 智能编码检测 - 适应不同环境
                                    text = self._decode_output(chunk)
                                    stderr += text
                                    
                                    if update_output and time.time() - last_update_time > 1.0:
                                        update_output(self._('shell_stream_error', default="📤 错误输出:\n```\n{text}\n```", text=text))
                                        last_update_time = time.time()
                            except asyncio.TimeoutError:
                                pass
                                
                        await asyncio.sleep(0.1)
                        
                    except Exception:
                        break
                        
            # 启动流式输出任务
            stream_task = asyncio.create_task(stream_output())
            
            # 等待进程完成或超时
            try:
                exit_code = await asyncio.wait_for(process.wait(), timeout=timeout)
                exited = True
            except asyncio.TimeoutError:
                exited = True
                # 优雅终止进程
                if process:
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        if process:
                            process.kill()
                            
                return {
                    "success": False,
                    "stdout": stdout,
                    "stderr": stderr + "\n[" + self._('shell_timeout_message', default="执行超时 {timeout}秒", timeout=timeout) + "]",
                    "exit_code": -1,
                    "execution_time": timeout,
                    "stdout_truncated": False,
                    "stderr_truncated": False
                }
            finally:
                stream_task.cancel()
                
            # 确保所有输出都被读取
            if process.stdout:
                remaining_stdout = await process.stdout.read()
                if remaining_stdout:
                    stdout += self._decode_output(remaining_stdout)
                    
            if process.stderr:
                remaining_stderr = await process.stderr.read()
                if remaining_stderr:
                    stderr += self._decode_output(remaining_stderr)
                    
            execution_time = time.time() - start_time
            
            # 智能输出处理 - 避免恶性截断，支持无限制模式
            stdout_truncated = False
            stderr_truncated = False
            
            # 无限制模式：完全不截断
            if self.max_output_size == float('inf'):
                pass  # 保留完整输出
            else:
                if len(stdout) > self.max_output_size:
                    # 保留关键信息：开头和结尾各保留40%
                    keep_size = int(self.max_output_size * 0.4)
                    stdout_start = stdout[:keep_size]
                    stdout_end = stdout[-keep_size:]
                    total_lines = stdout.count('\n') + 1
                    truncated_lines = stdout[keep_size:-keep_size].count('\n') + 1
                    stdout = f"{stdout_start}\n\n... [" + self._('shell_truncated_lines', default="中间{truncated}行被省略，共{total}行", truncated=truncated_lines, total=total_lines) + "] ...\n\n{stdout_end}"
                    stdout_truncated = True
                    
                if len(stderr) > self.max_output_size:
                    # 错误信息更重要，保留更多内容
                    keep_size = int(self.max_output_size * 0.6)
                    stderr_start = stderr[:keep_size] 
                    stderr_end = stderr[-keep_size:]
                    stderr = f"{stderr_start}\n\n... [" + self._('shell_stderr_truncated', default="错误输出被部分省略") + "] ...\n\n{stderr_end}"
                    stderr_truncated = True
                
            return {
                "success": exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "execution_time": execution_time,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated
            }
            
        except Exception as e:
            return {
                "success": False,
                "stdout": stdout,
                "stderr": stderr + "\n[" + self._('shell_execution_error', default="执行异常: {error}", error=str(e)) + "]",
                "exit_code": -1,
                "execution_time": time.time() - start_time,
                "stdout_truncated": False,
                "stderr_truncated": False
            }
            
    def _format_result(self, command: str, working_dir: str, result: Dict[str, Any]) -> ToolResult:
        """格式化执行结果 - 确保Agent能收到原生错误信息进行智能重试"""
        
        # 构建详细的LLM内容 - Agent看到的原生信息
        current_platform = platform.system()
        shell_env = "cmd.exe" if current_platform == "Windows" else "bash"
        
        # 构建清晰的Agent内容 - 确保完整传递
        status_icon = "✅" if result["success"] else "❌"
        status_text = "executed successfully" if result["success"] else "failed"
        
        llm_content_parts = [
            f"{status_icon} Shell command {status_text}:",
            f"Command: {command}",
            f"Exit Code: {result['exit_code']}",
            f"Execution Time: {result['execution_time']:.2f}s",
            ""
        ]
        
        # 优先显示stdout（通常是主要结果）
        if result['stdout']:
            llm_content_parts.extend([
                f"=== COMMAND OUTPUT ({len(result['stdout'])} chars) ===",
                result['stdout'],
                f"=== END OUTPUT ==="
            ])
        else:
            llm_content_parts.append("(no stdout output)")
            
        # 然后显示stderr（如果有）
        if result['stderr']:
            llm_content_parts.extend([
                "",
                f"=== ERROR OUTPUT ({len(result['stderr'])} chars) ===", 
                result['stderr'],
                f"=== END ERROR ==="
            ])
            
        # 添加截断信息（如果适用）
        stdout_truncated = result.get("stdout_truncated", False)
        stderr_truncated = result.get("stderr_truncated", False)
        if stdout_truncated or stderr_truncated:
            llm_content_parts.extend([
                "",
                f"⚠️ Large output processed intelligently:",
                f"- Stdout truncated: {'Yes' if stdout_truncated else 'No'}",
                f"- Stderr truncated: {'Yes' if stderr_truncated else 'No'}",
                f"- Original size preserved where possible"
            ])
        
        # 原生错误信息 - 保持最原始的形式，便于Agent理解和重试
        raw_error = result['stderr'].strip() if result['stderr'] else None
        
        # 构建用户显示内容
        if result["success"]:
            display_lines = [
                self._('shell_success_title', default="✅ Shell命令执行成功"),
                self._('shell_execution_time', default="⏱️ 执行时间: {time:.2f}秒", time=result['execution_time']),
                ""
            ]
            
            if result["stdout"]:
                display_lines.extend([
                    self._('shell_stdout_header', default="### 标准输出:"),
                    "```",
                    result["stdout"],
                    "```"
                ])
                
            if result["stderr"]:
                display_lines.extend([
                    "",
                    self._('shell_stderr_header', default="### 标准错误:"),
                    "```", 
                    result["stderr"],
                    "```"
                ])
                
            return ToolResult(
                summary=self._('shell_success_summary', default="Shell命令执行成功 (退出码: {code})", code=result['exit_code']),
                llm_content="\n".join(llm_content_parts),
                return_display="\n".join(display_lines)
            )
        else:
            display_lines = [
                self._('shell_failed_title', default="❌ Shell命令执行失败"),
                self._('shell_execution_time', default="⏱️ 执行时间: {time:.2f}秒", time=result['execution_time']),
                self._('shell_exit_code', default="🔢 退出码: {code}", code=result['exit_code']),
                ""
            ]
            
            if result["stderr"]:
                display_lines.extend([
                    self._('shell_error_header', default="### 错误信息:"),
                    "```",
                    result["stderr"],
                    "```"
                ])
                
            if result["stdout"]:
                display_lines.extend([
                    "",
                    self._('shell_stdout_header', default="### 标准输出:"),
                    "```",
                    result["stdout"], 
                    "```"
                ])
                
            # 确保Agent收到原生错误信息，方便智能重试
            # 完全保持原生形式，让Agent自主判断和适配
            agent_error_info = raw_error or f"Command failed with exit code {result['exit_code']}"
            
            return ToolResult(
                summary=self._('shell_failed_summary_detail', default="Shell命令执行失败 (退出码: {code})", code=result['exit_code']),
                llm_content="\n".join(llm_content_parts),
                return_display="\n".join(display_lines),
                error=agent_error_info  # 原生错误信息，便于Agent理解和重试
            )
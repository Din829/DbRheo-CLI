"""
CodeExecutionTool - 通用代码执行工具
支持多种编程语言的代码执行，类似SQL工具执行SQL
设计原则：最小侵入性、解决真实痛点、保持灵活性
"""

import asyncio
import os
import sys
import subprocess
import tempfile
import json
import traceback
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class CodeExecutionTool(DatabaseTool):
    """
    通用代码执行工具
    
    支持多种编程语言的本地执行，为Agent提供强大的计算和自动化能力。
    类似于SQL工具执行SQL查询，这个工具执行各种编程语言的代码。
    
    特点：
    - 支持多种语言（Python、JavaScript、Shell等）
    - 安全的执行环境
    - 灵活的超时控制
    - 支持上下文数据传递
    """
    
    # 支持的语言配置（可通过配置扩展）
    LANGUAGE_CONFIG = {
        "python": {
            "extension": ".py",
            "command": [sys.executable, "-u"],  # -u for unbuffered output
            "description": "Python代码（数据分析、自动化脚本）"
        },
        "javascript": {
            "extension": ".js",
            "command": ["node"],
            "description": "JavaScript代码（Node.js环境）"
        },
        "shell": {
            "extension": ".sh",
            "command": ["bash"],
            "description": "Shell脚本（系统命令、文件操作）"
        },
        "sql": {
            "extension": ".sql",
            "command": ["sqlite3"],  # 默认SQLite，可配置
            "description": "SQL脚本（直接执行）"
        }
    }
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        # 从配置中获取支持的语言
        supported_languages = config.get("code_execution_languages", list(self.LANGUAGE_CONFIG.keys()))
        
        # 构建参数schema
        parameter_schema = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code to execute"
                },
                "language": {
                    "type": "string",
                    "enum": supported_languages,
                    "description": f"Programming language: {', '.join(supported_languages)}"
                },
                "context": {
                    "type": "object",
                    "description": "Execution context (variables, data, etc.)",
                    "properties": {
                        "variables": {
                            "type": "object",
                            "description": "Variables to inject"
                        },
                        "sql_result": {
                            "description": "SQL query result (auto-converted to appropriate format)"
                        },
                        "files": {
                            "type": "array",
                            "description": "Related file paths",
                            "items": {
                                "type": "string"
                            }
                        }
                    }
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout (seconds)",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (optional)"
                }
            },
            "required": ["code", "language"]
        }
        
        # 构建描述
        lang_descriptions = [f"{lang}({self.LANGUAGE_CONFIG[lang]['description']})" for lang in supported_languages]
        description = f"Execute code in multiple languages. Supports: {', '.join(lang_descriptions)}. Each execution runs in a fresh environment - variables don't persist between calls. Consider combining operations when needed. Returns execution results."
        
        super().__init__(
            name="execute_code",
            display_name=self._('code_exec_tool_name', default="代码执行器") if i18n else "代码执行器",
            description=description,
            parameter_schema=parameter_schema,
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        self.supported_languages = supported_languages
        # 可配置的安全限制
        self.max_output_size = config.get("code_execution_max_output", 1024 * 1024)  # 1MB
        self.allowed_modules = config.get("code_execution_allowed_modules", [])
        self.temp_dir = config.get("code_execution_temp_dir", tempfile.gettempdir())
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        # 调试：打印接收到的参数
        from ..utils.debug_logger import log_info
        log_info("CodeExecution", f"Received params: {params}")
        
        code = params.get("code", "").strip()
        if not code:
            return self._('code_exec_empty', default="代码不能为空")
            
        language = params.get("language", "")
        if not language:
            # 如果没有提供语言，默认使用 python
            log_info("CodeExecution", "No language provided, defaulting to python")
            params["language"] = "python"
            language = "python"
            
        if language not in self.supported_languages:
            return self._('code_exec_unsupported_lang', default="不支持的语言：{language}。支持的语言：{supported}", language=language, supported=', '.join(self.supported_languages))
            
        timeout = params.get("timeout", 30)
        if timeout < 1 or timeout > 300:
            return self._('code_exec_invalid_timeout', default="超时时间必须在1-300秒之间")
            
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        language = params.get("language", "unknown")
        code_preview = params.get("code", "")[:50]
        return self._('code_exec_description', default="执行{language}代码：{preview}...", language=language, preview=code_preview)
        
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, Any]:
        """检查是否需要确认"""
        code = params.get("code", "")
        language = params.get("language", "")
        
        # 危险操作检测（灵活配置）
        danger_patterns = self.config.get("code_execution_danger_patterns", {
            "all": ["rm -rf", "format c:", "del /f /s /q"],
            "python": ["__import__('os').system", "eval(", "exec(", "compile("],
            "shell": ["sudo", "chmod 777", "mkfs"],
            "javascript": ["require('child_process')", "process.exit"]
        })
        
        # 检查通用危险模式
        risks = []
        for pattern in danger_patterns.get("all", []):
            if pattern.lower() in code.lower():
                risks.append(self._('code_exec_danger_pattern', default="包含危险操作：{pattern}", pattern=pattern))
                
        # 检查语言特定危险模式
        for pattern in danger_patterns.get(language, []):
            if pattern.lower() in code.lower():
                risks.append(self._('code_exec_lang_danger', default="包含{language}危险操作：{pattern}", language=language, pattern=pattern))
                
        if risks:
            return {
                "title": self._('code_exec_confirm_title', default="确认执行{language}代码", language=language),
                "message": self._('code_exec_danger_detected', default="检测到潜在危险操作"),
                "details": "\n".join(risks) + self._('code_exec_preview', default="\n\n代码预览：\n{code}...", code=code[:200])
            }
            
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行代码"""
        code = params.get("code", "")
        language = params.get("language", "")
        context = params.get("context", {})
        timeout = params.get("timeout", 30)
        working_dir = params.get("working_dir", self.temp_dir)
        
        try:
            if update_output:
                update_output(self._('code_exec_running', default="🚀 正在执行{language}代码...\n```{language}\n{code}\n```", language=language, code=code[:300] + ('...' if len(code) > 300 else '')))
                
            # 准备执行环境
            prepared_code = self._prepare_code_with_context(code, language, context)
            
            # 执行代码
            result = await self._execute_code(
                prepared_code, 
                language, 
                timeout, 
                working_dir,
                update_output
            )
            
            # 格式化结果
            if result["success"]:
                display = self._format_success_output(result, language)
                if update_output:
                    update_output(display)
                    
                return ToolResult(
                    summary=self._('code_exec_success_summary', default="{language}代码执行成功", language=language),
                    llm_content={
                        "success": True,
                        "language": language,
                        "output": result["output"],
                        "error": result["error"],
                        "execution_time": result["execution_time"]
                    },
                    return_display=display
                )
            else:
                display = self._format_error_output(result, language)
                if update_output:
                    update_output(display)
                    
                # 分析错误类型，为Agent提供修复建议
                error_analysis = self._analyze_error(result["error"], language)
                
                return ToolResult(
                    summary=self._('code_exec_failed_summary', default="{language}代码执行失败：{error_type}", language=language, error_type=error_analysis['type']),
                    llm_content={
                        "success": False,
                        "language": language,
                        "output": result["output"],
                        "error": result["error"],
                        "error_analysis": error_analysis,
                        "execution_time": result["execution_time"],
                        "retry_suggestion": error_analysis["suggestion"]
                    },
                    return_display=display,
                    error=result["error"]
                )
                
        except Exception as e:
            error_msg = self._('code_exec_exception', default="代码执行异常：{error}\n{trace}", error=str(e), trace=traceback.format_exc())
            return ToolResult(
                error=error_msg,
                summary=self._('code_exec_failed', default="代码执行失败"),
                return_display=self._('code_exec_failed_display', default="❌ 执行失败\n\n{error}", error=error_msg)
            )
            
    def _prepare_code_with_context(self, code: str, language: str, context: Dict[str, Any]) -> str:
        """准备带上下文的代码"""
        if not context:
            return code
            
        # 根据语言准备上下文注入
        if language == "python":
            lines = [self._('code_exec_context_comment', default="# 自动注入的上下文")]
            
            # 处理变量
            if "variables" in context:
                for name, value in context["variables"].items():
                    if isinstance(value, str):
                        lines.append(f"{name} = {repr(value)}")
                    else:
                        lines.append(f"{name} = {json.dumps(value, ensure_ascii=False)}")
                        
            # 处理SQL结果
            if "sql_result" in context:
                lines.append(self._('code_exec_sql_result_comment', default="# SQL查询结果"))
                lines.append("import pandas as pd")
                lines.append(f"sql_result = {json.dumps(context['sql_result'], ensure_ascii=False)}")
                lines.append(self._('code_exec_dataframe_comment', default="# 如果是表格数据，自动转换为DataFrame"))
                lines.append("if isinstance(sql_result, list) and sql_result and isinstance(sql_result[0], dict):")
                lines.append("    df = pd.DataFrame(sql_result)")
                    
            return "\n".join(lines) + self._('code_exec_user_code_sep', default="\n\n# 用户代码\n") + code
            
        elif language == "javascript":
            lines = [self._('code_exec_js_context_comment', default="// 自动注入的上下文")]
            
            if "variables" in context:
                for name, value in context["variables"].items():
                    lines.append(f"const {name} = {json.dumps(value)};")
                    
            if "sql_result" in context:
                lines.append(self._('code_exec_js_sql_comment', default="// SQL查询结果"))
                lines.append(f"const sqlResult = {json.dumps(context['sql_result'])};")
                
            return "\n".join(lines) + self._('code_exec_js_user_code_sep', default="\n\n// 用户代码\n") + code
            
        # 其他语言暂不支持上下文注入
        return code
        
    async def _execute_code(
        self, 
        code: str, 
        language: str, 
        timeout: int,
        working_dir: str,
        update_output: Optional[Any] = None
    ) -> Dict[str, Any]:
        """执行代码并返回结果"""
        import asyncio
        import time
        
        # 获取语言配置
        lang_config = self.LANGUAGE_CONFIG.get(language, {})
        if not lang_config:
            return {
                "success": False,
                "output": "",
                "error": self._('code_exec_lang_not_supported', default="不支持的语言：{language}", language=language),
                "execution_time": 0
            }
            
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=lang_config["extension"],
            dir=self.temp_dir,
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
            
        try:
            # 构建命令
            command = lang_config["command"] + [temp_file]
            
            # 执行代码
            start_time = time.time()
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            # 等待执行完成（带超时）
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                execution_time = time.time() - start_time
                
                # 解码输出
                output = stdout.decode('utf-8', errors='replace')
                error = stderr.decode('utf-8', errors='replace')
                
                # 限制输出大小
                if len(output) > self.max_output_size:
                    output = output[:self.max_output_size] + self._('code_exec_output_truncated', default="\n... [输出被截断]")
                if len(error) > self.max_output_size:
                    error = error[:self.max_output_size] + self._('code_exec_error_truncated', default="\n... [错误输出被截断]")
                    
                return {
                    "success": process.returncode == 0,
                    "output": output,
                    "error": error,
                    "execution_time": execution_time
                }
                
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "output": "",
                    "error": self._('code_exec_timeout', default="执行超时（{timeout}秒）", timeout=timeout),
                    "execution_time": timeout
                }
                
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
                
    def _format_success_output(self, result: Dict[str, Any], language: str) -> str:
        """格式化成功输出"""
        lines = [
            self._('code_exec_success_title', default="✅ {language}代码执行成功", language=language),
            self._('code_exec_time', default="⏱️ 执行时间：{time:.2f}秒", time=result['execution_time']),
            ""
        ]
        
        if result["output"]:
            lines.extend([
                self._('code_exec_stdout_title', default="### 标准输出："),
                "```",
                result["output"],
                "```"
            ])
            
        if result["error"]:
            lines.extend([
                "",
                self._('code_exec_stderr_title', default="### 标准错误："),
                "```",
                result["error"],
                "```"
            ])
            
        return "\n".join(lines)
        
    def _format_error_output(self, result: Dict[str, Any], language: str) -> str:
        """格式化错误输出"""
        lines = [
            self._('code_exec_failed_title', default="❌ {language}代码执行失败", language=language),
            self._('code_exec_time', default="⏱️ 执行时间：{time:.2f}秒", time=result['execution_time']),
            ""
        ]
        
        if result["error"]:
            lines.extend([
                self._('code_exec_error_title', default="### 错误信息："),
                "```",
                result["error"],
                "```"
            ])
            
        if result["output"]:
            lines.extend([
                "",
                self._('code_exec_stdout_title', default="### 标准输出："),
                "```",
                result["output"],
                "```"
            ])
            
        return "\n".join(lines)
    def _analyze_error(self, error_text: str, language: str) -> Dict[str, Any]:
        """分析错误类型并提供修复建议"""
        if not error_text:
            return {
                "type": self._('code_exec_error_unknown', default="未知错误"),
                "suggestion": self._('code_exec_error_unknown_suggest', default="检查代码逻辑"),
                "category": "unknown"
            }
            
        error_lower = error_text.lower()
        
        # Python错误分析
        if language == "python":
            if "syntaxerror" in error_lower:
                return {
                    "type": self._('code_exec_error_syntax', default="语法错误"),
                    "suggestion": self._('code_exec_error_syntax_suggest', default="检查代码语法：括号匹配、缩进、冒号等"),
                    "category": "syntax",
                    "fixable": True
                }
            elif "nameerror" in error_lower or ("name" in error_lower and "not defined" in error_lower):
                return {
                    "type": self._('code_exec_error_name', default="变量未定义"),
                    "suggestion": self._('code_exec_error_name_suggest', default="检查变量名拼写或在使用前先定义变量"),
                    "category": "name",
                    "fixable": True
                }
            elif "modulenotfounderror" in error_lower or "no module named" in error_lower:
                return {
                    "type": self._('code_exec_error_module', default="模块导入错误"),
                    "suggestion": self._('code_exec_error_module_suggest', default="检查模块名称或使用内置模块（如pandas、numpy、matplotlib）"),
                    "category": "import",
                    "fixable": True
                }
                
        # 通用错误分析
        if "timeout" in error_lower:
            return {
                "type": self._('code_exec_error_timeout_type', default="执行超时"),
                "suggestion": self._('code_exec_error_timeout_suggest', default="优化代码性能或增加超时时间"),
                "category": "timeout",
                "fixable": True
            }
            
        return {
            "type": self._('code_exec_error_runtime', default="运行时错误"),
            "suggestion": self._('code_exec_error_runtime_suggest', default="检查错误信息，修复相应的逻辑问题"),
            "category": "runtime",
            "fixable": True
        }

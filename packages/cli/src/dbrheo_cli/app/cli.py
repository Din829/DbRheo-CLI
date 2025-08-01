"""
CLI主应用类
负责初始化、配置加载、主循环管理等核心功能。
对应chat_cli.py中的DbRheoCLI类。
"""

import os
import sys
import readline
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from dbrheo.config.test_config import TestDatabaseConfig
from dbrheo.core.client import DatabaseClient
from dbrheo.types.core_types import SimpleAbortSignal
from dbrheo.utils.debug_logger import DebugLogger, log_info

from ..handlers.event_handler import EventHandler
from ..handlers.tool_handler import ToolHandler
from ..handlers.input_handler import InputHandler
from ..ui.console import console
from ..ui.layout_manager import create_layout_manager, FallbackLayoutManager
from ..i18n import _, I18n
from ..constants import COMMANDS, SYSTEM_COMMANDS, DEBUG_LEVEL_RANGE, DEFAULTS, ENV_VARS
from .config import CLIConfig


class DbRheoCLI:
    """
    主CLI应用类
    - 管理生命周期
    - 协调各模块交互
    - 保持与后端的连接
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config
        self.running = True
        self.session_id = f"{DEFAULTS['SESSION_ID_PREFIX']}_{os.getpid()}"
        self.tool_call_count = 0  # 工具调用统计
        self.in_response = False  # 标记是否正在接收响应
        
        # 初始化后端
        self._init_backend()
        
        # 初始化处理器
        self._init_handlers()
        
        # 初始化布局管理器 - 最小侵入性集成
        self._init_layout_manager()
        
        # 初始化历史记录
        self._init_history()
        
        # 设置键盘监听
        self._setup_keyboard_listener()
        
        log_info("CLI", "DbRheo CLI initialized")
    
    def _init_backend(self):
        """初始化后端连接，保持灵活性"""
        # 创建数据库配置
        if self.config.db_file:
            self.db_config = TestDatabaseConfig.create_with_sqlite_database(
                self.config.db_file
            )
        else:
            # 默认使用内存数据库
            self.db_config = TestDatabaseConfig.create_with_memory_database()
        
        # 创建i18n适配器，传递给core包
        # 使用简单的字典接口，避免core包依赖cli包的具体实现
        i18n_adapter = {
            'get': lambda key, **kwargs: _(key, **kwargs),
            'current_lang': lambda: I18n.current_lang
        }
        
        # 将i18n适配器设置到配置中
        self.db_config.set_test_config('i18n', i18n_adapter)
        
        # 创建客户端
        self.client = DatabaseClient(self.db_config)
        self.signal = SimpleAbortSignal()
        
        # 设置工具调度器回调
        self._setup_scheduler_callbacks()
    
    def _setup_scheduler_callbacks(self):
        """设置工具调度器回调，监听工具状态变化"""
        scheduler = self.client.tool_scheduler
        
        # 保存原始回调
        self._original_on_update = scheduler.on_tool_calls_update
        
        # 注册新回调
        def on_tools_update(tool_calls):
            # 更新工具调用计数
            self.tool_call_count = len(tool_calls)
            # 调用工具处理器
            if hasattr(self, 'tool_handler'):
                self.tool_handler.on_tools_update(tool_calls)
            # 调用原始回调
            if self._original_on_update:
                self._original_on_update(tool_calls)
        
        scheduler.on_tool_calls_update = on_tools_update
    
    def _init_handlers(self):
        """初始化各种处理器"""
        self.event_handler = EventHandler(self.config)
        self.tool_handler = ToolHandler(self.client.tool_scheduler, self.config)
        self.input_handler = InputHandler(self.config)
    
    def _init_layout_manager(self):
        """
        初始化布局管理器 - 最小侵入性设计
        如果增强布局不可用，自动fallback到传统模式
        """
        # 尝试创建增强布局管理器
        layout_manager = create_layout_manager(self.config)
        
        if layout_manager and layout_manager.is_available():
            self.layout_manager = layout_manager
            log_info("CLI", _('enhanced_layout'))
        else:
            # Fallback到传统模式
            self.layout_manager = FallbackLayoutManager(self.config)
            log_info("CLI", _('traditional_layout'))
        
        # 设置布局管理器为事件显示的输出目标
        self.event_handler.set_display_target(self.layout_manager)
    
    def _init_history(self):
        """初始化命令历史"""
        # 设置历史文件
        readline.set_history_length(self.config.max_history)
        
        # 尝试加载历史记录
        if os.path.exists(self.config.history_file):
            try:
                readline.read_history_file(self.config.history_file)
            except Exception as e:
                log_info("CLI", f"Failed to load history: {e}")
    
    def _setup_keyboard_listener(self):
        """设置键盘监听器"""
        # 允许通过环境变量完全禁用ESC监听（解决特殊情况）
        if os.getenv('DBRHEO_DISABLE_ESC_LISTENER', 'false').lower() == 'true':
            log_info("CLI", "ESC listener disabled by environment variable")
            return
            
        import threading
        
        def keyboard_listener():
            """在后台线程监听键盘输入"""
            try:
                import msvcrt  # Windows
                while self.running:
                    # 只在响应时才检测键盘输入，避免吞字
                    if self.in_response and msvcrt.kbhit():
                        key = msvcrt.getch()
                        # ESC键的ASCII码是27
                        if key == b'\x1b':
                            console.print(f"\n[yellow]{_('esc_abort')}[/yellow]")
                            self.signal.abort()
                            # 重置状态，避免界面卡死
                            self.in_response = False
                        # 注意：如果不是ESC键，字符已经被消耗
                        # 但由于只在in_response时检测，影响最小化
                    import time
                    time.sleep(0.1)
            except ImportError:
                # 非Windows系统，尝试其他方法
                try:
                    import termios, tty, select
                    # TODO: 实现Linux/Mac的ESC检测
                except:
                    pass
        
        # 在后台线程启动监听器
        listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
        listener_thread.start()
    
    def save_history(self):
        """保存历史记录"""
        try:
            readline.write_history_file(self.config.history_file)
        except Exception as e:
            log_info("CLI", f"Failed to save history: {e}")
    
    async def run(self):
        """
        主运行循环 - 支持传统和增强布局模式
        最小侵入性：自动选择最合适的运行模式
        """
        # 检查是否使用增强布局
        if hasattr(self.layout_manager, 'run_async') and self.layout_manager.is_available():
            # 使用增强布局模式
            await self._run_enhanced_mode()
        else:
            # 使用传统模式
            await self._run_traditional_mode()
    
    async def _run_traditional_mode(self):
        """传统运行模式 - 保持100%兼容"""
        while self.running:
            try:
                # 获取用户输入
                user_input = await self.input_handler.get_input()
                
                # 处理命令
                if user_input.startswith('/'):
                    await self._handle_command(user_input)
                    # 如果是退出命令，立即跳出循环
                    if not self.running:
                        break
                    continue
                
                # 处理普通消息
                await self._handle_message(user_input)
                
            except KeyboardInterrupt:
                # Ctrl+C 被信号处理器捕获
                break
            except EOFError:
                # Ctrl+D
                self.running = False
                break
            except Exception as e:
                console.print(f"[red]{_('error_format', error=e)}[/red]")
                if DebugLogger.should_log("DEBUG"):
                    import traceback
                    traceback.print_exc()
    
    async def _run_enhanced_mode(self):
        """增强运行模式 - 底部固定输入框"""
        try:
            # 显示欢迎信息
            # 不再显示增强布局模式标题，直接显示操作提示
            self.layout_manager.add_message(_('enhanced_layout_shortcuts'), style='class:dim')
            
            # 运行布局管理器，传入输入处理回调
            await self.layout_manager.run_async(self._handle_enhanced_input)
            
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
    
    async def _handle_enhanced_input(self, user_input: str):
        """
        处理增强模式下的用户输入
        与传统模式保持相同的处理逻辑
        """
        try:
            # 处理命令
            if user_input.startswith('/'):
                await self._handle_command(user_input)
                return
            
            # 处理普通消息
            await self._handle_message(user_input)
            
        except Exception as e:
            self.layout_manager.add_message(_('error_format', error=e), style='class:error')
            if DebugLogger.should_log("DEBUG"):
                import traceback
                error_trace = traceback.format_exc()
                self.layout_manager.add_message(error_trace, style='class:dim')
    
    async def _handle_command(self, command: str):
        """处理斜杠命令"""
        cmd = command.lower().strip()
        
        if cmd in COMMANDS['EXIT']:
            self.running = False
            # 立即中止所有正在进行的操作
            if hasattr(self, 'signal') and self.signal:
                self.signal.abort()
            
            # 立即退出，不等待清理
            console.print(f"[yellow]{_('exiting')}[/yellow]")
            
            # 强制停止事件循环
            try:
                loop = asyncio.get_event_loop()
                loop.stop()
            except:
                pass
            
            # 使用 os._exit 确保立即退出
            import os
            os._exit(0)
        elif cmd in COMMANDS['HELP']:
            self._show_help()
        elif cmd in COMMANDS['CLEAR']:
            os.system(SYSTEM_COMMANDS['CLEAR'])
        elif cmd.startswith(COMMANDS['DEBUG'][0]):
            self._handle_debug_command(cmd)
        elif cmd.startswith(COMMANDS['LANG'][0]) or cmd.startswith(COMMANDS['LANG'][1]):
            self._handle_lang_command(cmd)
        else:
            console.print(f"[yellow]{_('unknown_command', command=command)}[/yellow]")
    
    def _handle_debug_command(self, cmd: str):
        """处理调试命令"""
        parts = cmd.split()
        if len(parts) == 2 and parts[1].isdigit():
            level = int(parts[1])
            if DEBUG_LEVEL_RANGE[0] <= level <= DEBUG_LEVEL_RANGE[1]:
                # 将数字转换为日志级别名称
                level_map = {0: 'ERROR', 1: 'WARNING', 2: 'INFO', 3: 'DEBUG', 4: 'DEBUG', 5: 'DEBUG'}
                debug_level = level_map.get(level, 'INFO')
                os.environ[ENV_VARS['DEBUG_LEVEL']] = debug_level
                
                # 重新加载debug_logger模块以应用新的日志级别
                try:
                    import importlib
                    import dbrheo.utils.debug_logger
                    importlib.reload(dbrheo.utils.debug_logger)
                    from dbrheo.utils.debug_logger import DebugLogger
                    console.print(f"[green]{_('debug_level_set', level=level)} ({debug_level})[/green]")
                except Exception as e:
                    console.print(f"[yellow]{_('debug_reload_warning', error=e)}[/yellow]")
            else:
                console.print(f"[red]{_('debug_level_range')}[/red]")
        else:
            # 获取当前的调试级别
            current_level = os.environ.get(ENV_VARS['DEBUG_LEVEL'], 'INFO')
            # 反向映射显示数字
            level_to_num = {'ERROR': 0, 'WARNING': 1, 'INFO': 2, 'DEBUG': 3}
            current = level_to_num.get(current_level, 2)
            console.print(_('current_debug_level', level=current))
            console.print(_('debug_usage'))
    
    def _handle_lang_command(self, cmd: str):
        """处理语言切换命令"""
        parts = cmd.split()
        
        if len(parts) == 2:
            lang_arg = parts[1].lower()
            # 支持简短形式
            lang_map = {
                'zh': 'zh_CN',
                'cn': 'zh_CN',
                'zh_cn': 'zh_CN',
                'ja': 'ja_JP',
                'jp': 'ja_JP',
                'ja_jp': 'ja_JP',
                'en': 'en_US',
                'us': 'en_US',
                'en_us': 'en_US'
            }
            
            lang_code = lang_map.get(lang_arg)
            if lang_code and lang_code in I18n.get_available_languages():
                I18n.set_language(lang_code)
                lang_name = I18n.get_language_name(lang_code)
                console.print(f"[green]{_('language_set', lang=lang_name)}[/green]")
            else:
                console.print(f"[red]{_('language_not_supported', lang=lang_arg)}[/red]")
                console.print(_('available_languages'))
        else:
            # 显示当前语言
            current = I18n.current_lang
            lang_name = I18n.get_language_name(current)
            console.print(_('current_language', lang=lang_name))
            console.print(_('language_usage'))
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = f"""
[bold]{_('help_title')}:[/bold]
  /help        - {_('help_hint')}
  /exit, /quit - {_('help_exit')}
  /clear       - {_('help_clear')}
  /debug <0-5> - {_('help_debug')}
  /lang [code] - {_('help_lang')}
  ``` 或 <<<   - {_('help_multiline')}
  ESC         - {_('help_esc')}
  
[bold]{_('tool_confirmation_title')}:[/bold]
{_('tool_confirmation_help')}
"""
        console.print(help_text)
    
    async def _handle_message(self, user_input: str):
        """处理用户消息"""
        # 检查是否是确认命令
        if self.tool_handler.has_pending_confirmations():
            if await self.tool_handler.handle_confirmation_input(user_input, self.signal):
                # 确认后继续处理
                await self._continue_after_confirmation()
                return
        
        # 显示用户消息
        self.event_handler.show_user_message(user_input)
        
        # 发送到后端并处理响应
        try:
            # 每次新对话开始时重置信号状态
            if hasattr(self.signal, 'reset'):
                self.signal.reset()
            self.in_response = True  # 标记开始接收响应
            tool_calls = []  # 记录本次对话的工具调用
            
            async for event in self.client.send_message_stream(
                user_input, self.signal, self.session_id
            ):
                # 检查是否需要退出
                if not self.running or self.signal.aborted:
                    break
                    
                # 记录工具调用
                if event.get('type') == 'ToolCallRequest':
                    tool_value = event.get('value')
                    if tool_value:
                        tool_name = getattr(tool_value, 'name', 'unknown')
                        tool_calls.append(tool_name)
                
                await self.event_handler.process(event)
                
                # 如果收到等待确认事件，中断循环等待用户输入
                if event.get('type') == 'AwaitingConfirmation':
                    break
            
            # 显示工具调用统计
            if tool_calls:
                unique_tools = list(set(tool_calls))
                console.print(f"\n[dim]{_('tool_calls_summary', count=len(tool_calls), tools=', '.join(unique_tools))}[/dim]")
                
        except Exception as e:
            console.print(f"[red]{_('error_processing', error=e)}[/red]")
            if DebugLogger.should_log("DEBUG"):
                import traceback
                traceback.print_exc()
        finally:
            self.in_response = False  # 重置响应标志
    
    async def _continue_after_confirmation(self):
        """确认后继续处理"""
        # 等待工具执行完成
        await asyncio.sleep(0.5)
        
        # 显示继续处理的提示
        console.print(f"\n[dim]{_('continuing')}[/dim]")
        
        # 发送继续消息让AI继续处理
        try:
            # 继续处理时不重置信号（保持中止状态）
            self.in_response = True  # 标记开始接收响应
            tool_calls = []  # 记录工具调用
            
            async for event in self.client.send_message_stream(
                "Please continue.", self.signal, self.session_id
            ):
                # 检查是否需要退出
                if not self.running or self.signal.aborted:
                    break
                    
                # 记录工具调用
                if event.get('type') == 'ToolCallRequest':
                    tool_value = event.get('value')
                    if tool_value:
                        tool_name = getattr(tool_value, 'name', 'unknown')
                        tool_calls.append(tool_name)
                
                await self.event_handler.process(event)
                
                if event.get('type') == 'AwaitingConfirmation':
                    break
            
            # 显示工具调用统计（如果有的话）
            if tool_calls:
                unique_tools = list(set(tool_calls))
                console.print(f"\n[dim]{_('tool_calls_continue', count=len(tool_calls), tools=', '.join(unique_tools))}[/dim]")
                    
        except Exception as e:
            console.print(f"[red]{_('error_continuing', error=e)}[/red]")
        finally:
            self.in_response = False  # 重置响应标志
    
    def cleanup(self):
        """清理资源"""
        log_info("CLI", "Cleaning up resources...")
        
        # 设置运行标志
        self.running = False
        
        # 保存历史记录
        try:
            self.save_history()
        except Exception as e:
            log_info("CLI", f"Failed to save history: {e}")
        
        # 中止任何正在进行的操作
        if hasattr(self, 'signal') and self.signal:
            self.signal.abort()
        
        # 清理处理器
        if hasattr(self, 'tool_handler') and self.tool_handler:
            self.tool_handler.cleanup()
        
        if hasattr(self, 'event_handler') and self.event_handler:
            # 完成流式显示
            if hasattr(self.event_handler, 'stream_display'):
                try:
                    import asyncio
                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(self.event_handler.stream_display.finish())
                except:
                    pass
        
        # 清理数据库客户端
        if hasattr(self, 'client') and self.client:
            # 清理工具调度器回调
            if hasattr(self.client, 'tool_scheduler') and self.client.tool_scheduler:
                scheduler = self.client.tool_scheduler
                if hasattr(self, '_original_on_update'):
                    scheduler.on_tool_calls_update = self._original_on_update
        
        # 清理数据库连接（如果有的话）
        if hasattr(self, 'db_config') and self.db_config:
            # 注：当前实现中数据库连接由各个工具管理，无需集中清理
            pass
        
        log_info("CLI", "Cleanup complete")
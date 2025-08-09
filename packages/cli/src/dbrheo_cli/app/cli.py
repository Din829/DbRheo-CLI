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
        log_info("CLI", f"🔄 Creating new DatabaseClient (previous client ID: {id(self.client) if hasattr(self, 'client') else 'None'})")
        self.client = DatabaseClient(self.db_config)
        log_info("CLI", f"🔄 New DatabaseClient created with ID: {id(self.client)}")
        log_info("CLI", f"🔄 New tool_scheduler ID: {id(self.client.tool_scheduler)}")
        self.signal = SimpleAbortSignal()
        
        # 将client引用保存到config中（供token警告功能使用）
        self.config._client = self.client
        
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
        elif cmd.startswith(COMMANDS['MODEL'][0]):
            self._handle_model_command(cmd)
        elif cmd in COMMANDS['TOKEN']:
            self._handle_token_command()
        elif cmd in COMMANDS['DATABASE']:
            self._handle_database_command()
        elif cmd.startswith(COMMANDS['MCP'][0]):
            await self._handle_mcp_command(cmd)
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
    
    def _handle_model_command(self, cmd: str):
        """处理模型切换命令"""
        from ..constants import SUPPORTED_MODELS
        parts = cmd.split()
        
        if len(parts) == 2:
            model_name = parts[1]
            
            # 验证模型名称
            if model_name not in SUPPORTED_MODELS:
                console.print(f"[red]{_('invalid_model', model=model_name)}[/red]")
                console.print(f"\n[cyan]{_('supported_models')}:[/cyan]")
                for key, name in SUPPORTED_MODELS.items():
                    console.print(f"  [bold]/model {key}[/bold] → {name}")
                return
            
            # 设置环境变量
            os.environ[ENV_VARS['MODEL']] = model_name
            
            # 重新创建后端连接以使用新模型
            try:
                # 清理当前连接状态
                if hasattr(self, 'signal') and self.signal:
                    self.signal.abort()  # 中止任何进行中的操作
                
                # 重新初始化后端
                self._init_backend()
                
                # 重新初始化处理器以使用新的scheduler
                self._init_handlers()
                
                # 保存用户的模型选择偏好（最小侵入性）
                if hasattr(self.client.config, 'save_user_preference'):
                    self.client.config.save_user_preference('model', model_name)
                
                console.print(f"[green]{_('model_switched', model=model_name)}[/green]")
                
                # 检查新模型的 API Key
                from ..utils.api_key_checker import show_api_key_setup_guide
                show_api_key_setup_guide(model_name)
                
                # 显示具体的可用模型
                console.print(f"\n[cyan]{_('available_models')}:[/cyan]")
                for key, name in SUPPORTED_MODELS.items():
                    console.print(f"  [bold]/model {key}[/bold] → {name}")
            except Exception as e:
                console.print(f"[red]{_('model_switch_failed', error=e)}[/red]")
                log_info("CLI", f"Model switch failed: {e}")
        else:
            # 显示当前模型和可用选项
            current_model = os.environ.get(ENV_VARS['MODEL'], 'gemini-2.5-flash')
            console.print(f"[cyan]{_('current_model', model=current_model)}[/cyan]")
            console.print(f"\n{_('model_usage')}:\n")
            for key, name in SUPPORTED_MODELS.items():
                if key == 'gemini':
                    console.print(f"  [bold]/model {key}[/bold] → {name} ({_('default')})")
                else:
                    console.print(f"  [bold]/model {key}[/bold] → {name}")
            console.print(f"\n[dim]{_('example')}: /model claude[/dim]")
    
    def _handle_token_command(self):
        """处理 token 统计命令"""
        if hasattr(self.client, 'token_statistics'):
            self._show_token_statistics(self.client.token_statistics)
        else:
            console.print(f"[yellow]{_('token_statistics_unavailable')}[/yellow]")
    
    async def _handle_mcp_command(self, cmd: str):
        """处理 MCP 命令"""
        parts = cmd.split()
        
        # 获取工具注册表
        tool_registry = self.client.tool_registry if hasattr(self.client, 'tool_registry') else None
        if not tool_registry:
            console.print(f"[yellow]{_('mcp_support_not_available')}[/yellow]")
            return
        
        # 尝试获取 MCP 注册表
        mcp_registry = tool_registry.get_mcp_registry()
        
        if len(parts) == 1:
            # 显示 MCP 状态和帮助
            await self._show_mcp_status(mcp_registry)
        elif len(parts) >= 2:
            action = parts[1].lower()
            
            if action == 'list':
                await self._show_mcp_servers(mcp_registry)
            elif action == 'add':
                if len(parts) >= 3:
                    await self._add_mcp_server(mcp_registry, parts[2:])
                else:
                    console.print(f"[yellow]{_('mcp_add_usage')}[/yellow]")
            elif action == 'remove':
                if len(parts) >= 3:
                    await self._remove_mcp_server(mcp_registry, parts[2])
                else:
                    console.print(f"[yellow]{_('mcp_remove_usage')}[/yellow]")
            elif action == 'reload':
                await self._reload_mcp_servers(mcp_registry, tool_registry)
            elif action == 'help':
                self._show_mcp_help()
            else:
                console.print(f"[yellow]{_('mcp_unknown_action', action=action)}[/yellow]")
                self._show_mcp_help()
    
    async def _show_mcp_status(self, mcp_registry):
        """显示 MCP 状态"""
        if not mcp_registry:
            # MCP 未初始化，尝试初始化
            tool_registry = self.client.tool_registry
            console.print(f"[cyan]{_('mcp_initializing')}[/cyan]")
            success = await tool_registry.initialize_mcp()
            
            if success:
                mcp_registry = tool_registry.get_mcp_registry()
                console.print(f"[green]{_('mcp_initialized')}[/green]")
            else:
                console.print(f"[yellow]{_('mcp_not_available_install')}[/yellow]")
                return
        
        # 显示服务器状态
        if mcp_registry:
            statuses = mcp_registry.get_all_server_statuses()
            
            if statuses:
                console.print(f"\n[bold]{_('mcp_servers_title')}[/bold]")
                for name, status in statuses.items():
                    status_icon = {
                        'connected': '🟢',
                        'connecting': '🔄',
                        'disconnected': '🔴',
                        'error': '❌'
                    }.get(status.value, '❓')
                    
                    tools = mcp_registry.get_server_tools(name)
                    console.print(f"  {status_icon} {name} - {status.value} ({len(tools)} {_('mcp_tools')})")
            else:
                console.print(f"[dim]{_('mcp_no_servers')}[/dim]")
                console.print(f"\n{_('mcp_add_server_hint')}")
                console.print(f"{_('mcp_add_server_example')}")
    
    async def _show_mcp_servers(self, mcp_registry):
        """显示 MCP 服务器列表"""
        if not mcp_registry:
            console.print(f"[yellow]{_('mcp_not_initialized')}[/yellow]")
            return
        
        await self._show_mcp_status(mcp_registry)
    
    async def _add_mcp_server(self, mcp_registry, args):
        """添加 MCP 服务器"""
        if not mcp_registry:
            console.print(f"[yellow]{_('mcp_not_initialized')}[/yellow]")
            return
        
        if len(args) < 2:
            console.print(f"[yellow]{_('mcp_add_usage')}[/yellow]")
            return
        
        name = args[0]
        remaining_args = args[1:]
        
        # Flexible parsing to support various formats
        # Examples:
        # 1. /mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
        # 2. /mcp add filesystem 'npx -y @modelcontextprotocol/server-filesystem /tmp'
        # 3. /mcp add filesystem npx @modelcontextprotocol/server-filesystem /tmp
        # 4. /mcp add api https://api.example.com
        # 5. /mcp add puppeteer "npx -y @modelcontextprotocol/server-puppeteer"
        
        import shlex
        from dbrheo.tools.mcp import MCPServerConfig
        
        # First, join all remaining args to handle various input styles
        full_command = ' '.join(remaining_args)
        
        # Check if it's a URL (for HTTP/SSE servers)
        if full_command.startswith(('http://', 'https://', 'ws://', 'wss://')):
            config = MCPServerConfig(url=full_command)
        else:
            # It's a command - parse intelligently
            # Try to detect if the whole thing is quoted
            if len(remaining_args) == 1:
                # Single argument, might be quoted
                try:
                    command_parts = shlex.split(remaining_args[0])
                except:
                    command_parts = remaining_args[0].split()
            else:
                # Multiple arguments
                # Check if first arg is the command and rest are args
                command = remaining_args[0]
                
                # Special handling for npx commands
                if command == 'npx':
                    # This is an npx command
                    config = MCPServerConfig(
                        command='npx',
                        args=remaining_args[1:]  # Everything after npx
                    )
                elif command == 'node' or command == 'python' or command == 'python3':
                    # Other common commands
                    config = MCPServerConfig(
                        command=command,
                        args=remaining_args[1:]
                    )
                else:
                    # Try to parse as a full command string
                    try:
                        command_parts = shlex.split(full_command)
                    except:
                        command_parts = full_command.split()
                    
                    if command_parts:
                        config = MCPServerConfig(
                            command=command_parts[0],
                            args=command_parts[1:] if len(command_parts) > 1 else []
                        )
                    else:
                        console.print(f"[red]{_('mcp_invalid_command')}[/red]")
                        return
        
        console.print(f"[cyan]{_('mcp_adding_server', name=name)}[/cyan]")
        await mcp_registry.add_server(name, config, self.client.tool_registry)
        console.print(f"[green]{_('mcp_server_added', name=name)}[/green]")
    
    async def _remove_mcp_server(self, mcp_registry, name):
        """移除 MCP 服务器"""
        if not mcp_registry:
            console.print(f"[yellow]{_('mcp_not_initialized')}[/yellow]")
            return
        
        console.print(f"[cyan]{_('mcp_removing_server', name=name)}[/cyan]")
        await mcp_registry.remove_server(name, self.client.tool_registry)
        console.print(f"[green]{_('mcp_server_removed', name=name)}[/green]")
    
    async def _reload_mcp_servers(self, mcp_registry, tool_registry):
        """重新加载 MCP 服务器"""
        console.print(f"[cyan]{_('mcp_reloading')}[/cyan]")
        
        if mcp_registry:
            await mcp_registry.refresh(tool_registry)
        else:
            await tool_registry.initialize_mcp()
        
        console.print(f"[green]{_('mcp_reloaded')}[/green]")
    
    def _show_mcp_help(self):
        """显示 MCP 帮助信息"""
        help_text = f"""
[bold]{_('mcp_help_title')}[/bold]

  [cyan]/mcp[/cyan]                    - {_('mcp_help_status')}
  [cyan]/mcp list[/cyan]              - {_('mcp_help_list')}
  [cyan]/mcp add <name> <cmd>[/cyan]  - {_('mcp_help_add')}
  [cyan]/mcp remove <name>[/cyan]      - {_('mcp_help_remove')}
  [cyan]/mcp reload[/cyan]            - {_('mcp_help_reload')}
  [cyan]/mcp help[/cyan]              - {_('mcp_help_help')}

[bold]{_('mcp_help_examples')}[/bold]
  [dim]# NPX servers (multiple formats supported):[/dim]
  /mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
  /mcp add puppeteer 'npx -y @modelcontextprotocol/server-puppeteer'
  /mcp add github npx @modelcontextprotocol/server-github
  
  [dim]# HTTP/WebSocket servers:[/dim]
  /mcp add api https://api.example.com/mcp
  /mcp add ws wss://example.com/mcp
  
  [dim]# Other command servers:[/dim]
  /mcp add custom python3 /path/to/mcp_server.py --port 3000
  /mcp add myserver node server.js

[dim]{_('mcp_help_note')}[/dim]
"""
        console.print(help_text)
    
    def _show_token_statistics(self, stats):
        """显示 token 统计信息"""
        summary = stats.get_summary()
        
        if summary['total_calls'] == 0:
            console.print(f"[dim]{_('no_token_usage_yet')}[/dim]")
            return
        
        # 显示标题
        console.print(f"\n[bold]{_('token_usage_title')}[/bold]")
        
        # 显示总计
        console.print(_('token_usage_total', 
                       total=summary['total_tokens'],
                       calls=summary['total_calls']))
        console.print(_('token_usage_detail', 
                       prompt=summary['total_prompt_tokens']))
        console.print(_('token_usage_detail_output', 
                       completion=summary['total_completion_tokens']))
        
        # 如果有缓存，显示缓存信息
        if summary.get('total_cached_tokens', 0) > 0:
            original_prompt = summary.get('original_prompt_tokens', summary['total_prompt_tokens'])
            console.print(f"[dim]  (原始输入: {original_prompt} tokens, 缓存: {summary['total_cached_tokens']} tokens)[/dim]")
        
        # 按模型显示
        if summary['by_model']:
            console.print(f"\n{_('token_usage_by_model')}")
            for model, model_stats in summary['by_model'].items():
                console.print(_('token_usage_model_detail',
                              model=model,
                              total=model_stats['total_tokens'],
                              calls=model_stats['calls']))
                # 如果有缓存，显示缓存信息
                if model_stats.get('cached_tokens', 0) > 0:
                    console.print(f"[dim]    缓存: {model_stats['cached_tokens']} tokens[/dim]")
        
        
        console.print()  # 空行
    
    def _handle_database_command(self):
        """处理数据库连接命令"""
        # 显示数据库连接帮助信息
        db_help_text = f"""
[bold]{_('database_help_title', default='数据库连接帮助')}:[/bold]

{_('database_help_intro', default='使用以下格式提供数据库连接信息：')}

[bold]{_('database_help_direct', default='直接连接')}:[/bold]
  host port user password database_name

[bold]{_('database_help_ssh', default='SSH隧道连接')}:[/bold]
  host port user password database_name ssh_host ssh_user ssh_key_path [ssh_port]

[bold]{_('database_help_examples', default='示例')}:[/bold]
  [dim]# 直接连接到本地MySQL[/dim]
  localhost 3306 root mypassword mydb
  
  [dim]# 通过SSH隧道连接[/dim]
  localhost 3306 root mypassword mydb bastion.com ec2-user ~/.ssh/key.pem
  
  [dim]# 指定SSH端口[/dim]
  localhost 3306 root mypassword mydb bastion.com ec2-user ~/.ssh/key.pem 2222

[bold]{_('database_help_saved', default='保存的连接')}:[/bold]
  {_('database_help_list_saved', default='查看保存的连接：发送 "列出保存的数据库连接"')}
  {_('database_help_load_saved', default='加载保存的连接：发送 "加载连接 <别名>"')}
"""
        console.print(db_help_text)
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = f"""
[bold]{_('help_title')}:[/bold]
  /help        - {_('help_hint')}
  /exit, /quit - {_('help_exit')}
  /clear       - {_('help_clear')}
  /debug <0-5> - {_('help_debug')}
  /lang [code] - {_('help_lang')}
  /model [name]- {_('help_model')}
  /token       - {_('help_token')}
  /database    - {_('help_database', default='数据库连接帮助')}
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
        log_info("CLI", "=== _continue_after_confirmation START ===")
        
        # 获取当前模型
        current_model = os.environ.get(ENV_VARS['MODEL'], 'gemini-2.5-flash')
        log_info("CLI", f"Current model: {current_model}")
        
        # 只对需要严格消息配对的模型进行特殊处理
        model_lower = current_model.lower()
        needs_strict_pairing = any(model in model_lower for model in ['gpt', 'claude', 'openai', 'sonnet'])
        
        if needs_strict_pairing:
            log_info("CLI", f"Model {current_model} needs strict message pairing, using polling approach")
            
            # 对GPT/Claude模型使用轮询确保工具真正完成
            max_wait = 5.0  # 最多等待5秒
            poll_interval = 0.1  # 每100ms检查一次
            waited = 0
            
            log_info("CLI", f"Starting polling for tool completion (max {max_wait}s)...")
            
            while waited < max_wait:
                # 检查是否还有未完成的工具
                active_tools = [
                    call for call in self.client.tool_scheduler.tool_calls
                    if call.status in ['scheduled', 'executing', 'validating']
                ]
                
                if not active_tools:
                    log_info("CLI", f"All tools completed after {waited:.1f}s")
                    break
                    
                log_info("CLI", f"Still have {len(active_tools)} active tools, waiting...")
                await asyncio.sleep(poll_interval)
                waited += poll_interval
            
            if waited >= max_wait:
                log_info("CLI", f"Warning: Polling timeout after {max_wait}s, proceeding anyway")
        else:
            # Gemini等模型保持原有逻辑
            wait_time = self._get_model_wait_time(current_model)
            log_info("CLI", f"Wait time for {current_model}: {wait_time}s")
            log_info("CLI", f"Starting wait for tool completion...")
            await asyncio.sleep(wait_time)
        
        log_info("CLI", f"Wait completed, proceeding to send 'Please continue.'")
        
        # 显示继续处理的提示
        console.print(f"\n[dim]{_('continuing')}[/dim]")
        
        # 发送继续消息让AI继续处理
        try:
            # 继续处理时不重置信号（保持中止状态）
            self.in_response = True  # 标记开始接收响应
            tool_calls = []  # 记录工具调用
            
            log_info("CLI", "Sending 'Please continue.' to AI")
            
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
    
    def _get_model_wait_time(self, model_name: str) -> float:
        """
        根据模型类型返回合适的等待时间
        
        Args:
            model_name: 模型名称
            
        Returns:
            等待时间（秒）
        """
        model_lower = model_name.lower()
        
        # 模型特性配置 - 易于扩展和维护
        model_features = {
            # 需要严格消息配对的模型需要更长等待时间
            'claude': 1.5,
            'gpt': 1.5,
            'openai': 1.5,
            # Gemini 等支持灵活消息格式的模型使用较短等待时间
            'gemini': 0.5,
            # 默认值
            'default': 0.5
        }
        
        # 匹配模型类型
        for model_prefix, wait_time in model_features.items():
            if model_prefix in model_lower:
                return wait_time
                
        return model_features['default']
    
    def cleanup(self):
        """清理资源"""
        log_info("CLI", "Cleaning up resources...")
        
        # 设置运行标志
        self.running = False
        
        # 显示 token 统计（如果有的话）
        if hasattr(self, 'client') and hasattr(self.client, 'token_statistics'):
            summary = self.client.token_statistics.get_summary()
            if summary['total_calls'] > 0:
                # 在退出前显示统计
                console.print()  # 空行
                self._show_token_statistics(self.client.token_statistics)
        
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
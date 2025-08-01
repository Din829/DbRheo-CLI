#!/usr/bin/env python3
"""
DbRheo CLI 主入口
保持专业、简洁、可靠的设计原则
"""

import os
import sys
import signal
import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

# 设置默认调试级别，如果环境变量中没有设置的话
if 'DBRHEO_DEBUG_LEVEL' not in os.environ:
    os.environ['DBRHEO_DEBUG_LEVEL'] = 'ERROR'
if 'DBRHEO_DEBUG_VERBOSITY' not in os.environ:
    os.environ['DBRHEO_DEBUG_VERBOSITY'] = 'MINIMAL'

# 添加src到Python路径（开发时需要）
sys.path.insert(0, str(Path(__file__).parent.parent))

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    # 支持多个可能的.env文件位置，注意大小写变化
    current_file = Path(__file__).resolve()
    base_paths = [
        current_file.parent.parent.parent.parent.parent,  # 向上5级到gemini-cli目录
        current_file.parent.parent.parent.parent,  # 向上4级
        current_file.parent.parent.parent,  # CLI包目录
        Path.cwd(),  # 当前工作目录
    ]
    
    # 尝试不同的目录名称组合
    for base in base_paths:
        for dirname in ["DbRheo", "Dbrheo", "dbrheo"]:
            env_path = base / "学习中" / dirname / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                print(f"[INFO] Loaded .env from: {env_path}")
                break
        # 也尝试直接在base目录下
        env_path = base / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Loaded .env from: {env_path}")
            break
except ImportError:
    # 如果没有安装python-dotenv，继续运行
    pass

from dbrheo_cli.app.cli import DbRheoCLI
from dbrheo_cli.app.config import CLIConfig
from dbrheo_cli.i18n import _
from dbrheo_cli.constants import ENV_VARS, DEFAULTS, DEBUG_LEVEL_RANGE
from dbrheo.utils.debug_logger import DebugLogger, log_info


# 全局控制台实例
console = Console()


def setup_signal_handlers(cli: DbRheoCLI):
    """设置信号处理器，确保优雅退出"""
    def signal_handler(signum, frame):
        log_info("Main", _('signal_received', signum=signum))
        # 立即设置退出标志
        cli.running = False
        
        # 中止所有操作
        if hasattr(cli, 'signal') and cli.signal:
            cli.signal.abort()
        
        # 强制退出事件循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except:
            pass
        
        # 如果上述方法都不行，强制退出
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def setup_environment():
    """从环境变量读取配置"""
    # DEBUG模式 - DebugLogger通过环境变量读取，这里只是确保环境变量设置正确
    if ENV_VARS['DEBUG_LEVEL'] not in os.environ:
        os.environ[ENV_VARS['DEBUG_LEVEL']] = DEFAULTS['DEBUG_LEVEL']
    
    # DEBUG详细程度
    if ENV_VARS['DEBUG_VERBOSITY'] not in os.environ:
        os.environ[ENV_VARS['DEBUG_VERBOSITY']] = DEFAULTS['DEBUG_VERBOSITY']
    
    # 实时日志
    if os.environ.get(ENV_VARS['ENABLE_LOG'], '').lower() == 'true':
        # 日志已通过环境变量启用，无需额外操作
        log_info("Main", "Realtime logging enabled via environment")


@click.command()
@click.option('--db-file', 
              help='数据库文件路径，默认使用内存数据库',
              type=click.Path())
@click.option('--log', 
              is_flag=True,
              help='启用实时日志输出')
@click.option('--debug', 
              type=click.IntRange(*DEBUG_LEVEL_RANGE),
              help='设置调试级别 (0-5)')
@click.option('--no-color',
              is_flag=True,
              help='禁用彩色输出')
@click.option('--config',
              type=click.Path(exists=True),
              help='配置文件路径')
@click.option('--model',
              help='选择AI模型 (例如: gemini, claude-3.5-sonnet, gpt-4.1)')
def main(db_file: Optional[str], 
         log: bool, 
         debug: Optional[int],
         no_color: bool,
         config: Optional[str],
         model: Optional[str]):
    """
    DbRheo CLI - 数据库智能助手
    
    专业、简洁、可靠的数据库操作界面
    """
    # 设置环境变量配置
    setup_environment()
    
    # 命令行参数覆盖环境变量
    if debug is not None:
        # 将数字转换为日志级别名称
        level_map = {0: 'ERROR', 1: 'WARNING', 2: 'INFO', 3: 'DEBUG', 4: 'DEBUG', 5: 'DEBUG'}
        debug_level = level_map.get(debug, 'INFO')
        os.environ[ENV_VARS['DEBUG_LEVEL']] = debug_level
        # 重新导入debug_logger模块以应用新的日志级别
        import importlib
        import dbrheo.utils.debug_logger
        importlib.reload(dbrheo.utils.debug_logger)
        log_info("Main", _('debug_level_set', level=debug))
    
    if log:
        os.environ[ENV_VARS['ENABLE_LOG']] = 'true'
        log_info("Main", _('log_enabled'))
    
    # 设置模型
    if model:
        os.environ[ENV_VARS['MODEL']] = model
        log_info("Main", _('model_switched', model=model))
    
    # 创建CLI配置
    cli_config = CLIConfig(
        db_file=db_file,
        no_color=no_color,
        config_file=config
    )
    
    # 创建并运行CLI
    try:
        cli = DbRheoCLI(cli_config)
        setup_signal_handlers(cli)
        
        # 显示启动画面
        from dbrheo_cli.ui.startup import StartupScreen
        startup = StartupScreen(cli_config, console)
        
        # 检查是否在主目录运行（类似 Gemini CLI）
        custom_message = None
        if os.path.expanduser("~") == os.getcwd():
            custom_message = _('home_dir_warning')
            
        # 显示完整启动画面
        startup.display(
            version="0.1.0",
            show_tips=True,
            custom_message=custom_message,
            logo_style="default"  # 使用默认大号版本
        )
        
        # 运行主循环
        asyncio.run(cli.run())
        
        # 确保清理资源
        cli.cleanup()
        
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{_('user_interrupt')}[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]{_('error_occurred', error=e)}[/red]")
        if DebugLogger.should_log("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
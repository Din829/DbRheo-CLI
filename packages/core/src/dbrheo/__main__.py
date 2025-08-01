"""
应用启动入口 - 支持多种启动方式
可以作为模块运行：python -m dbrheo
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加当前包到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量文件
def load_env_file():
    """加载.env文件中的环境变量"""
    env_paths = [
        Path.cwd() / '.env',  # 当前工作目录
        Path(__file__).parent.parent.parent.parent.parent / '.env',  # 项目根目录
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            print(f"Loading environment from: {env_path}")
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 只设置未设置的环境变量
                        if key not in os.environ:
                            os.environ[key] = value
            break
    else:
        print("Warning: No .env file found")

# 在导入其他模块前加载环境变量
load_env_file()

from dbrheo.config.base import DatabaseConfig
from dbrheo.api.app import create_app


def setup_logging(level: str = "INFO"):
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("dbrheo.log")
        ]
    )


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DbRheo - 智能数据库Agent")
    parser.add_argument("--host", default="localhost", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="开发模式（自动重载）")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    
    args = parser.parse_args()
    
    # 如果环境变量中设置了 DEBUG=true，自动启用 reload
    if not args.reload and os.getenv('DBRHEO_DEBUG', '').lower() == 'true':
        args.reload = True
        print("Debug mode detected, enabling auto-reload")
    
    # 设置日志
    setup_logging(args.log_level)
    
    # 启动服务器
    try:
        import uvicorn
        
        # 如果启用了 reload，必须使用字符串格式的应用路径
        if args.reload:
            uvicorn.run(
                "dbrheo.api.app:app",  # 模块路径字符串
                host=args.host,
                port=args.port,
                reload=True,
                reload_dirs=["packages/core/src"],  # 监控的目录
                log_level=args.log_level.lower()
            )
        else:
            # 不使用 reload 时，可以直接传递应用对象
            app = create_app()
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                reload=False,
                log_level=args.log_level.lower()
            )
    except ImportError:
        print("Error: uvicorn not installed. Please install with: pip install uvicorn")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down DbRheo server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

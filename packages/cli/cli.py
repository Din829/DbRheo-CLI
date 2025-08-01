#!/usr/bin/env python3
"""
DbRheo CLI快速启动脚本

用于开发时快速启动CLI，不需要安装。
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 添加core包路径
core_path = Path(__file__).parent.parent / "core" / "src"
if str(core_path) not in sys.path:
    sys.path.insert(0, str(core_path))

if __name__ == "__main__":
    from dbrheo_cli.main import main
    main()
#!/usr/bin/env python3
"""
DbRheo CLI快速启动脚本

用于开发时快速启动CLI，不需要安装。
"""

import sys
import os
from pathlib import Path

# 创建一个过滤的stderr包装器
class FilteredStderr:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        
    def write(self, text):
        # 过滤掉特定的警告
        if "there are non-text parts in the response" not in text:
            self.original_stderr.write(text)
    
    def flush(self):
        self.original_stderr.flush()
        
    def __getattr__(self, name):
        return getattr(self.original_stderr, name)

# 替换标准错误输出
sys.stderr = FilteredStderr(sys.stderr)

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
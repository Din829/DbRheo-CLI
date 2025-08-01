#!/usr/bin/env python3
"""
增强布局功能设置脚本
用于安装依赖和测试功能
"""

import os
import sys
import subprocess
import importlib.util

def check_dependency(package_name):
    """检查依赖是否已安装"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def install_dependency(package_name):
    """安装依赖包"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("DbRheo CLI 增强布局功能设置")
    print("=" * 40)
    
    # 检查prompt-toolkit
    if check_dependency('prompt_toolkit'):
        print("✓ prompt-toolkit 已安装")
    else:
        print("✗ prompt-toolkit 未安装，正在安装...")
        if install_dependency('prompt-toolkit>=3.0.43'):
            print("✓ prompt-toolkit 安装成功")
        else:
            print("✗ prompt-toolkit 安装失败")
            print("请手动运行: pip install prompt-toolkit>=3.0.43")
            sys.exit(1)
    
    # 设置环境变量
    print("\n配置增强布局...")
    os.environ['DBRHEO_ENHANCED_LAYOUT'] = 'true'
    print("✓ 已启用增强布局模式")
    
    print("\n环境变量配置:")
    print("DBRHEO_ENHANCED_LAYOUT=true     # 启用增强布局")
    print("DBRHEO_INPUT_HEIGHT_MIN=3       # 输入框最小高度") 
    print("DBRHEO_INPUT_HEIGHT_MAX=10      # 输入框最大高度")
    print("DBRHEO_AUTO_SCROLL=true         # 自动滚动")
    print("DBRHEO_SHOW_SEPARATOR=true      # 显示分隔线")
    
    print("\n要启用增强布局，请在运行CLI前设置环境变量:")
    print("Windows: set DBRHEO_ENHANCED_LAYOUT=true")
    print("Linux/Mac: export DBRHEO_ENHANCED_LAYOUT=true")
    
    print("\n测试增强布局...")
    try:
        # 导入测试
        from src.dbrheo_cli.ui.layout_manager import create_layout_manager, LayoutConfig
        from src.dbrheo_cli.app.config import CLIConfig
        
        # 创建测试配置
        config = CLIConfig()
        config.enhanced_layout = True
        
        # 测试布局管理器
        manager = create_layout_manager(config)
        if manager and manager.is_available():
            print("✓ 增强布局管理器可用")
            print("✓ prompt-toolkit 集成正常")
            print("\n🎉 增强布局功能设置完成！")
            print("\n现在可以运行 CLI 并体验底部固定输入框功能")
        else:
            print("✗ 增强布局管理器不可用")
            
            # 调试信息
            layout_config = LayoutConfig.from_env()
            print(f"调试: enabled={layout_config.enabled}")
            print(f"调试: prompt-toolkit可用={check_dependency('prompt_toolkit')}")
            
    except ImportError as e:
        print(f"✗ 导入错误: {e}")
        print("请确保在正确的目录运行此脚本")

if __name__ == '__main__':
    main()
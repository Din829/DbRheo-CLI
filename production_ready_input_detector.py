#!/usr/bin/env python3
"""
生产就绪的跨平台输入缓冲区检测器
基于研究结果的最佳实践实现
"""

import sys
import platform
import os
from typing import List, Optional, Tuple
import time


class ProductionInputDetector:
    """
    生产环境使用的输入检测器
    
    特点:
    1. 跨平台兼容
    2. 可靠的错误处理
    3. 不消耗数据
    4. 保守但实用的策略
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.platform_info = self._detect_platform()
        self.detection_method = self._select_detection_method()
        
        if self.debug:
            print(f"[DEBUG] 平台: {self.platform_info}")
            print(f"[DEBUG] 选择方法: {self.detection_method}")
    
    def _detect_platform(self) -> dict:
        """检测平台信息"""
        info = {
            'system': platform.system(),
            'is_windows': platform.system() == 'Windows',
            'is_wsl': False,
            'is_tty': sys.stdin.isatty()
        }
        
        # 检测WSL
        try:
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        info['is_wsl'] = True
        except:
            pass
            
        return info
    
    def _select_detection_method(self) -> str:
        """选择最适合的检测方法"""
        if self.platform_info['is_windows']:
            # Windows平台
            try:
                import msvcrt
                return 'msvcrt'
            except ImportError:
                return 'heuristic'
        else:
            # Unix-like平台
            try:
                import select
                if hasattr(select, 'select') and self.platform_info['is_tty']:
                    return 'select'
            except ImportError:
                pass
            return 'heuristic'
    
    def has_pending_input(self, timeout: float = 0.05) -> bool:
        """
        检测是否有待处理的输入
        
        Args:
            timeout: 检测超时时间（秒）
            
        Returns:
            bool: 是否有待处理的输入
        """
        try:
            if self.detection_method == 'msvcrt':
                return self._check_with_msvcrt()
            elif self.detection_method == 'select':
                return self._check_with_select(timeout)
            else:
                return False  # 启发式方法不做实时检测
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 检测异常: {e}")
            return False
    
    def _check_with_msvcrt(self) -> bool:
        """使用msvcrt检测（Windows）"""
        try:
            import msvcrt
            return msvcrt.kbhit()
        except Exception:
            return False
    
    def _check_with_select(self, timeout: float) -> bool:
        """使用select检测（Unix）"""
        try:
            import select
            
            # WSL环境使用稍长的超时
            if self.platform_info['is_wsl']:
                timeout = max(timeout, 0.1)
            
            readable, _, _ = select.select([sys.stdin], [], [], timeout)
            return bool(readable)
        except Exception:
            return False
    
    def collect_multiline_paste(self, first_line: str, 
                              max_wait: float = 0.5,
                              min_lines_for_detection: int = 2) -> Tuple[bool, List[str]]:
        """
        收集粘贴的多行内容
        
        Args:
            first_line: 第一行内容
            max_wait: 最长等待时间
            min_lines_for_detection: 最少行数才认为是粘贴
            
        Returns:
            Tuple[bool, List[str]]: (是否检测到多行, 所有行的列表)
        """
        lines = [first_line]
        
        if self.detection_method == 'heuristic':
            # 启发式方法：不做实时检测，直接返回
            return False, lines
        
        start_time = time.time()
        check_interval = 0.01  # 10ms检查间隔
        consecutive_empty_checks = 0
        max_consecutive_empty = 3  # 连续3次无输入则停止
        
        while time.time() - start_time < max_wait:
            if self.has_pending_input(check_interval):
                try:
                    line = sys.stdin.readline()
                    if line:
                        lines.append(line.rstrip('\n\r'))
                        consecutive_empty_checks = 0  # 重置计数器
                        
                        if self.debug:
                            print(f"[DEBUG] 收集到第{len(lines)}行")
                    else:
                        break
                except Exception as e:
                    if self.debug:
                        print(f"[DEBUG] 读取异常: {e}")
                    break
            else:
                consecutive_empty_checks += 1
                if consecutive_empty_checks >= max_consecutive_empty and len(lines) > 1:
                    # 已经有多行内容且连续无输入，可以结束了
                    break
                time.sleep(check_interval)
        
        is_multiline = len(lines) >= min_lines_for_detection
        
        if self.debug and is_multiline:
            print(f"[DEBUG] 检测到{len(lines)}行粘贴内容")
        
        return is_multiline, lines


class SmartMultilineInput:
    """
    智能多行输入处理器
    结合自动检测和手动模式
    """
    
    def __init__(self, debug: bool = False):
        self.detector = ProductionInputDetector(debug)
        self.debug = debug
    
    def get_input(self, prompt: str = "> ") -> str:
        """
        智能获取输入
        
        策略:
        1. 检查显式多行标记
        2. 尝试自动检测粘贴
        3. 根据内容特征提示用户
        """
        # 读取第一行
        first_line = input(prompt).rstrip()
        
        if self.debug:
            print(f"[DEBUG] 第一行: {repr(first_line)}")
        
        # 1. 检查显式多行标记
        if self._is_explicit_multiline_marker(first_line):
            return self._handle_explicit_multiline(first_line)
        
        # 2. 尝试自动检测粘贴
        is_paste, all_lines = self.detector.collect_multiline_paste(first_line)
        if is_paste:
            return '\n'.join(all_lines)
        
        # 3. 检查内容特征，提示用户
        if self._might_be_multiline(first_line):
            return self._prompt_for_continuation(first_line)
        
        # 4. 单行输入
        return first_line
    
    def _is_explicit_multiline_marker(self, line: str) -> bool:
        """检查是否有显式的多行标记"""
        markers = ['```', '<<<', '"""', "'''"]
        stripped = line.strip()
        return (stripped in markers or 
                line.endswith('\\') or 
                stripped == '\\')
    
    def _handle_explicit_multiline(self, first_line: str) -> str:
        """处理显式多行标记"""
        stripped = first_line.strip()
        
        if stripped in ['```', '<<<', '"""', "'''"]:
            # 代码块模式
            print(f"[多行模式] 输入 {stripped} 结束")
            lines = []
            
            while True:
                try:
                    line = input("... ")
                    if line.strip() == stripped:
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            
            return '\n'.join(lines)
        
        elif first_line.endswith('\\') or stripped == '\\':
            # 续行模式
            lines = []
            if stripped != '\\':
                lines.append(first_line[:-1].rstrip())
            
            print("[续行模式] 空行结束")
            
            while True:
                try:
                    line = input("... ")
                    if not line.strip():
                        break
                    
                    if line.endswith('\\'):
                        lines.append(line[:-1].rstrip())
                    else:
                        lines.append(line)
                        
                except (EOFError, KeyboardInterrupt):
                    break
            
            return '\n'.join(lines)
        
        return first_line
    
    def _might_be_multiline(self, line: str) -> bool:
        """判断内容是否可能需要多行"""
        # SQL语句
        sql_starters = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'WITH', 'ALTER']
        upper_line = line.strip().upper()
        for starter in sql_starters:
            if upper_line.startswith(starter + ' ') and not line.rstrip().endswith(';'):
                return True
        
        # 未闭合的结构
        open_chars = {'(': ')', '[': ']', '{': '}'}
        stack = []
        in_string = False
        string_char = None
        
        for char in line:
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    string_char = char
                elif char in open_chars:
                    stack.append(char)
                elif char in open_chars.values():
                    if stack:
                        stack.pop()
            else:
                if char == string_char:
                    in_string = False
        
        return len(stack) > 0 or in_string
    
    def _prompt_for_continuation(self, first_line: str) -> str:
        """提示用户是否继续输入"""
        print(f"[提示] 检测到可能的多行内容")
        print("继续输入更多行吗？(y/N/auto)")
        print("  y: 手动多行模式")
        print("  N: 就是单行(默认)")
        print("  auto: 自动检测模式")
        
        choice = input("选择: ").lower().strip()
        
        if choice == 'y':
            return self._manual_continuation(first_line)
        elif choice == 'auto':
            # 给更长时间检测粘贴
            is_paste, all_lines = self.detector.collect_multiline_paste(
                first_line, max_wait=1.0
            )
            return '\n'.join(all_lines)
        else:
            return first_line
    
    def _manual_continuation(self, first_line: str) -> str:
        """手动续行模式"""
        lines = [first_line]
        print("[手动多行] 空行结束")
        
        while True:
            try:
                line = input("... ")
                if not line.strip():
                    break
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break
        
        return '\n'.join(lines)


# 使用示例和测试
def demo():
    """演示用法"""
    print("生产就绪的多行输入检测器")
    print("=" * 50)
    
    # 创建检测器（开启调试）
    smart_input = SmartMultilineInput(debug=True)
    
    print("\n功能说明:")
    print("1. 自动检测粘贴的多行内容")
    print("2. 支持 ```、<<<、\\等显式多行标记")
    print("3. 智能识别SQL等可能的多行内容")
    print("4. 跨平台兼容")
    print("\n输入 'exit' 退出")
    
    while True:
        try:
            print()
            result = smart_input.get_input("💬 你: ")
            
            if result.lower() == 'exit':
                break
            
            print("\n📝 接收到的完整内容:")
            print("-" * 40)
            print(result)
            print("-" * 40)
            
            # 显示统计信息
            lines = result.split('\n')
            print(f"📊 统计: {len(lines)}行, {len(result)}字符")
            
        except KeyboardInterrupt:
            print("\n\n👋 再见!")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    demo()
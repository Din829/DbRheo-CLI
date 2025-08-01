#!/usr/bin/env python3
"""
修复后的多行输入实现
解决粘贴内容丢失和意外执行的问题
"""

import sys
import select
import termios
import tty
import time
from typing import List, Tuple, Optional

class FixedMultilineInput:
    """
    修复的多行输入处理器
    主要改进：
    1. 更可靠的粘贴检测
    2. 避免内容丢失
    3. 更好的WSL兼容性
    """
    
    def __init__(self, paste_timeout=0.1, max_paste_wait=0.5):
        self.paste_timeout = paste_timeout
        self.max_paste_wait = max_paste_wait
        self.is_wsl = self._detect_wsl()
        
    def _detect_wsl(self) -> bool:
        """检测是否在WSL环境中"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def get_input_with_paste_detection(self, prompt: str = "> ") -> str:
        """
        获取输入，智能检测粘贴的多行内容
        
        核心改进：
        1. 使用更长的初始等待时间
        2. 多次检查确保不丢失内容
        3. WSL特殊处理
        """
        # 保存终端设置
        if sys.stdin.isatty():
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                # 设置为原始模式可能有助于检测
                tty.setcbreak(sys.stdin.fileno())
            except:
                pass
        else:
            old_settings = None
        
        try:
            # 先恢复正常模式读取第一行
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
            # 打印提示并获取第一行
            print(prompt, end='', flush=True)
            first_line = sys.stdin.readline().rstrip('\n\r')
            
            # 立即检查是否有更多内容
            additional_lines = self._collect_paste_lines()
            
            if additional_lines:
                all_lines = [first_line] + additional_lines
                print(f"[检测到{len(all_lines)}行粘贴内容]")
                return '\n'.join(all_lines)
            
            return first_line
            
        finally:
            # 恢复终端设置
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def _collect_paste_lines(self) -> List[str]:
        """
        收集粘贴的额外行
        使用多种策略确保不丢失内容
        """
        lines = []
        total_wait = 0
        
        # WSL环境下可能需要更长的等待时间
        timeout = self.paste_timeout * 2 if self.is_wsl else self.paste_timeout
        
        while total_wait < self.max_paste_wait:
            if self._has_pending_input(timeout):
                # 有待读取的内容
                try:
                    line = sys.stdin.readline()
                    if line:
                        lines.append(line.rstrip('\n\r'))
                        # 重置等待时间，因为刚读到内容
                        total_wait = 0
                    else:
                        break
                except:
                    break
            else:
                # 没有检测到输入
                total_wait += timeout
                
                # 如果已经读到一些行，再等待一下
                if lines and total_wait < self.max_paste_wait / 2:
                    continue
                else:
                    break
        
        return lines
    
    def _has_pending_input(self, timeout: float) -> bool:
        """
        检查是否有待读取的输入
        改进的检测方法
        """
        if not hasattr(select, 'select'):
            return False
        
        try:
            # 使用select检查
            readable, _, _ = select.select([sys.stdin], [], [], timeout)
            return bool(readable)
        except:
            # select失败，尝试其他方法
            return self._alternative_input_check()
    
    def _alternative_input_check(self) -> bool:
        """
        备选的输入检查方法
        用于select不可用的情况
        """
        try:
            # 尝试使用非阻塞读取
            import fcntl
            import os
            
            # 获取当前标志
            flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
            # 设置非阻塞
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            try:
                # 尝试读取一个字符
                char = sys.stdin.read(1)
                if char:
                    # 有内容，放回去
                    sys.stdin = io.StringIO(char + sys.stdin.read())
                    return True
                return False
            finally:
                # 恢复阻塞模式
                fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags)
        except:
            return False


class RobustMultilineHandler:
    """
    最可靠的多行处理方案
    使用缓冲区管理避免内容丢失
    """
    
    def __init__(self):
        self.buffer = []
        self.paste_mode = False
        
    def get_multiline_input(self, prompt: str = "> ") -> str:
        """
        获取可能的多行输入
        使用更保守的策略
        """
        # 如果缓冲区有内容，先处理缓冲区
        if self.buffer:
            line = self.buffer.pop(0)
            print(f"{prompt}{line}")
            return line
        
        # 获取第一行
        first_line = input(prompt)
        
        # 快速连续读取检测粘贴
        lines = [first_line]
        
        # 给一个短暂的时间窗口收集粘贴内容
        import time
        start_time = time.time()
        timeout = 0.05  # 50ms
        
        while time.time() - start_time < timeout:
            if self._can_read_immediately():
                try:
                    line = input()
                    lines.append(line)
                except:
                    break
            else:
                # 稍等一下再检查
                time.sleep(0.01)
        
        if len(lines) > 1:
            # 检测到多行粘贴
            print(f"[检测到{len(lines)}行内容]")
            return '\n'.join(lines)
        
        # 检查是否是手动多行
        if first_line.strip() in ['```', '<<<'] or first_line.endswith('\\'):
            return self._manual_multiline(first_line)
        
        return first_line
    
    def _can_read_immediately(self) -> bool:
        """检查是否可以立即读取（有缓冲内容）"""
        if hasattr(select, 'select'):
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0)
                return bool(r)
            except:
                pass
        return False
    
    def _manual_multiline(self, first_line: str) -> str:
        """手动多行模式"""
        lines = []
        
        if first_line.strip() in ['```', '<<<']:
            marker = first_line.strip()
            print(f"多行模式，输入 {marker} 结束")
            
            while True:
                line = input("... ")
                if line.strip() == marker:
                    break
                lines.append(line)
        else:
            # 续行模式
            lines = [first_line[:-1] if first_line.endswith('\\') else first_line]
            print("续行模式，空行结束")
            
            while True:
                line = input("... ")
                if not line.strip():
                    break
                if line.endswith('\\'):
                    lines.append(line[:-1])
                else:
                    lines.append(line)
        
        return '\n'.join(lines)


# 测试脚本
if __name__ == "__main__":
    print("修复的多行输入测试")
    print("="*50)
    print("请尝试粘贴多行内容，或使用 ``` 进入多行模式")
    print("="*50)
    
    # 选择测试哪个实现
    if '--robust' in sys.argv:
        handler = RobustMultilineHandler()
        get_input = handler.get_multiline_input
    else:
        handler = FixedMultilineInput()
        get_input = handler.get_input_with_paste_detection
    
    while True:
        try:
            result = get_input("\n💬 你: ")
            
            print("\n完整输入：")
            print("-"*30)
            print(result)
            print("-"*30)
            
            if result.lower() == 'exit':
                break
                
        except KeyboardInterrupt:
            print("\n退出")
            break
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
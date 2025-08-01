#!/usr/bin/env python3
"""
多行输入最终解决方案
结合多种策略，提供最可靠的体验
"""

import sys
import select
import time
import os
from typing import List, Optional, Tuple
import asyncio

class MultilineInputSolution:
    """
    综合性的多行输入解决方案
    
    特性：
    1. 智能粘贴检测（多策略）
    2. 手动多行模式
    3. 内容特征识别
    4. WSL优化
    """
    
    def __init__(self, config=None):
        # 配置选项
        self.paste_timeout = float(os.getenv('DBRHEO_PASTE_TIMEOUT', '0.1'))
        self.paste_detection = os.getenv('DBRHEO_PASTE_DETECTION', 'true').lower() == 'true'
        self.smart_detection = os.getenv('DBRHEO_SMART_DETECTION', 'true').lower() == 'true'
        self.debug = os.getenv('DBRHEO_DEBUG_INPUT', 'false').lower() == 'true'
        
        # 检测环境
        self.is_wsl = self._detect_wsl()
        self.supports_select = hasattr(select, 'select') and sys.stdin.isatty()
        
        if self.debug:
            print(f"[DEBUG] WSL: {self.is_wsl}, select: {self.supports_select}")
    
    def _detect_wsl(self) -> bool:
        """检测WSL环境"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def get_input(self, prompt: str = "> ") -> str:
        """
        主输入方法，自动选择最佳策略
        """
        # 打印提示
        print(prompt, end='', flush=True)
        
        # 读取第一行
        try:
            first_line = sys.stdin.readline().rstrip('\n\r')
        except KeyboardInterrupt:
            print()  # 换行
            raise
        
        if self.debug:
            print(f"\n[DEBUG] 第一行: {repr(first_line)}")
        
        # 策略1：检查显式多行标记
        if self._is_explicit_multiline(first_line):
            return self._handle_explicit_multiline(first_line)
        
        # 策略2：智能内容检测
        if self.smart_detection and self._looks_like_multiline(first_line):
            continuation = self._try_collect_continuation(first_line)
            if continuation:
                return continuation
        
        # 策略3：粘贴检测（如果启用且支持）
        if self.paste_detection and self.supports_select:
            paste_result = self._try_paste_detection(first_line)
            if paste_result:
                return paste_result
        
        # 默认：返回单行
        return first_line
    
    def _is_explicit_multiline(self, line: str) -> bool:
        """检查是否有显式的多行标记"""
        stripped = line.strip()
        return (
            stripped in ['```', '<<<', '"""', "'''"] or
            line.endswith('\\') or
            stripped == '\\'
        )
    
    def _looks_like_multiline(self, line: str) -> bool:
        """基于内容判断是否可能是多行"""
        # SQL语句通常是多行
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'WITH']
        upper_line = line.strip().upper()
        for keyword in sql_keywords:
            if upper_line.startswith(keyword + ' '):
                return not line.rstrip().endswith(';')
        
        # 未闭合的括号/引号
        if self._has_unclosed_delimiters(line):
            return True
        
        # JSON/字典开始
        if line.strip() in ['{', '['] or line.strip().endswith('{') or line.strip().endswith('['):
            return True
        
        return False
    
    def _has_unclosed_delimiters(self, line: str) -> bool:
        """检查未闭合的定界符"""
        stack = []
        in_string = False
        string_char = None
        escaped = False
        
        for char in line:
            if escaped:
                escaped = False
                continue
                
            if char == '\\':
                escaped = True
                continue
            
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    string_char = char
                elif char in '([{':
                    stack.append(char)
                elif char in ')]}':
                    if not stack:
                        continue
                    stack.pop()
            else:
                if char == string_char:
                    in_string = False
        
        return len(stack) > 0 or in_string
    
    def _try_paste_detection(self, first_line: str) -> Optional[str]:
        """尝试检测粘贴的多行内容"""
        lines = [first_line]
        
        # WSL环境下使用更长的超时
        timeout = self.paste_timeout * 2 if self.is_wsl else self.paste_timeout
        max_attempts = 5  # 最多尝试5次
        
        for attempt in range(max_attempts):
            try:
                readable, _, _ = select.select([sys.stdin], [], [], timeout)
                if not readable:
                    # 没有更多输入
                    if attempt > 0:  # 至少检测到过一次
                        time.sleep(0.01)  # 再等一下
                        continue
                    break
                
                # 读取可用的行
                line = sys.stdin.readline()
                if line:
                    lines.append(line.rstrip('\n\r'))
                    timeout = 0.01  # 后续使用更短的超时
                else:
                    break
                    
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] select错误: {e}")
                break
        
        if len(lines) > 1:
            if self.debug:
                print(f"[DEBUG] 检测到{len(lines)}行粘贴")
            return '\n'.join(lines)
        
        return None
    
    def _try_collect_continuation(self, first_line: str) -> Optional[str]:
        """尝试收集续行内容"""
        print("[检测到可能的多行内容，继续输入，空行结束]")
        
        lines = [first_line]
        
        while True:
            try:
                line = input("... ")
                
                # 空行结束
                if not line.strip():
                    break
                
                lines.append(line)
                
                # 检查是否应该结束
                all_text = '\n'.join(lines)
                
                # SQL语句遇到分号结束
                if (first_line.strip().upper().split()[0] in 
                    ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'WITH'] and 
                    line.rstrip().endswith(';')):
                    break
                
                # 结构完整且没有续行符
                if not self._has_unclosed_delimiters(all_text) and not line.endswith('\\'):
                    # 询问是否继续
                    if input("继续输入？(y/N): ").lower() != 'y':
                        break
                        
            except (EOFError, KeyboardInterrupt):
                break
        
        return '\n'.join(lines) if len(lines) > 1 else None
    
    def _handle_explicit_multiline(self, first_line: str) -> str:
        """处理显式的多行输入"""
        stripped = first_line.strip()
        
        # 代码块模式
        if stripped in ['```', '<<<', '"""', "'''"]:
            print(f"[多行模式，输入 {stripped} 结束]")
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
        
        # 续行模式
        elif first_line.endswith('\\') or stripped == '\\':
            lines = []
            if stripped != '\\' and first_line.endswith('\\'):
                lines.append(first_line[:-1])
            
            print("[续行模式，空行结束]")
            
            while True:
                try:
                    line = input("... ")
                    if not line.strip():
                        break
                    
                    if line.endswith('\\'):
                        lines.append(line[:-1])
                    else:
                        lines.append(line)
                        
                except (EOFError, KeyboardInterrupt):
                    break
            
            return '\n'.join(lines)
        
        return first_line


class AsyncMultilineInput:
    """异步版本的多行输入"""
    
    def __init__(self):
        self.sync_handler = MultilineInputSolution()
    
    async def get_input(self, prompt: str = "> ") -> str:
        """异步获取输入"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_handler.get_input, prompt)


# 集成到现有系统的示例
def create_enhanced_input_handler():
    """
    创建增强的输入处理器
    可以直接替换现有的input()调用
    """
    handler = MultilineInputSolution()
    
    def enhanced_input(prompt: str = "> ") -> str:
        return handler.get_input(prompt)
    
    return enhanced_input


# 测试和演示
if __name__ == "__main__":
    print("多行输入解决方案测试")
    print("="*50)
    print("功能:")
    print("1. 自动检测粘贴的多行内容")
    print("2. 智能识别SQL等多行语句") 
    print("3. 支持 ``` 代码块和 \\ 续行")
    print("4. WSL环境优化")
    print("="*50)
    
    # 设置调试模式
    if '--debug' in sys.argv:
        os.environ['DBRHEO_DEBUG_INPUT'] = 'true'
    
    handler = MultilineInputSolution()
    
    while True:
        try:
            result = handler.get_input("\n💬 你: ")
            
            if result.lower() == 'exit':
                break
            
            print("\n收到的完整输入:")
            print("-"*40)
            print(result)
            print("-"*40)
            
            # 显示一些统计
            lines = result.split('\n')
            print(f"行数: {len(lines)}")
            print(f"字符数: {len(result)}")
            
        except KeyboardInterrupt:
            print("\n\n退出")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
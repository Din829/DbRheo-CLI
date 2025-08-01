#!/usr/bin/env python3
"""
改进的多行输入处理方案
解决粘贴内容意外执行的问题
"""

import sys
import select
import time
import asyncio
from typing import List, Optional, Tuple

class ImprovedMultilineInput:
    """
    改进的多行输入处理器
    解决粘贴时第一行立即执行的问题
    """
    
    def __init__(self, paste_timeout=0.1, debug=False):
        self.paste_timeout = paste_timeout
        self.debug = debug
        
    def get_multiline_input(self, prompt: str = "> ") -> str:
        """
        获取可能的多行输入
        
        策略：
        1. 先读取第一行
        2. 立即检查是否有后续输入（paste检测）
        3. 如果检测到多行，收集所有行
        4. 如果没有检测到，检查是否需要手动多行模式
        """
        # 获取第一行
        first_line = input(prompt)
        
        if self.debug:
            print(f"[DEBUG] 第一行: {repr(first_line)}")
        
        # 快速检查是否有更多输入（粘贴检测）
        has_more, additional_lines = self._check_for_paste()
        
        if has_more:
            # 检测到粘贴的多行内容
            all_lines = [first_line] + additional_lines
            if self.debug:
                print(f"[DEBUG] 检测到粘贴，共 {len(all_lines)} 行")
            return '\n'.join(all_lines)
        
        # 检查手动多行模式标记
        if first_line.strip() in ['```', '<<<', '\\']:
            return self._manual_multiline_mode(first_line)
        
        # 单行输入
        return first_line
    
    def _check_for_paste(self) -> Tuple[bool, List[str]]:
        """
        检查是否有粘贴的多行内容
        返回: (是否有多行, 额外的行列表)
        """
        if not hasattr(select, 'select'):
            # Windows等不支持select的系统
            return False, []
        
        additional_lines = []
        
        try:
            # 使用较长的超时时间来确保捕获所有粘贴内容
            # 多次短超时比一次长超时更可靠
            for _ in range(3):  # 尝试3次
                readable, _, _ = select.select([sys.stdin], [], [], self.paste_timeout / 3)
                
                if not readable:
                    break
                
                # 读取所有可用的行
                while True:
                    # 再次检查是否有数据（无超时）
                    readable, _, _ = select.select([sys.stdin], [], [], 0)
                    if not readable:
                        break
                    
                    # 读取一行
                    line = sys.stdin.readline()
                    if not line:
                        break
                    
                    line = line.rstrip('\n\r')
                    additional_lines.append(line)
                    
                    if self.debug:
                        print(f"[DEBUG] 读取到额外行: {repr(line)}")
            
            return len(additional_lines) > 0, additional_lines
            
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] paste检测错误: {e}")
            return False, []
    
    def _manual_multiline_mode(self, first_line: str) -> str:
        """
        手动多行输入模式
        支持 ``` 代码块或 \ 续行
        """
        lines = []
        
        if first_line.strip() in ['```', '<<<']:
            # 代码块模式
            print("进入多行模式，再次输入 ``` 或 <<< 结束")
            
            while True:
                try:
                    line = input("... ")
                    if line.strip() in ['```', '<<<']:
                        break
                    lines.append(line)
                except EOFError:
                    break
                    
        elif first_line.strip() == '\\' or first_line.endswith('\\'):
            # 续行模式
            if first_line.strip() != '\\':
                lines.append(first_line[:-1])  # 移除末尾的\
            
            print("续行模式，空行结束")
            
            while True:
                try:
                    line = input("... ")
                    if line.strip() == "":
                        break
                    if line.endswith('\\'):
                        lines.append(line[:-1])
                    else:
                        lines.append(line)
                        # 不以\结尾，可选择结束
                        if input("继续输入？(y/N): ").lower() != 'y':
                            break
                except EOFError:
                    break
        
        return '\n'.join(lines)


class AsyncMultilineInput:
    """
    异步版本的多行输入处理器
    适用于asyncio环境
    """
    
    def __init__(self, paste_timeout=0.1, debug=False):
        self.sync_handler = ImprovedMultilineInput(paste_timeout, debug)
        
    async def get_input(self, prompt: str = "> ") -> str:
        """异步获取输入"""
        loop = asyncio.get_event_loop()
        
        # 在线程池中运行同步输入操作
        result = await loop.run_in_executor(
            None,
            self.sync_handler.get_multiline_input,
            prompt
        )
        
        return result


def test_improved_input():
    """测试改进的输入处理"""
    print("测试改进的多行输入处理")
    print("="*50)
    print("提示：")
    print("1. 直接粘贴多行文本会自动识别")
    print("2. 输入 ``` 或 <<< 进入手动多行模式")
    print("3. 行尾加 \\ 续行")
    print("="*50)
    
    handler = ImprovedMultilineInput(debug=True)
    
    while True:
        try:
            result = handler.get_multiline_input("\n💬 你: ")
            
            print("\n收到的完整输入：")
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


async def test_async_input():
    """测试异步输入"""
    print("测试异步多行输入处理")
    
    handler = AsyncMultilineInput(debug=True)
    
    while True:
        try:
            result = await handler.get_input("\n💬 你: ")
            
            print("\n收到的完整输入：")
            print("-"*30)
            print(result)
            print("-"*30)
            
            if result.lower() == 'exit':
                break
                
        except KeyboardInterrupt:
            print("\n退出")
            break


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--async':
        asyncio.run(test_async_input())
    else:
        test_improved_input()
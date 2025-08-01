#!/usr/bin/env python3
"""
智能粘贴处理方案
基于内容特征而非时间检测
"""

import sys
import re
from typing import List, Optional

class SmartPasteHandler:
    """
    基于内容特征的智能粘贴处理
    不依赖select或时间检测
    """
    
    # SQL语句模式
    SQL_PATTERNS = [
        r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)\s+',
        r'^\s*(WITH|FROM|WHERE|JOIN|GROUP BY|ORDER BY|HAVING)\s+',
    ]
    
    # 代码块标记
    CODE_MARKERS = ['```', '<<<', '"""', "'''"]
    
    # JSON/对象起始
    STRUCTURE_STARTS = ['{', '[', '(']
    
    def __init__(self, debug=False):
        self.debug = debug
        self.sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_PATTERNS]
        
    def get_smart_input(self, prompt: str = "> ") -> str:
        """
        智能获取输入，自动处理多行情况
        """
        first_line = input(prompt).rstrip()
        
        # 检查是否需要多行
        if self._should_continue_input(first_line):
            return self._collect_multiline(first_line)
        
        return first_line
    
    def _should_continue_input(self, line: str) -> bool:
        """
        判断是否应该继续读取多行
        """
        line_stripped = line.strip()
        
        # 1. 显式多行标记
        if line_stripped in self.CODE_MARKERS:
            return True
        
        # 2. 续行符
        if line.endswith('\\'):
            return True
        
        # 3. SQL语句（通常是多行）
        if self._is_sql_start(line):
            # SQL语句如果没有分号结尾，需要继续
            return not line.rstrip().endswith(';')
        
        # 4. 未闭合的结构
        if self._has_unclosed_structure(line):
            return True
        
        # 5. 缩进（可能是代码块）
        if line.startswith('  ') or line.startswith('\t'):
            return True
        
        return False
    
    def _is_sql_start(self, line: str) -> bool:
        """检查是否是SQL语句开始"""
        for pattern in self.sql_patterns:
            if pattern.match(line):
                return True
        return False
    
    def _has_unclosed_structure(self, line: str) -> bool:
        """检查是否有未闭合的括号、引号等"""
        # 简单的括号匹配
        stack = []
        in_string = False
        string_char = None
        
        for i, char in enumerate(line):
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    string_char = char
                elif char in '([{':
                    stack.append(char)
                elif char in ')]}':
                    if not stack:
                        return False
                    opener = stack.pop()
                    if not self._matches(opener, char):
                        return False
            else:
                if char == string_char and (i == 0 or line[i-1] != '\\'):
                    in_string = False
        
        # 如果还有未闭合的括号或字符串，需要继续
        return len(stack) > 0 or in_string
    
    def _matches(self, opener: str, closer: str) -> bool:
        """检查括号是否匹配"""
        pairs = {'(': ')', '[': ']', '{': '}'}
        return pairs.get(opener) == closer
    
    def _collect_multiline(self, first_line: str) -> str:
        """收集多行输入"""
        lines = [first_line]
        continuation_prompt = "... "
        
        # 判断结束条件
        if first_line.strip() in self.CODE_MARKERS:
            # 代码块模式
            end_marker = first_line.strip()
            print(f"进入多行模式，输入 {end_marker} 结束")
            
            while True:
                try:
                    line = input(continuation_prompt)
                    if line.strip() == end_marker:
                        break
                    lines.append(line)
                except EOFError:
                    break
        else:
            # 智能续行模式
            while True:
                try:
                    line = input(continuation_prompt)
                    lines.append(line)
                    
                    # 检查是否应该结束
                    all_text = '\n'.join(lines)
                    
                    # SQL语句：遇到分号结束
                    if self._is_sql_start(lines[0]) and line.rstrip().endswith(';'):
                        break
                    
                    # 空行结束（除非是SQL或代码块）
                    if line.strip() == '' and not self._is_sql_start(lines[0]):
                        lines.pop()  # 移除空行
                        break
                    
                    # 检查结构是否完整
                    if not self._has_unclosed_structure(all_text):
                        # 如果没有显式的续行标记，询问是否继续
                        if not line.endswith('\\'):
                            # 对于SQL，检查是否有分号
                            if self._is_sql_start(lines[0]):
                                if line.rstrip().endswith(';'):
                                    break
                            else:
                                # 非SQL，没有续行符，结束
                                break
                    
                except EOFError:
                    break
        
        return '\n'.join(lines)


def demonstrate_smart_paste():
    """演示智能粘贴处理"""
    print("智能粘贴处理演示")
    print("="*50)
    print("特性：")
    print("1. 自动识别SQL语句并等待分号")
    print("2. 自动识别未闭合的括号/引号")
    print("3. 支持 ``` 代码块")
    print("4. 支持 \\ 续行")
    print("="*50)
    
    handler = SmartPasteHandler(debug=True)
    
    examples = [
        "SELECT * FROM users",
        "SELECT * FROM users;",
        '{"name": "test",',
        "def hello():",
        "普通单行文本",
    ]
    
    print("\n示例输入预测：")
    for ex in examples:
        should_continue = handler._should_continue_input(ex)
        print(f"'{ex}' -> {'多行' if should_continue else '单行'}")
    
    print("\n开始测试（输入 'exit' 退出）：")
    
    while True:
        try:
            result = handler.get_smart_input("\n💬 你: ")
            
            if result.lower() == 'exit':
                break
            
            print("\n收到的输入：")
            print("-"*30)
            print(result)
            print("-"*30)
            
        except KeyboardInterrupt:
            print("\n退出")
            break


if __name__ == "__main__":
    demonstrate_smart_paste()
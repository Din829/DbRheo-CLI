#!/usr/bin/env python
"""
DbRheo 实时日志监控器 V2
通过监控日志文件实现实时显示
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
import threading

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

from dbrheo.utils.realtime_logger import LogEventType, LogLevel


class FileLogMonitor:
    """文件日志监控器"""
    
    def __init__(self, log_file="dbrheo_realtime.log"):
        self.log_file = Path(log_file)
        self.file_position = 0
        self.is_running = False
        self.filters = {}
        
        # 颜色映射
        self.color_map = {
            LogEventType.CONVERSATION.value: "\033[36m",  # 青色
            LogEventType.TOOL_CALL.value: "\033[33m",     # 黄色
            LogEventType.TOOL_RESULT.value: "\033[32m",   # 绿色
            LogEventType.ERROR.value: "\033[31m",         # 红色
            LogEventType.SYSTEM.value: "\033[90m",        # 灰色
            LogEventType.NETWORK.value: "\033[35m",       # 紫色
            LogEventType.PERFORMANCE.value: "\033[34m",   # 蓝色
        }
        self.reset = "\033[0m"
        
    def set_filters(self, **filters):
        """设置过滤器"""
        self.filters = filters
        
    def should_display(self, log_entry):
        """检查是否应该显示这条日志"""
        # 级别过滤
        if 'min_level' in self.filters:
            level = LogLevel[log_entry.get('level', 'INFO')]
            if level.value < self.filters['min_level'].value:
                return False
                
        # 类型过滤
        if 'types' in self.filters:
            if log_entry.get('type') not in self.filters['types']:
                return False
                
        # 来源过滤
        if 'source_filter' in self.filters:
            if self.filters['source_filter'] not in log_entry.get('source', ''):
                return False
                
        # 工具过滤
        if 'tool_filter' in self.filters:
            data = log_entry.get('data', {})
            if 'tool' in data and self.filters['tool_filter'] not in data['tool']:
                return False
                
        return True
        
    def format_log_entry(self, log_entry):
        """格式化日志条目"""
        event_type = log_entry.get('type', 'system')
        color = self.color_map.get(event_type, self.reset)
        
        # 基本信息
        time_str = log_entry.get('time', datetime.now().strftime("%H:%M:%S.%f")[:-3])
        source = log_entry.get('source', '')
        message = log_entry.get('message', '')
        
        output = f"{color}[{time_str}] [{event_type}] {source}{self.reset}"
        if message:
            output += f" - {message}"
            
        # 特殊格式化不同类型的事件
        data = log_entry.get('data', {})
        
        if event_type == LogEventType.CONVERSATION.value:
            role = data.get('role', 'Unknown')
            content = data.get('content', '')
            if len(content) > 100:
                content = content[:97] + "..."
            output = f"{color}[{time_str}] 💬 {role}: {content}{self.reset}"
            
        elif event_type == LogEventType.TOOL_CALL.value:
            tool = data.get('tool', '')
            params = data.get('params', {})
            call_id = data.get('call_id', '')[:8] if data.get('call_id') else ''
            output = f"{color}[{time_str}] 🔧 调用工具: {tool}"
            if call_id:
                output += f" [{call_id}]"
            output += self.reset
            
            # 显示参数（缩进）
            if params and isinstance(params, dict):
                for key, value in params.items():
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:47] + "..."
                    output += f"\n    {key}: {value}"
                    
        elif event_type == LogEventType.TOOL_RESULT.value:
            tool = data.get('tool', '')
            success = data.get('success', True)
            result = data.get('result', '')
            call_id = data.get('call_id', '')[:8] if data.get('call_id') else ''
            
            status_icon = "✅" if success else "❌"
            output = f"{color}[{time_str}] {status_icon} {tool} 结果"
            if call_id:
                output += f" [{call_id}]"
            output += self.reset
            
            if result and len(str(result)) > 0:
                result_str = str(result)
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                output += f"\n    {result_str}"
                
        return output
        
    def monitor_file(self):
        """监控日志文件"""
        # 如果文件不存在，等待它创建
        while not self.log_file.exists() and self.is_running:
            time.sleep(0.5)
            
        # 打开文件并定位到末尾（只显示新日志）
        with open(self.log_file, 'r', encoding='utf-8') as f:
            # 移动到文件末尾
            f.seek(0, 2)
            self.file_position = f.tell()
            
            while self.is_running:
                # 检查文件是否有新内容
                line = f.readline()
                if line:
                    try:
                        # 解析JSON日志
                        log_entry = json.loads(line.strip())
                        
                        # 检查是否应该显示
                        if self.should_display(log_entry):
                            # 格式化并显示
                            formatted = self.format_log_entry(log_entry)
                            print(formatted)
                            
                    except json.JSONDecodeError:
                        # 如果不是JSON，直接显示
                        print(f"[RAW] {line.strip()}")
                        
                else:
                    # 没有新内容，等待
                    time.sleep(0.1)
                    
                    # 检查文件是否被轮转
                    try:
                        current_size = self.log_file.stat().st_size
                        if current_size < self.file_position:
                            # 文件被轮转了，重新打开
                            return self.monitor_file()
                    except:
                        pass
                        
    def start(self):
        """启动监控"""
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_file)
        self.monitor_thread.start()
        
    def stop(self):
        """停止监控"""
        self.is_running = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join()


def display_banner():
    """显示启动横幅"""
    print("\033[36m" + "="*60)
    print("🔍 DbRheo Realtime Log Monitor V2")
    print("="*60 + "\033[0m")
    print("监控Agent对话和工具调用的实时日志")
    print("按 Ctrl+C 退出\n")


def main():
    parser = argparse.ArgumentParser(description='DbRheo实时日志监控器')
    parser.add_argument(
        '--file',
        default='dbrheo_realtime.log',
        help='日志文件路径'
    )
    parser.add_argument(
        '--level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='最小日志级别'
    )
    parser.add_argument(
        '--types',
        nargs='+',
        choices=['conversation', 'tool', 'result', 'system', 'error', 'network', 'performance'],
        help='要显示的事件类型'
    )
    parser.add_argument(
        '--filter-source',
        help='按来源过滤'
    )
    parser.add_argument(
        '--filter-tool',
        help='按工具名过滤'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='生成测试日志'
    )
    
    args = parser.parse_args()
    
    # 显示横幅
    display_banner()
    
    # 创建监控器
    monitor = FileLogMonitor(args.file)
    
    # 设置过滤器
    filters = {}
    if args.level:
        filters['min_level'] = LogLevel[args.level]
    if args.types:
        type_map = {
            'conversation': LogEventType.CONVERSATION.value,
            'tool': LogEventType.TOOL_CALL.value,
            'result': LogEventType.TOOL_RESULT.value,
            'system': LogEventType.SYSTEM.value,
            'error': LogEventType.ERROR.value,
            'network': LogEventType.NETWORK.value,
            'performance': LogEventType.PERFORMANCE.value
        }
        filters['types'] = [type_map[t] for t in args.types]
    if args.filter_source:
        filters['source_filter'] = args.filter_source
    if args.filter_tool:
        filters['tool_filter'] = args.filter_tool
        
    monitor.set_filters(**filters)
    
    # 如果是测试模式，生成一些测试日志
    if args.test:
        print("\033[33m[测试模式] 生成测试日志到文件...\033[0m\n")
        with open(args.file, 'a', encoding='utf-8') as f:
            # 写入测试日志
            test_logs = [
                {
                    "timestamp": time.time(),
                    "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "type": "system",
                    "level": "INFO",
                    "source": "System",
                    "message": "日志监控器启动",
                    "data": {"version": "2.0.0"}
                },
                {
                    "timestamp": time.time(),
                    "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "type": "conversation",
                    "level": "INFO",
                    "source": "Conversation",
                    "message": "User: 帮我查询数据库",
                    "data": {"role": "User", "content": "帮我查询数据库中的用户表"}
                },
                {
                    "timestamp": time.time(),
                    "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "type": "tool_call",
                    "level": "INFO",
                    "source": "Tool:schema_discovery",
                    "message": "Calling schema_discovery",
                    "data": {"tool": "schema_discovery", "params": {"database": "main.db"}, "call_id": "test-123"}
                }
            ]
            
            for log in test_logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
                f.flush()
                time.sleep(0.5)
    
    # 启动监控
    print(f"\033[32m监控器正在运行... 监控文件: {args.file}\033[0m")
    print("\033[90m提示: 在另一个终端运行 DbRheo Agent (使用 --log 参数)\033[0m\n")
    
    try:
        monitor.start()
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n\033[33m正在关闭监控器...\033[0m")
        monitor.stop()
        print("\033[32m监控器已关闭\033[0m")


if __name__ == '__main__':
    main()
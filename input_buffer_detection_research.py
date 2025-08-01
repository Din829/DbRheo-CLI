#!/usr/bin/env python3
"""
Python输入缓冲区检测方法综合研究
研究各种平台上检测stdin缓冲区是否有剩余内容的方法
"""

import sys
import platform
import os
from typing import Optional, Dict, Any, List, Tuple


class InputBufferDetector:
    """
    输入缓冲区检测器
    集成多种跨平台的检测方法
    """
    
    def __init__(self):
        self.platform_info = self._get_platform_info()
        self.available_methods = self._detect_available_methods()
        
    def _get_platform_info(self) -> Dict[str, Any]:
        """获取平台信息"""
        info = {
            'system': platform.system(),
            'platform': sys.platform,
            'is_tty': sys.stdin.isatty(),
            'python_version': sys.version_info,
            'is_wsl': False
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
        
    def _detect_available_methods(self) -> Dict[str, bool]:
        """检测可用的方法"""
        methods = {}
        
        # 1. select.select() 检测
        try:
            import select
            methods['select'] = hasattr(select, 'select')
        except ImportError:
            methods['select'] = False
            
        # 2. msvcrt 检测 (Windows)
        try:
            import msvcrt
            methods['msvcrt'] = True
        except ImportError:
            methods['msvcrt'] = False
            
        # 3. termios 检测 (Unix)
        try:
            import termios
            methods['termios'] = True
        except ImportError:
            methods['termios'] = False
            
        # 4. fcntl 检测 (Unix)
        try:
            import fcntl
            methods['fcntl'] = True
        except ImportError:
            methods['fcntl'] = False
            
        # 5. threading 检测
        try:
            import threading
            methods['threading'] = True
        except ImportError:
            methods['threading'] = False
            
        return methods
        
    def method1_select_based(self, timeout: float = 0.0) -> Tuple[bool, str]:
        """
        方法1: 使用select.select()检测
        
        优点:
        - Unix/Linux系统广泛支持
        - 可以设置超时
        - 相对可靠
        
        缺点:  
        - Windows上不支持stdin
        - WSL中可能有延迟问题
        """
        if not self.available_methods.get('select', False):
            return False, "select模块不可用"
            
        try:
            import select
            readable, _, _ = select.select([sys.stdin], [], [], timeout)
            has_input = bool(readable)
            
            details = f"select.select()检测结果: {has_input}"
            if self.platform_info['is_wsl']:
                details += " (WSL环境，可能有延迟)"
                
            return has_input, details
            
        except Exception as e:
            return False, f"select检测失败: {e}"
            
    def method2_msvcrt_kbhit(self) -> Tuple[bool, str]:
        """
        方法2: Windows msvcrt.kbhit()
        
        优点:
        - Windows原生支持
        - 检测键盘输入缓冲区
        - 非阻塞
        
        缺点:
        - 仅Windows可用
        - 只检测键盘输入，不检测管道/重定向
        """
        if not self.available_methods.get('msvcrt', False):
            return False, "msvcrt模块不可用（非Windows系统）"
            
        try:
            import msvcrt
            has_input = msvcrt.kbhit()
            return has_input, f"msvcrt.kbhit()检测结果: {has_input}"
            
        except Exception as e:
            return False, f"msvcrt检测失败: {e}"
            
    def method3_sys_stdin_readable(self) -> Tuple[bool, str]:
        """
        方法3: sys.stdin.readable()
        
        注意: 这个方法检查流是否可读，而不是是否有待读数据
        """
        try:
            is_readable = sys.stdin.readable()
            return is_readable, f"sys.stdin.readable()结果: {is_readable} (注意：这只表示流是否可读)"
            
        except Exception as e:
            return False, f"readable()检测失败: {e}"
            
    def method4_fcntl_nonblocking(self) -> Tuple[bool, str]:
        """
        方法4: 使用fcntl设置非阻塞读取
        
        优点:
        - Unix系统支持
        - 可以检测是否有数据
        
        缺点:
        - 会修改文件描述符状态
        - 需要小心处理状态恢复
        - 可能消耗数据
        """
        if not self.available_methods.get('fcntl', False):
            return False, "fcntl模块不可用（非Unix系统）"
            
        try:
            import fcntl
            import io
            
            # 保存当前标志
            fd = sys.stdin.fileno()
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            
            try:
                # 设置非阻塞
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
                
                # 尝试读取一个字符
                try:
                    data = os.read(fd, 1)
                    if data:
                        # 有数据，需要放回去（但这很困难）
                        # 这是这个方法的主要缺点
                        return True, f"fcntl非阻塞检测: 有数据 (警告：已消耗1字节)"
                    else:
                        return False, "fcntl非阻塞检测: 无数据"
                except OSError as e:
                    if e.errno == 11:  # EAGAIN/EWOULDBLOCK
                        return False, "fcntl非阻塞检测: 无数据可读"
                    else:
                        raise
                        
            finally:
                # 恢复原标志
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
                
        except Exception as e:
            return False, f"fcntl检测失败: {e}"
            
    def method5_termios_peek(self) -> Tuple[bool, str]:
        """
        方法5: 使用termios配合select进行检测
        
        这是对method1的增强版本
        """
        if not (self.available_methods.get('termios', False) and 
                self.available_methods.get('select', False)):
            return False, "termios或select模块不可用"
            
        try:
            import select
            import termios
            import tty
            
            if not sys.stdin.isatty():
                return False, "stdin不是TTY"
                
            # 保存原始设置
            old_settings = termios.tcgetattr(sys.stdin.fileno())
            
            try:
                # 设置为原始模式
                tty.setraw(sys.stdin.fileno())
                
                # 检测是否有输入
                readable, _, _ = select.select([sys.stdin], [], [], 0)
                has_input = bool(readable)
                
                return has_input, f"termios+select检测: {has_input}"
                
            finally:
                # 恢复设置
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                
        except Exception as e:
            return False, f"termios检测失败: {e}"
            
    def method6_threading_timeout(self, timeout: float = 0.1) -> Tuple[bool, str]:
        """
        方法6: 使用线程和超时进行检测
        
        创建一个线程尝试读取，主线程等待一定时间
        这是最通用但也最复杂的方法
        """
        if not self.available_methods.get('threading', False):
            return False, "threading模块不可用"
            
        import threading
        import queue
        import time
        
        result_queue = queue.Queue()
        
        def read_thread():
            try:
                # 尝试读取一个字符（会阻塞）
                char = sys.stdin.read(1)
                result_queue.put(('data', char))
            except Exception as e:
                result_queue.put(('error', str(e)))
                
        # 启动读取线程
        thread = threading.Thread(target=read_thread, daemon=True)
        thread.start()
        
        # 等待指定时间
        try:
            result_type, result_data = result_queue.get(timeout=timeout)
            if result_type == 'data':
                return True, f"线程检测: 有数据 (警告：已消耗数据 {repr(result_data)})"
            else:
                return False, f"线程检测错误: {result_data}"
        except queue.Empty:
            return False, f"线程检测: 在{timeout}秒内无数据"
            
    def comprehensive_test(self, timeout: float = 0.05) -> Dict[str, Any]:
        """
        综合测试所有可用方法
        """
        results = {
            'platform_info': self.platform_info,
            'available_methods': self.available_methods,
            'test_results': {}
        }
        
        # 测试各种方法
        methods = [
            ('select_based', self.method1_select_based, timeout),
            ('msvcrt_kbhit', self.method2_msvcrt_kbhit, None),
            ('stdin_readable', self.method3_sys_stdin_readable, None),
            ('fcntl_nonblocking', self.method4_fcntl_nonblocking, None),
            ('termios_peek', self.method5_termios_peek, None),
            ('threading_timeout', self.method6_threading_timeout, timeout)
        ]
        
        for method_name, method_func, param in methods:
            try:
                if param is not None:
                    has_input, details = method_func(param)
                else:
                    has_input, details = method_func()
                    
                results['test_results'][method_name] = {
                    'has_input': has_input,
                    'details': details,
                    'success': True
                }
            except Exception as e:
                results['test_results'][method_name] = {
                    'has_input': False,
                    'details': f"方法执行异常: {e}",
                    'success': False
                }
                
        return results
        
    def get_recommended_method(self) -> Tuple[str, str]:
        """
        根据平台推荐最佳方法
        """
        system = self.platform_info['system']
        is_tty = self.platform_info['is_tty']
        is_wsl = self.platform_info['is_wsl']
        
        if system == 'Windows':
            if self.available_methods.get('msvcrt', False) and is_tty:
                return 'msvcrt_kbhit', "Windows平台推荐使用msvcrt.kbhit()"
            else:
                return 'select_based', "Windows非TTY环境，使用select（可能不支持）"
                
        elif system in ['Linux', 'Darwin']:  # Linux或macOS
            if is_wsl:
                return 'select_based', "WSL环境推荐使用select.select()，但可能有延迟"
            elif self.available_methods.get('select', False):
                return 'select_based', "Unix系统推荐使用select.select()"
            else:
                return 'threading_timeout', "select不可用，使用线程方法"
                
        else:
            return 'threading_timeout', "未知平台，使用通用的线程方法"


class CrossPlatformInputDetector:
    """
    跨平台输入检测的最佳实践实现
    """
    
    def __init__(self, default_timeout: float = 0.05):
        self.detector = InputBufferDetector()
        self.default_timeout = default_timeout
        self.recommended_method, self.method_reason = self.detector.get_recommended_method()
        
    def has_pending_input(self, timeout: Optional[float] = None) -> bool:
        """
        检测是否有待处理的输入
        自动选择最佳方法
        """
        if timeout is None:
            timeout = self.default_timeout
            
        # 根据推荐方法进行检测
        try:
            if self.recommended_method == 'msvcrt_kbhit':
                has_input, _ = self.detector.method2_msvcrt_kbhit()
                return has_input
                
            elif self.recommended_method == 'select_based':
                has_input, _ = self.detector.method1_select_based(timeout)
                return has_input
                
            elif self.recommended_method == 'threading_timeout':
                # 注意：这个方法会消耗数据，通常不推荐用于实际应用
                return False  # 为了安全起见返回False
                
            else:
                return False
                
        except:
            return False
            
    def collect_multiline_paste(self, first_line: str, max_wait: float = 0.5) -> List[str]:
        """
        收集粘贴的多行内容
        这是实际应用中的最佳实践
        """
        lines = [first_line]
        total_wait = 0.0
        check_interval = 0.02  # 20ms检查间隔
        
        while total_wait < max_wait:
            if self.has_pending_input(check_interval):
                try:
                    line = sys.stdin.readline()
                    if line:
                        lines.append(line.rstrip('\n\r'))
                        total_wait = 0.0  # 重置等待时间
                    else:
                        break
                except:
                    break
            else:
                total_wait += check_interval
                
        return lines


def demo_and_test():
    """演示和测试各种方法"""
    print("Python输入缓冲区检测方法研究")
    print("=" * 60)
    
    detector = InputBufferDetector()
    
    # 显示平台信息
    print("\n平台信息:")
    for key, value in detector.platform_info.items():
        print(f"  {key}: {value}")
        
    print("\n可用方法:")
    for method, available in detector.available_methods.items():
        print(f"  {method}: {'✓' if available else '✗'}")
        
    # 获取推荐方法
    recommended, reason = detector.get_recommended_method()
    print(f"\n推荐方法: {recommended}")
    print(f"推荐理由: {reason}")
    
    # 交互式测试
    print("\n" + "=" * 60)
    print("交互式测试 - 请选择:")
    print("1. 综合测试所有方法（需要有输入缓冲区内容）")
    print("2. 实时检测演示")
    print("3. 多行粘贴收集演示")
    print("4. 退出")
    
    while True:
        try:
            choice = input("\n选择 (1-4): ").strip()
            
            if choice == '1':
                print("\n请先粘贴一些多行内容到输入缓冲区，然后按回车:")
                input("按回车开始测试...")
                
                results = detector.comprehensive_test()
                print("\n测试结果:")
                for method, result in results['test_results'].items():
                    status = "✓" if result['success'] else "✗"
                    has_input = "有输入" if result['has_input'] else "无输入"
                    print(f"  {status} {method}: {has_input} - {result['details']}")
                    
            elif choice == '2':
                print("\n实时检测演示（按Ctrl+C退出）:")
                print("请尝试快速输入内容...")
                
                cross_detector = CrossPlatformInputDetector()
                
                try:
                    while True:
                        has_input = cross_detector.has_pending_input(0.1)
                        print(f"\r检测结果: {'有输入' if has_input else '无输入'}", end='', flush=True)
                        import time
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\n检测停止")
                    
            elif choice == '3':
                print("\n多行粘贴收集演示:")
                print("请粘贴多行内容:")
                
                cross_detector = CrossPlatformInputDetector()
                first_line = input("> ")
                
                lines = cross_detector.collect_multiline_paste(first_line)
                
                print(f"\n收集到 {len(lines)} 行:")
                for i, line in enumerate(lines, 1):
                    print(f"  第{i}行: {repr(line)}")
                    
            elif choice == '4':
                break
            else:
                print("无效选择")
                
        except KeyboardInterrupt:
            print("\n\n程序中断")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    demo_and_test()
"""
重试机制实现 - 参考Gemini CLI的retry策略
支持指数退避、抖动、429错误处理等
"""

import asyncio
import time
import random
from typing import TypeVar, Callable, Optional, Union, Awaitable, Dict, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryOptions:
    """重试配置选项"""
    def __init__(
        self,
        max_attempts: int = 5,
        initial_delay_ms: int = 5000,  # 5秒
        max_delay_ms: int = 30000,     # 30秒
        should_retry: Optional[Callable[[Exception], bool]] = None,
        on_persistent_429: Optional[Callable[[], Awaitable[None]]] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.should_retry = should_retry or self._default_should_retry
        self.on_persistent_429 = on_persistent_429
        
    @staticmethod
    def _default_should_retry(error: Exception) -> bool:
        """默认重试策略：429和5xx错误"""
        error_message = str(error)
        
        # 检查429错误
        if "429" in error_message:
            return True
            
        # 检查5xx错误
        if any(f"5{i}" in error_message for i in range(10)):
            return True
            
        # 检查特定的错误类型
        if hasattr(error, 'status'):
            status = getattr(error, 'status')
            if status == 429 or (500 <= status < 600):
                return True
                
        return False


def get_retry_after_delay_ms(error: Exception) -> Optional[int]:
    """从错误中提取Retry-After延迟时间（毫秒）"""
    # 尝试从不同位置获取Retry-After头
    retry_after = None
    
    if hasattr(error, 'response') and hasattr(error.response, 'headers'):
        retry_after = error.response.headers.get('Retry-After')
    elif hasattr(error, 'headers'):
        retry_after = error.headers.get('Retry-After')
        
    if not retry_after:
        return None
        
    # 尝试解析为秒数
    try:
        seconds = int(retry_after)
        return seconds * 1000
    except ValueError:
        pass
        
    # 尝试解析为HTTP日期
    try:
        from datetime import datetime
        from email.utils import parsedate_to_datetime
        retry_date = parsedate_to_datetime(retry_after)
        delay_ms = max(0, int((retry_date.timestamp() - time.time()) * 1000))
        return delay_ms
    except:
        pass
        
    return None


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    options: Optional[RetryOptions] = None
) -> T:
    """
    使用指数退避和抖动的重试机制
    
    参数:
        func: 要执行的异步函数
        options: 重试配置选项
        
    返回:
        函数执行结果
        
    抛出:
        最后一次尝试的异常
    """
    options = options or RetryOptions()
    
    current_delay_ms = options.initial_delay_ms
    consecutive_429_count = 0
    last_error = None
    
    for attempt in range(options.max_attempts):
        try:
            # 执行函数
            result = await func()
            
            # 成功后重置429计数
            if consecutive_429_count > 0:
                consecutive_429_count = 0
                logger.info("Successfully recovered from 429 errors")
                
            return result
            
        except Exception as error:
            last_error = error
            
            # 检查是否应该重试
            if not options.should_retry(error):
                raise error
                
            # 检查是否是最后一次尝试
            if attempt == options.max_attempts - 1:
                raise error
                
            # 处理429错误
            if "429" in str(error):
                consecutive_429_count += 1
                logger.warning(f"429 error (attempt {attempt + 1}/{options.max_attempts})")
                
                # 连续多次429错误，触发降级
                if consecutive_429_count >= 3 and options.on_persistent_429:
                    logger.warning("Persistent 429 errors detected, triggering fallback")
                    await options.on_persistent_429()
                    # 降级后立即重试，不计入重试次数
                    continue
            else:
                logger.error(f"Error on attempt {attempt + 1}/{options.max_attempts}: {error}")
                
            # 计算延迟时间
            retry_after_delay = get_retry_after_delay_ms(error)
            if retry_after_delay is not None:
                delay_ms = retry_after_delay
                logger.info(f"Using Retry-After delay: {delay_ms}ms")
            else:
                # 使用指数退避 + 抖动
                jitter = current_delay_ms * 0.3 * (random.random() * 2 - 1)
                delay_ms = max(0, current_delay_ms + jitter)
                logger.info(f"Using exponential backoff delay: {delay_ms}ms")
                
                # 准备下次延迟（指数增长）
                current_delay_ms = min(options.max_delay_ms, current_delay_ms * 2)
                
            # 等待
            await asyncio.sleep(delay_ms / 1000)
            
    # 不应该到达这里，但为了安全
    raise last_error


def retry_decorator(
    max_attempts: int = 5,
    initial_delay_ms: int = 5000,
    max_delay_ms: int = 30000,
    should_retry: Optional[Callable[[Exception], bool]] = None
):
    """
    装饰器形式的重试机制
    
    使用示例:
        @retry_decorator(max_attempts=3)
        async def fetch_data():
            return await api_call()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            options = RetryOptions(
                max_attempts=max_attempts,
                initial_delay_ms=initial_delay_ms,
                max_delay_ms=max_delay_ms,
                should_retry=should_retry
            )
            
            async def wrapped_func():
                return await func(*args, **kwargs)
                
            return await retry_with_backoff(wrapped_func, options)
            
        return wrapper
    return decorator


# 同步版本（用于同步代码）
def retry_with_backoff_sync(
    func: Callable[[], T],
    options: Optional[RetryOptions] = None
) -> T:
    """同步版本的重试机制"""
    options = options or RetryOptions()
    
    current_delay_ms = options.initial_delay_ms
    consecutive_429_count = 0
    last_error = None
    
    for attempt in range(options.max_attempts):
        try:
            result = func()
            
            if consecutive_429_count > 0:
                consecutive_429_count = 0
                logger.info("Successfully recovered from 429 errors")
                
            return result
            
        except Exception as error:
            last_error = error
            
            if not options.should_retry(error):
                raise error
                
            if attempt == options.max_attempts - 1:
                raise error
                
            if "429" in str(error):
                consecutive_429_count += 1
                logger.warning(f"429 error (attempt {attempt + 1}/{options.max_attempts})")
            else:
                logger.error(f"Error on attempt {attempt + 1}/{options.max_attempts}: {error}")
                
            retry_after_delay = get_retry_after_delay_ms(error)
            if retry_after_delay is not None:
                delay_ms = retry_after_delay
                logger.info(f"Using Retry-After delay: {delay_ms}ms")
            else:
                jitter = current_delay_ms * 0.3 * (random.random() * 2 - 1)
                delay_ms = max(0, current_delay_ms + jitter)
                logger.info(f"Using exponential backoff delay: {delay_ms}ms")
                current_delay_ms = min(options.max_delay_ms, current_delay_ms * 2)
                
            time.sleep(delay_ms / 1000)
            
    raise last_error
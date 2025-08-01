"""
重试机制 - 提供可配置的重试逻辑
用于处理网络请求、数据库连接等可能失败的操作
"""

import asyncio
import logging
from typing import TypeVar, Callable, Any, Optional, List, Type
from dataclasses import dataclass
from functools import wraps

T = TypeVar('T')

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Optional[List[Type[Exception]]] = None


async def with_retry(
    func: Callable[..., T],
    config: RetryConfig,
    *args,
    **kwargs
) -> T:
    """
    异步重试装饰器
    支持指数退避、抖动、异常过滤等功能
    """
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            last_exception = e
            
            # 检查是否为可重试的异常
            if config.retryable_exceptions:
                if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                    logger.warning(f"Non-retryable exception: {e}")
                    raise e
                    
            # 最后一次尝试，不再重试
            if attempt == config.max_attempts - 1:
                break
                
            # 计算延迟时间
            delay = _calculate_delay(attempt, config)
            
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f} seconds..."
            )
            
            await asyncio.sleep(delay)
            
    # 所有重试都失败了
    logger.error(f"All {config.max_attempts} attempts failed. Last error: {last_exception}")
    raise last_exception


def retry(config: RetryConfig):
    """重试装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await with_retry(func, config, *args, **kwargs)
        return wrapper
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算延迟时间（指数退避 + 抖动）"""
    import random
    
    # 指数退避
    delay = config.base_delay * (config.exponential_base ** attempt)
    
    # 限制最大延迟
    delay = min(delay, config.max_delay)
    
    # 添加抖动
    if config.jitter:
        delay = delay * (0.5 + random.random() * 0.5)
        
    return delay


# 预定义的重试配置
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError
    ]
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError
    ]
)

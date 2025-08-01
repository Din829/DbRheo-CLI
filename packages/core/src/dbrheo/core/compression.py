"""
历史压缩机制 - 完全参考Gemini CLI的tryCompressChat
当对话历史过长时自动压缩，保持Token在限制范围内
"""

from typing import List, Optional, Dict, Any
from ..types.core_types import Content
from .chat import DatabaseChat


async def try_compress_chat(
    chat: DatabaseChat, 
    prompt_id: str, 
    force: bool = False
) -> Optional[Dict[str, Any]]:
    """
    历史压缩 - 完全参考Gemini CLI的tryCompressChat
    
    压缩策略：
    1. 计算当前历史的token数量
    2. 如果超过阈值（70%），触发压缩
    3. 保留最近30%的详细历史
    4. 压缩前70%的历史为摘要
    5. 更新历史记录
    """
    curated_history = chat.get_history(True)  # 获取清理后的历史
    
    if not curated_history:
        return None
        
    # 计算token数量
    token_count = await _count_tokens(curated_history)
    if token_count is None:
        return None
        
    # 压缩阈值：70%（与Gemini CLI一致）
    token_limit = _get_token_limit(chat.config.get_model())
    compression_threshold = 0.7 * token_limit
    
    if not force and token_count < compression_threshold:
        return None
        
    # 确定压缩边界：保留最近30%的历史
    preserve_threshold = 0.3
    compress_before_index = _find_index_after_fraction(
        curated_history, 1 - preserve_threshold
    )
    
    # 找到下一个用户消息作为Turn边界
    while (compress_before_index < len(curated_history) and
           curated_history[compress_before_index].get('role') != 'user'):
        compress_before_index += 1
        
    history_to_compress = curated_history[:compress_before_index]
    history_to_keep = curated_history[compress_before_index:]
    
    # 执行压缩（使用专门的压缩提示词）
    compressed_summary = await _compress_history_segment(
        history_to_compress, prompt_id
    )
    
    # 更新历史：压缩摘要 + 保留的详细历史
    chat.set_history([
        {'role': 'user', 'parts': [{'text': compressed_summary}]},
        *history_to_keep
    ])
    
    return {
        'original_token_count': token_count,
        'compressed_token_count': await _count_tokens(chat.get_history(True)),
        'compression_ratio': len(history_to_compress) / len(curated_history)
    }


async def _count_tokens(history: List[Content]) -> Optional[int]:
    """计算历史记录的token数量"""
    # TODO: 实现实际的token计数逻辑
    # 可以使用tiktoken或调用Gemini API的计数接口
    total_chars = 0
    for content in history:
        for part in content.get('parts', []):
            if part.get('text'):
                total_chars += len(part['text'])
    
    # 粗略估算：4个字符约等于1个token
    return total_chars // 4


def _get_token_limit(model: str) -> int:
    """获取模型的token限制"""
    model_limits = {
        'gemini-1.5-pro': 2000000,
        'gemini-1.5-flash': 1000000,
        'gemini-1.0-pro': 30720
    }
    return model_limits.get(model, 30720)


def _find_index_after_fraction(history: List[Content], fraction: float) -> int:
    """找到指定比例后的索引位置"""
    target_index = int(len(history) * fraction)
    return min(target_index, len(history) - 1)


async def _compress_history_segment(
    history_segment: List[Content], 
    prompt_id: str
) -> str:
    """压缩历史片段为摘要"""
    # TODO: 实现实际的历史压缩逻辑
    # 使用专门的压缩提示词调用LLM生成摘要
    
    # 临时实现：简单的文本摘要
    summary_parts = []
    for content in history_segment:
        role = content.get('role', 'unknown')
        for part in content.get('parts', []):
            if part.get('text'):
                text = part['text'][:100] + "..." if len(part['text']) > 100 else part['text']
                summary_parts.append(f"{role}: {text}")
                
    return f"[压缩的对话历史摘要]\n" + "\n".join(summary_parts[-10:])  # 保留最后10条

"""
next_speaker判断逻辑 - 完全参考Gemini CLI的checkNextSpeaker
AI自主判断下一步是继续执行还是等待用户输入
"""

from typing import Optional, Dict, Any
from ..types.core_types import AbortSignal
from .chat import DatabaseChat
from .prompts import DatabasePromptManager


# JSON Schema定义
NEXT_SPEAKER_SCHEMA = {
    "type": "object",
    "properties": {
        "next_speaker": {
            "type": "string",
            "enum": ["user", "model"],
            "description": "Who should speak next"
        },
        "reasoning": {
            "type": "string",
            "description": "Explanation for the decision"
        }
    },
    "required": ["next_speaker", "reasoning"]
}


async def check_next_speaker(
    chat: DatabaseChat, 
    client: 'DatabaseClient', 
    signal: AbortSignal
) -> Optional[Dict[str, Any]]:
    """
    AI自主判断下一步 - 与Gemini CLI的checkNextSpeaker完全一致
    
    判断规则（按优先级）：
    1. 特殊情况优先处理：
       - 最后是工具执行结果 → model继续处理结果
       - 最后是空的model消息 → model继续完成响应
    2. AI智能判断（通过临时提示词询问）：
       - Model继续：明确表示下一步动作
       - User回答：向用户提出了需要回答的问题
       - User输入：完成当前任务，等待新指令
    """
    # 调试
    from ..utils.debug_logger import log_info
    log_info("NextSpeaker", f"🤔 CHECK_NEXT_SPEAKER called")
    
    # 1. 特殊情况优先处理（与Gemini CLI逻辑一致）
    curated_history = chat.get_history(True)
    if not curated_history:
        return None
        
    last_message = curated_history[-1]
    
    # 工具刚执行完，AI应该继续处理结果
    if last_message.get('role') == 'function':
        return {
            'next_speaker': 'model',
            'reasoning': 'Function response received, model should process the result'
        }
        
    # 空的model消息，应该继续完成响应
    if (last_message.get('role') == 'model' and
        not any(part.get('text', '').strip() for part in last_message.get('parts', []))):
        return {
            'next_speaker': 'model',
            'reasoning': 'Empty model response, should continue'
        }
        
    # 2. AI智能判断（临时提示词，不保存到历史）
    prompt_manager = DatabasePromptManager()
    check_prompt = prompt_manager.get_next_speaker_prompt()
    
    # 构建临时内容（与Gemini CLI方式一致）
    contents = [
        *curated_history,
        {'role': 'user', 'parts': [{'text': check_prompt}]}
    ]
    
    # 3. 调用LLM判断（使用相同的模型和配置）
    try:
        response = await client.generate_json(
            contents,
            NEXT_SPEAKER_SCHEMA,
            signal,
            # 使用临时系统指令覆盖（不影响主对话）
            system_instruction=""  # 清空系统指令，专注判断任务
        )
        return response
    except Exception as e:
        # 判断失败时的默认行为
        return {
            'next_speaker': 'user',
            'reasoning': f'Failed to determine next speaker: {str(e)}'
        }

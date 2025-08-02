"""
API Key 检查工具
检查各个模型所需的 API Key 是否已配置
"""

import os
from typing import Tuple, Optional, List
from ..ui.console import console
from ..i18n import _


def check_api_key_for_model(model: str) -> Tuple[bool, Optional[str]]:
    """
    检查指定模型的 API Key 是否已配置
    
    Args:
        model: 模型名称
        
    Returns:
        (是否配置, 缺失的环境变量名)
    """
    model_lower = model.lower()
    
    # Gemini 系列
    if 'gemini' in model_lower:
        if os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY'):
            return True, None
        return False, 'api_key_gemini'
    
    # Claude 系列
    elif any(name in model_lower for name in ['claude', 'sonnet', 'opus']):
        if os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('CLAUDE_API_KEY'):
            return True, None
        return False, 'api_key_claude'
    
    # OpenAI 系列
    elif any(name in model_lower for name in ['gpt', 'openai', 'o1', 'o3', 'o4']):
        if os.environ.get('OPENAI_API_KEY'):
            return True, None
        return False, 'api_key_openai'
    
    # 未知模型，假设不需要 API Key
    return True, None


def show_api_key_setup_guide(model: str):
    """
    显示 API Key 设置指南
    
    Args:
        model: 模型名称
    """
    has_key, key_type = check_api_key_for_model(model)
    
    if not has_key and key_type:
        console.print(f"\n[yellow]{_('api_key_missing', model=model)}[/yellow]")
        console.print(f"\n{_('api_key_setup')}")
        console.print(f"  [cyan]{_(key_type)}[/cyan]")
        
        console.print(f"\n{_('api_key_instructions')}")
        
        # 根据模型类型显示对应的 URL
        model_lower = model.lower()
        if 'gemini' in model_lower:
            console.print(f"  [blue]{_('api_key_gemini_url')}[/blue]")
        elif any(name in model_lower for name in ['claude', 'sonnet', 'opus']):
            console.print(f"  [blue]{_('api_key_claude_url')}[/blue]")
        elif any(name in model_lower for name in ['gpt', 'openai', 'o1', 'o3']):
            console.print(f"  [blue]{_('api_key_openai_url')}[/blue]")
        
        console.print(f"\n[dim]{_('api_key_reminder')}[/dim]\n")
        return True
    
    return False


def check_all_api_keys() -> List[str]:
    """
    检查所有常用模型的 API Key 配置情况
    
    Returns:
        未配置 API Key 的模型列表
    """
    missing_models = []
    
    # 检查主要模型
    models_to_check = [
        ('gemini', 'Gemini'),
        ('claude', 'Claude'),
        ('gpt', 'OpenAI GPT')
    ]
    
    for model_key, model_name in models_to_check:
        has_key, _ = check_api_key_for_model(model_key)
        if not has_key:
            missing_models.append(model_name)
    
    return missing_models
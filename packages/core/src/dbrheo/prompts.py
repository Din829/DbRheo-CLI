"""
提示词管理系统
参考Gemini CLI的分层提示词设计
"""

import datetime
from typing import Dict, Optional, List
from .config.base import DatabaseConfig
from .prompts.database_agent_prompt import get_database_agent_prompt, get_tool_guidance

# 东京时区常量
TOKYO_TZ = datetime.timezone(datetime.timedelta(hours=9))


class PromptManager:
    """
    提示词管理器 - 分层系统
    优先级：用户自定义 > 工作区配置 > 系统默认
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._cache = {}
        
    def get_system_prompt(self, context: Optional[Dict] = None) -> str:
        """
        获取系统提示词
        支持上下文感知和动态调整
        """
        # 检查用户自定义提示词
        custom_prompt = self.config.get("custom_system_prompt")
        if custom_prompt:
            return self._process_template(custom_prompt, context)
            
        # 使用默认的数据库Agent提示词
        base_prompt = get_database_agent_prompt()
        
        # 添加当前时间（东京时间）
        tokyo_time = datetime.datetime.now(TOKYO_TZ)
        base_prompt += f"\n\nCurrent Tokyo time: {tokyo_time.strftime('%Y-%m-%d %H:%M:%S JST')}"
        
        # 添加语言提示
        # 检查当前语言设置
        if hasattr(self.config, 'get') and self.config.get('i18n'):
            i18n = self.config.get('i18n')
            if isinstance(i18n, dict) and 'current_lang' in i18n:
                current_lang = i18n['current_lang']()
                if current_lang == 'ja_JP':
                    base_prompt += "\n日本語で応答する際は、中国語を混在させず、専門用語は正確に、自然な日本語表現を使用してください。"
                elif current_lang == 'zh_CN':
                    base_prompt += "\n使用中文回复时，请使用规范的简体中文和准确的技术术语。"
                elif current_lang == 'en_US':
                    base_prompt += "\nUse clear, professional English with accurate technical terminology."
        
        # 添加上下文特定的指导
        if context:
            additional_guidance = self._get_contextual_guidance(context)
            if additional_guidance:
                base_prompt += f"\n\n## Current Context\n{additional_guidance}"
                
        return base_prompt
        
    def get_tool_prompt(self, tool_name: str) -> str:
        """获取工具特定的提示词"""
        # 检查缓存
        if tool_name in self._cache:
            return self._cache[tool_name]
            
        # 获取工具指导
        guidance = get_tool_guidance(tool_name)
        
        # 添加用户自定义的工具提示
        custom_tool_prompts = self.config.get("tool_prompts", {})
        if tool_name in custom_tool_prompts:
            guidance = custom_tool_prompts[tool_name] + "\n\n" + guidance
            
        self._cache[tool_name] = guidance
        return guidance
        
    def get_next_speaker_prompt(self) -> str:
        """获取next_speaker判断的提示词"""
        return """Based on the conversation history and the last message, determine who should speak next.

Rules:
1. If the last message was a tool execution result (function response), return "model" to process the result
2. If the model asked a question that needs user input, return "user"  
3. If the model indicated it will perform more actions, return "model"
4. If the task is complete and waiting for new instructions, return "user"

Respond with a JSON object: {"next_speaker": "model" or "user", "reasoning": "brief explanation"}"""
        
    def _get_contextual_guidance(self, context: Dict) -> str:
        """基于上下文生成额外指导"""
        guidance_parts = []
        
        # 数据库连接信息
        if 'database_type' in context:
            db_type = context['database_type']
            guidance_parts.append(f"You are connected to a {db_type} database.")
            
        # 已发现的表
        if 'discovered_tables' in context:
            tables = context['discovered_tables']
            if tables:
                guidance_parts.append(f"Previously discovered tables: {', '.join(tables[:10])}")
                
        # 当前任务类型
        if 'task_type' in context:
            task_type = context['task_type']
            if task_type == 'exploration':
                guidance_parts.append("Focus on understanding the database structure and relationships.")
            elif task_type == 'analysis':
                guidance_parts.append("Focus on extracting insights and patterns from the data.")
            elif task_type == 'modification':
                guidance_parts.append("Be extra careful with data modifications. Always verify impact.")
                
        return "\n".join(guidance_parts)
        
    def _process_template(self, template: str, context: Optional[Dict]) -> str:
        """处理提示词模板中的变量"""
        if not context:
            return template
            
        # 简单的变量替换
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
            
        return template


class PromptLibrary:
    """
    提示词库 - 存储常用提示词模板
    """
    
    # 错误恢复提示词
    ERROR_RECOVERY = """The previous operation failed with error: {error}

Analyze the error and try an alternative approach. Consider:
1. Syntax issues in the SQL
2. Missing tables or columns
3. Permission problems
4. Data type mismatches

Provide a clear explanation and attempt a different solution."""
    
    # 性能优化提示词
    PERFORMANCE_OPTIMIZATION = """The query is taking too long or consuming too many resources.

Consider these optimization strategies:
1. Add appropriate indexes
2. Limit the result set
3. Use more efficient JOIN strategies
4. Partition large tables
5. Pre-aggregate data

Suggest specific improvements for this query."""
    
    # 数据探索提示词
    DATA_EXPLORATION = """Help the user explore and understand their database.

Start with:
1. Overview of available tables
2. Identify key business entities
3. Discover relationships between tables
4. Highlight interesting patterns or anomalies

Guide them through progressive discovery."""
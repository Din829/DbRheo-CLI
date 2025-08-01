"""
LLM 服务工厂 - 根据配置动态创建不同的 LLM 服务
设计原则：灵活性、可扩展性、最小侵入性
"""

from typing import Dict, Type, Optional
from ..config.base import DatabaseConfig
from ..utils.debug_logger import log_info


class LLMServiceFactory:
    """
    LLM 服务工厂类
    - 动态服务创建
    - 灵活的模型映射
    - 易于扩展新模型
    """
    
    # 模型映射表 - 避免硬编码，便于扩展
    MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
        "gemini": {
            "module": "gemini_service",
            "class": "GeminiService",
            "prefixes": ["gemini", "models/gemini"]  # 支持多种前缀
        },
        "claude": {
            "module": "claude_service", 
            "class": "ClaudeService",
            "prefixes": ["claude", "anthropic", "sonnet", "opus", "haiku"]  # 支持 sonnet4, opus4 等
        },
        "openai": {
            "module": "openai_service",
            "class": "OpenAIService", 
            "prefixes": ["gpt", "openai", "o1"]
        }
    }
    
    @staticmethod
    def create_llm_service(config: DatabaseConfig):
        """
        根据配置创建相应的 LLM 服务
        
        Args:
            config: 数据库配置对象
            
        Returns:
            LLM 服务实例
            
        Raises:
            ValueError: 当模型不被支持时
        """
        model_name = config.get_model()
        
        # 查找匹配的服务
        service_info = LLMServiceFactory._find_service_for_model(model_name)
        
        if not service_info:
            # 如果没有找到匹配，默认使用 Gemini（保持向后兼容）
            log_info("LLMFactory", f"Model '{model_name}' not recognized, using Gemini as default")
            service_info = LLMServiceFactory.MODEL_MAPPINGS["gemini"]
        
        # 动态导入和创建服务
        try:
            module_name = service_info['module']
            class_name = service_info['class']
            
            # 动态导入 - 使用相对导入
            from importlib import import_module
            full_module_name = f".{module_name}"
            module = import_module(full_module_name, package='dbrheo.services')
            service_class = getattr(module, class_name)
            
            # 创建实例
            log_info("LLMFactory", f"Creating {class_name} for model '{model_name}'")
            return service_class(config)
            
        except ImportError as e:
            # 如果服务类还未实现，回退到 Gemini
            log_info("LLMFactory", f"Failed to import {service_info['module']}: {e}")
            log_info("LLMFactory", "Falling back to GeminiService")
            
            from .gemini_service import GeminiService
            return GeminiService(config)
        except ValueError as e:
            # 配置错误（如缺少 API key）
            log_info("LLMFactory", f"Configuration error for {class_name}: {e}")
            raise
            
        except Exception as e:
            log_info("LLMFactory", f"Error creating service: {e}")
            raise
    
    @staticmethod
    def _find_service_for_model(model_name: str) -> Optional[Dict[str, str]]:
        """
        根据模型名称查找对应的服务信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            服务信息字典或 None
        """
        model_lower = model_name.lower()
        
        # 遍历所有映射，查找匹配的前缀
        for service_name, service_info in LLMServiceFactory.MODEL_MAPPINGS.items():
            for prefix in service_info["prefixes"]:
                if model_lower.startswith(prefix.lower()):
                    return service_info
                    
        return None
    
    @staticmethod
    def register_model_mapping(service_name: str, module: str, class_name: str, prefixes: list):
        """
        注册新的模型映射（便于运行时扩展）
        
        Args:
            service_name: 服务名称
            module: 模块名
            class_name: 类名
            prefixes: 模型前缀列表
        """
        LLMServiceFactory.MODEL_MAPPINGS[service_name] = {
            "module": module,
            "class": class_name,
            "prefixes": prefixes
        }
        log_info("LLMFactory", f"Registered new model mapping: {service_name}")


# 导出便捷函数
def create_llm_service(config: DatabaseConfig):
    """便捷函数 - 创建 LLM 服务"""
    return LLMServiceFactory.create_llm_service(config)
"""
参数清理工具 - 清理工具参数中不被 Google AI SDK 支持的字段
参考 Gemini CLI 的 sanitizeParameters 实现
"""

from typing import Dict, Any, Set


def sanitize_parameters(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理参数模式，移除 Google AI SDK 不支持的字段
    
    Args:
        schema: 原始参数模式
        
    Returns:
        清理后的参数模式
    """
    if not schema:
        return schema
        
    # 创建副本以避免修改原始数据
    cleaned_schema = schema.copy()
    
    # 使用集合追踪已访问的对象，防止循环引用
    visited = set()
    
    _sanitize_parameters_recursive(cleaned_schema, visited)
    
    return cleaned_schema


def _sanitize_parameters_recursive(schema: Dict[str, Any], visited: Set[int]):
    """
    递归清理参数模式
    
    Args:
        schema: 当前处理的模式
        visited: 已访问对象的集合
    """
    # 防止循环引用
    schema_id = id(schema)
    if schema_id in visited:
        return
    visited.add(schema_id)
    
    # 移除不支持的字段
    unsupported_fields = [
        'default',      # Protocol message Schema has no "default" field
        'minimum',      # Protocol message Schema has no "minimum" field
        'maximum',      # Protocol message Schema has no "maximum" field
        'minLength',    # 可能不支持
        'maxLength',    # 可能不支持
        'minItems',     # 可能不支持
        'maxItems',     # 可能不支持
        'uniqueItems',  # 可能不支持
        'additionalProperties',  # 可能不支持
        '$schema',      # JSON Schema 元数据
        '$ref',         # JSON Schema 引用
        '$defs',        # JSON Schema 定义
    ]
    
    for field in unsupported_fields:
        if field in schema:
            del schema[field]
    
    # 处理 format 字段 - 只保留 'enum' 和 'date-time'
    if schema.get('type') == 'string' and 'format' in schema:
        if schema['format'] not in ['enum', 'date-time']:
            del schema['format']
    
    # 递归处理 properties
    if 'properties' in schema and isinstance(schema['properties'], dict):
        for prop_name, prop_schema in schema['properties'].items():
            if isinstance(prop_schema, dict):
                _sanitize_parameters_recursive(prop_schema, visited)
    
    # 递归处理 items（数组类型）
    if 'items' in schema and isinstance(schema['items'], dict):
        _sanitize_parameters_recursive(schema['items'], visited)
    
    # 递归处理 anyOf
    if 'anyOf' in schema and isinstance(schema['anyOf'], list):
        for item in schema['anyOf']:
            if isinstance(item, dict):
                _sanitize_parameters_recursive(item, visited)
    
    # 递归处理 oneOf
    if 'oneOf' in schema and isinstance(schema['oneOf'], list):
        for item in schema['oneOf']:
            if isinstance(item, dict):
                _sanitize_parameters_recursive(item, visited)
    
    # 递归处理 allOf
    if 'allOf' in schema and isinstance(schema['allOf'], list):
        for item in schema['allOf']:
            if isinstance(item, dict):
                _sanitize_parameters_recursive(item, visited)
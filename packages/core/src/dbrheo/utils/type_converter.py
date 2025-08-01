"""
类型转换工具 - 处理数据库返回的特殊类型
确保所有数据都能被 Gemini API 序列化
"""

from decimal import Decimal
from datetime import datetime, date, time
from typing import Any, Dict, List, Union
import json


def convert_to_serializable(value: Any) -> Any:
    """
    将数据库返回的特殊类型转换为可序列化的基本类型
    
    支持的转换：
    - Decimal -> float
    - datetime/date/time -> ISO格式字符串
    - bytes -> base64字符串（如果需要）
    - 嵌套的字典和列表递归处理
    """
    if value is None:
        return None
        
    # Decimal 转换为 float
    if isinstance(value, Decimal):
        # 保持精度，但转换为 float
        return float(value)
        
    # 日期时间类型转换为 ISO 格式字符串
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, time):
        return value.isoformat()
        
    # bytes 类型转换（如果需要可以转为 base64）
    elif isinstance(value, bytes):
        try:
            # 尝试 UTF-8 解码
            return value.decode('utf-8')
        except UnicodeDecodeError:
            # 如果解码失败，转为十六进制字符串
            return value.hex()
            
    # 递归处理字典
    elif isinstance(value, dict):
        return {k: convert_to_serializable(v) for k, v in value.items()}
        
    # 递归处理列表
    elif isinstance(value, (list, tuple)):
        return [convert_to_serializable(item) for item in value]
        
    # 其他类型尝试直接返回
    else:
        # 检查是否可以被 JSON 序列化
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            # 如果不能序列化，转为字符串
            return str(value)


def convert_row_to_serializable(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    转换数据库查询结果的单行数据
    """
    return convert_to_serializable(row)


def convert_rows_to_serializable(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    转换数据库查询结果的多行数据
    """
    return [convert_row_to_serializable(row) for row in rows]
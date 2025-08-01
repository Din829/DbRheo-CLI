"""
自定义异常类 - 提供结构化的错误处理
定义数据库Agent特有的异常类型
"""

from typing import Optional, Dict, Any


class DatabaseAgentError(Exception):
    """数据库Agent基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class ToolExecutionError(DatabaseAgentError):
    """工具执行异常"""
    
    def __init__(
        self, 
        tool_name: str,
        message: str,
        original_error: Optional[Exception] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.tool_name = tool_name
        self.original_error = original_error
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "tool_name": self.tool_name,
            "original_error": str(self.original_error) if self.original_error else None
        })
        return result


class ValidationError(DatabaseAgentError):
    """参数验证异常"""
    
    def __init__(
        self, 
        field_name: str,
        message: str,
        invalid_value: Any = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.field_name = field_name
        self.invalid_value = invalid_value
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "field_name": self.field_name,
            "invalid_value": self.invalid_value
        })
        return result


class DatabaseConnectionError(DatabaseAgentError):
    """数据库连接异常"""
    
    def __init__(
        self, 
        database_name: str,
        message: str,
        connection_string: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.database_name = database_name
        self.connection_string = connection_string
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "database_name": self.database_name,
            "connection_string": self.connection_string
        })
        return result


class SQLExecutionError(DatabaseAgentError):
    """SQL执行异常"""
    
    def __init__(
        self, 
        sql: str,
        message: str,
        error_position: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.sql = sql
        self.error_position = error_position
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "sql": self.sql,
            "error_position": self.error_position
        })
        return result


class ConfigurationError(DatabaseAgentError):
    """配置异常"""
    
    def __init__(
        self, 
        config_key: str,
        message: str,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.config_key = config_key
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "config_key": self.config_key
        })
        return result


class PermissionError(DatabaseAgentError):
    """权限异常"""
    
    def __init__(
        self, 
        operation: str,
        resource: str,
        message: str,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.operation = operation
        self.resource = resource
        
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "operation": self.operation,
            "resource": self.resource
        })
        return result

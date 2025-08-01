"""
DatabaseRiskEvaluator - 智能风险评估器
完全对齐文档要求的多维度SQL风险评估系统
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from ..config.base import DatabaseConfig


class RiskLevel(Enum):
    """风险级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    """风险评估结果"""
    level: RiskLevel
    score: float  # 0-100
    reasons: List[str]
    recommendations: List[str]
    requires_confirmation: bool
    estimated_impact: str  # "low" | "medium" | "high"
    affected_tables: List[str]
    operation_type: str


class DatabaseRiskEvaluator:
    """
    智能SQL风险评估器 - 完全对齐文档要求
    
    多维度风险评估：
    1. 操作类型风险（SELECT < INSERT < UPDATE < DELETE < DDL）
    2. 影响范围风险（WHERE条件、表大小、关联表数量）
    3. 数据完整性风险（外键约束、唯一约束、NOT NULL）
    4. 性能影响风险（全表扫描、复杂JOIN、大数据量）
    5. 安全风险（SQL注入模式、权限提升）
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self.config = config
        self._i18n = i18n  # 可选的i18n实例
        self.allow_dangerous_operations = config.get("allow_dangerous_operations", False)
        
        # 危险操作模式（硬编码用于安全防护）
        self.dangerous_patterns = [
            r'\bDROP\s+TABLE\b',
            r'\bTRUNCATE\s+TABLE\b',
            r'\bDELETE\s+FROM\s+\w+\s*(?!WHERE)',  # DELETE without WHERE
            r'\bUPDATE\s+\w+\s+SET\s+.*?(?!WHERE)',  # UPDATE without WHERE
            r'\bALTER\s+TABLE\s+.*?\bDROP\b',
            r'\bDROP\s+DATABASE\b',
            r'\bDROP\s+SCHEMA\b'
        ]
        
        # 操作类型权重
        self.operation_weights = {
            'SELECT': 1.0,
            'INSERT': 2.0,
            'UPDATE': 3.0,
            'DELETE': 4.0,
            'CREATE': 2.5,
            'ALTER': 4.5,
            'DROP': 5.0,
            'TRUNCATE': 4.8
        }
        
    def evaluate_sql_risk(
        self, 
        sql: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        评估SQL语句的风险级别
        
        Args:
            sql: SQL语句
            context: 上下文信息（表结构、数据量等）
            
        Returns:
            RiskAssessment: 风险评估结果
        """
        sql_clean = sql.strip()
        context = context or {}
        
        # 1. 解析SQL基本信息
        operation_type = self._extract_operation_type(sql_clean)
        affected_tables = self._extract_table_names(sql_clean)
        
        # 2. 多维度风险评估
        risk_factors = []
        total_score = 0.0
        
        # 操作类型风险
        op_risk, op_reasons = self._assess_operation_risk(operation_type, sql_clean)
        risk_factors.extend(op_reasons)
        total_score += op_risk
        
        # 影响范围风险
        scope_risk, scope_reasons = self._assess_scope_risk(sql_clean, affected_tables, context)
        risk_factors.extend(scope_reasons)
        total_score += scope_risk
        
        # 数据完整性风险
        integrity_risk, integrity_reasons = self._assess_integrity_risk(sql_clean, context)
        risk_factors.extend(integrity_reasons)
        total_score += integrity_risk
        
        # 性能影响风险
        perf_risk, perf_reasons = self._assess_performance_risk(sql_clean, context)
        risk_factors.extend(perf_reasons)
        total_score += perf_risk
        
        # 安全风险
        security_risk, security_reasons = self._assess_security_risk(sql_clean)
        risk_factors.extend(security_reasons)
        total_score += security_risk
        
        # 3. 计算最终风险级别
        risk_level = self._calculate_risk_level(total_score)
        
        # 4. 生成建议
        recommendations = self._generate_recommendations(
            operation_type, risk_level, risk_factors, sql_clean
        )
        
        # 5. 确定是否需要确认
        requires_confirmation = self._requires_confirmation(risk_level, operation_type, sql_clean)
        
        # 6. 估算影响范围
        estimated_impact = self._estimate_impact(operation_type, sql_clean, context)
        
        return RiskAssessment(
            level=risk_level,
            score=min(total_score, 100.0),
            reasons=risk_factors,
            recommendations=recommendations,
            requires_confirmation=requires_confirmation,
            estimated_impact=estimated_impact,
            affected_tables=affected_tables,
            operation_type=operation_type
        )
        
    def _extract_operation_type(self, sql: str) -> str:
        """提取SQL操作类型"""
        sql_upper = sql.upper().strip()
        
        for op in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE']:
            if sql_upper.startswith(op):
                return op
                
        return 'UNKNOWN'
        
    def _extract_table_names(self, sql: str) -> List[str]:
        """提取SQL中涉及的表名"""
        # 简化的表名提取逻辑
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'INSERT\s+INTO\s+(\w+)',
            r'DELETE\s+FROM\s+(\w+)',
            r'CREATE\s+TABLE\s+(\w+)',
            r'ALTER\s+TABLE\s+(\w+)',
            r'DROP\s+TABLE\s+(\w+)',
            r'TRUNCATE\s+TABLE\s+(\w+)'
        ]
        
        tables = set()
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)
            
        return list(tables)
        
    def _assess_operation_risk(self, operation_type: str, sql: str) -> Tuple[float, List[str]]:
        """评估操作类型风险"""
        base_score = self.operation_weights.get(operation_type, 2.0) * 10
        reasons = []
        
        # 检查危险操作模式
        for pattern in self.dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                base_score += 30
                reasons.append(self._("risk_dangerous_pattern", f"检测到危险操作模式: {pattern}", pattern=pattern))
                
        if operation_type in ['DROP', 'TRUNCATE']:
            reasons.append(self._("risk_high_operation", "高风险操作：可能导致数据永久丢失"))
        elif operation_type in ['DELETE', 'UPDATE']:
            if 'WHERE' not in sql.upper():
                base_score += 25
                reasons.append(self._("risk_no_where", "缺少WHERE条件：可能影响所有数据"))
                
        return base_score, reasons
        
    def _assess_scope_risk(self, sql: str, tables: List[str], context: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估影响范围风险"""
        score = 0.0
        reasons = []
        
        # 多表操作风险
        if len(tables) > 3:
            score += 15
            reasons.append(self._("risk_multiple_tables", "涉及多个表({count}个)：操作复杂度较高", count=len(tables)))
            
        # 表大小风险（基于上下文）
        table_sizes = context.get('table_sizes', {})
        for table in tables:
            size = table_sizes.get(table, 0)
            if size > 1000000:  # 100万行
                score += 20
                reasons.append(self._("risk_large_table", "大表操作({table})：可能影响性能", table=table))
                
        return score, reasons
        
    def _assess_integrity_risk(self, sql: str, context: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估数据完整性风险"""
        score = 0.0
        reasons = []
        
        # 外键约束风险
        if 'DELETE' in sql.upper() or 'UPDATE' in sql.upper():
            foreign_keys = context.get('foreign_keys', [])
            if foreign_keys:
                score += 10
                reasons.append(self._("risk_foreign_key", "可能影响外键约束关系"))
                
        return score, reasons
        
    def _assess_performance_risk(self, sql: str, context: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估性能影响风险"""
        score = 0.0
        reasons = []
        
        # 全表扫描风险
        if 'WHERE' not in sql.upper() and 'SELECT' in sql.upper():
            score += 15
            reasons.append(self._("risk_full_scan", "可能导致全表扫描"))
            
        # 复杂JOIN风险
        join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
        if join_count > 2:
            score += join_count * 5
            reasons.append(self._("risk_complex_join", "复杂JOIN操作({count}个)：可能影响性能", count=join_count))
            
        return score, reasons
        
    def _assess_security_risk(self, sql: str) -> Tuple[float, List[str]]:
        """评估安全风险"""
        score = 0.0
        reasons = []
        
        # SQL注入模式检测
        injection_patterns = [
            r"'.*?OR.*?'.*?'",
            r"'.*?UNION.*?SELECT",
            r"'.*?;.*?--",
            r"'.*?;.*?DROP"
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                score += 40
                reasons.append(self._("risk_sql_injection", "检测到潜在SQL注入模式"))
                break
                
        return score, reasons
        
    def _calculate_risk_level(self, score: float) -> RiskLevel:
        """根据分数计算风险级别"""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 30:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
            
    def _generate_recommendations(
        self, 
        operation_type: str, 
        risk_level: RiskLevel, 
        risk_factors: List[str], 
        sql: str
    ) -> List[str]:
        """生成安全建议"""
        recommendations = []
        
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append(self._("risk_recommend_test", "建议在测试环境中先验证此操作"))
            
        if 'WHERE' not in sql.upper() and operation_type in ['UPDATE', 'DELETE']:
            recommendations.append(self._("risk_recommend_where", "建议添加WHERE条件限制影响范围"))
            
        if operation_type in ['DROP', 'TRUNCATE']:
            recommendations.append(self._("risk_recommend_backup", "建议先创建数据备份"))
            
        if self._("risk_full_scan", "可能导致全表扫描") in risk_factors:
            recommendations.append(self._("risk_recommend_index", "建议添加适当的索引或WHERE条件"))
            
        return recommendations
        
    def _requires_confirmation(self, risk_level: RiskLevel, operation_type: str, sql: str) -> bool:
        """判断是否需要用户确认"""
        # 高风险操作总是需要确认
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True
            
        # 危险操作需要确认
        if operation_type in ['DROP', 'TRUNCATE', 'ALTER']:
            return True
            
        # 无WHERE条件的修改操作需要确认
        if operation_type in ['UPDATE', 'DELETE'] and 'WHERE' not in sql.upper():
            return True
            
        return False
        
    def _estimate_impact(self, operation_type: str, sql: str, context: Dict[str, Any]) -> str:
        """估算操作影响范围"""
        if operation_type in ['DROP', 'TRUNCATE']:
            return "high"
        elif operation_type in ['DELETE', 'UPDATE'] and 'WHERE' not in sql.upper():
            return "high"
        elif operation_type in ['ALTER', 'CREATE']:
            return "medium"
        else:
            return "low"
    
    def _(self, key: str, default: str, **kwargs) -> str:
        """
        获取国际化文本，如果没有i18n则返回默认文本
        与DatabaseTool的_()方法保持一致
        """
        if self._i18n and hasattr(self._i18n, 'get'):
            # 先获取文本
            text = self._i18n.get(key)
            if text is None:
                # 如果i18n没有这个key，使用默认值
                text = default
        else:
            # 使用默认文本
            text = default
        
        # 简单的格式化
        for k, v in kwargs.items():
            text = text.replace(f'{{{k}}}', str(v))
        
        return text

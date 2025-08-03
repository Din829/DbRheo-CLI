"""
Token 使用统计管理
最小侵入性设计，用于收集和聚合 token 使用数据
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TokenUsageRecord:
    """单次 API 调用的 token 使用记录"""
    timestamp: datetime
    model: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    
    
@dataclass 
class TokenStatistics:
    """会话级 token 统计"""
    records: List[TokenUsageRecord] = field(default_factory=list)
    
    def add_usage(self, model: str, usage_data: Dict[str, Any]):
        """添加一次使用记录"""
        record = TokenUsageRecord(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=usage_data.get('prompt_tokens', 0),
            completion_tokens=usage_data.get('completion_tokens', 0),
            total_tokens=usage_data.get('total_tokens', 0)
        )
        
        # 详细调试
        from ..utils.debug_logger import log_info
        log_info("TokenStats", f"📦 ADDING RECORD #{len(self.records) + 1}:")
        log_info("TokenStats", f"   - Model: {model}")
        log_info("TokenStats", f"   - prompt_tokens: {record.prompt_tokens}")
        log_info("TokenStats", f"   - completion_tokens: {record.completion_tokens}")
        log_info("TokenStats", f"   - total_tokens: {record.total_tokens}")
        log_info("TokenStats", f"   - Timestamp: {record.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # 显示当前累计
        current_total = sum(r.total_tokens or 0 for r in self.records)
        log_info("TokenStats", f"   - Running total BEFORE: {current_total}")
        log_info("TokenStats", f"   - Running total AFTER: {current_total + (record.total_tokens or 0)}")
        
        self.records.append(record)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        if not self.records:
            return {
                'total_calls': 0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_tokens': 0,
                'by_model': {}
            }
        
        # 计算总计 - 处理可能的 None 值
        total_prompt = sum(r.prompt_tokens or 0 for r in self.records)
        total_completion = sum(r.completion_tokens or 0 for r in self.records)
        
        # 按模型分组统计
        by_model = {}
        for record in self.records:
            if record.model not in by_model:
                by_model[record.model] = {
                    'calls': 0,
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                }
            by_model[record.model]['calls'] += 1
            by_model[record.model]['prompt_tokens'] += record.prompt_tokens or 0
            by_model[record.model]['completion_tokens'] += record.completion_tokens or 0
            by_model[record.model]['total_tokens'] += record.total_tokens or 0
        
        return {
            'total_calls': len(self.records),
            'total_prompt_tokens': total_prompt,
            'total_completion_tokens': total_completion,
            'total_tokens': total_prompt + total_completion,
            'by_model': by_model
        }
    
    def get_cost_estimate(self) -> Dict[str, float]:
        """获取成本估算（基于公开价格）"""
        # 2025年1月的参考价格（每1M tokens）
        pricing = {
            'gemini-2.5-flash': {'input': 0.075, 'output': 0.30},  # $0.075/$0.30 per 1M
            'gemini-1.5-pro': {'input': 1.25, 'output': 5.00},     # $1.25/$5.00 per 1M
            'claude-3.5-sonnet': {'input': 3.00, 'output': 15.00}, # $3/$15 per 1M
            'gpt-4.1': {'input': 2.50, 'output': 10.00},           # $2.50/$10 per 1M
            'gpt-4.1-mini': {'input': 0.15, 'output': 0.60}        # $0.15/$0.60 per 1M
        }
        
        total_cost = 0.0
        cost_by_model = {}
        
        for model, stats in self.get_summary()['by_model'].items():
            # 查找价格（支持模型别名）
            model_pricing = None
            for key in pricing:
                if key in model.lower():
                    model_pricing = pricing[key]
                    break
            
            if model_pricing:
                input_cost = (stats['prompt_tokens'] / 1_000_000) * model_pricing['input']
                output_cost = (stats['completion_tokens'] / 1_000_000) * model_pricing['output']
                model_cost = input_cost + output_cost
                
                cost_by_model[model] = {
                    'input_cost': input_cost,
                    'output_cost': output_cost,
                    'total_cost': model_cost
                }
                total_cost += model_cost
        
        return {
            'total_cost': total_cost,
            'by_model': cost_by_model
        }
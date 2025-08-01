"""
编码检测和处理工具 - 支持多语言系统
设计原则：动态检测、智能适配、最小侵入
"""

import os
import sys
import platform
import locale
import subprocess
from typing import List, Optional, Tuple


class EncodingDetector:
    """智能编码检测器 - 自动适应不同语言系统"""
    
    # 编码组定义 - 按语言分组
    ENCODING_GROUPS = {
        'japanese': ['cp932', 'shift_jis', 'euc_jp', 'iso2022_jp', 'utf-8'],
        'chinese': ['gbk', 'gb18030', 'gb2312', 'big5', 'utf-8'],
        'korean': ['cp949', 'euc_kr', 'utf-8'],
        'western': ['cp1252', 'latin-1', 'iso-8859-1', 'utf-8'],
        'cyrillic': ['cp1251', 'koi8-r', 'utf-8'],
        'universal': ['utf-8', 'utf-16', 'utf-32']
    }
    
    # Windows代码页映射
    CODEPAGE_MAP = {
        932: 'japanese',    # 日语
        936: 'chinese',     # 简体中文
        950: 'chinese',     # 繁体中文
        949: 'korean',      # 韩语
        1251: 'cyrillic',   # 西里尔文
        1252: 'western',    # 西欧
    }
    
    @classmethod
    def get_system_encoding(cls) -> str:
        """获取系统默认编码 - 优先使用系统设置"""
        # 1. 尝试从环境变量获取
        env_encoding = os.environ.get('DBRHEO_ENCODING')
        if env_encoding:
            return env_encoding
            
        # 2. 尝试获取系统首选编码
        try:
            preferred = locale.getpreferredencoding(False)
            if preferred and preferred.lower() != 'ascii':
                return preferred
        except:
            pass
            
        # 3. Windows特殊处理 - 获取控制台代码页
        if platform.system() == 'Windows':
            try:
                # 获取活动代码页
                result = subprocess.run(
                    ['cmd', '/c', 'chcp'], 
                    capture_output=True, 
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    # 解析输出，如 "活动代码页: 932" 或 "Active code page: 932"
                    import re
                    match = re.search(r':\s*(\d+)', result.stdout)
                    if match:
                        codepage = int(match.group(1))
                        # 返回对应的Python编码名
                        if codepage == 932:
                            return 'cp932'
                        elif codepage == 936:
                            return 'cp936'
                        elif codepage == 950:
                            return 'cp950'
                        elif codepage == 949:
                            return 'cp949'
                        elif codepage == 65001:
                            return 'utf-8'
            except:
                pass
                
        # 4. 默认UTF-8
        return 'utf-8'
    
    @classmethod
    def get_encoding_candidates(cls, 
                              for_platform: Optional[str] = None,
                              for_shell: bool = False) -> List[str]:
        """
        获取编码候选列表 - 根据系统智能排序
        
        Args:
            for_platform: 指定平台 ('Windows', 'Darwin', 'Linux')
            for_shell: 是否用于Shell输出解码
            
        Returns:
            编码列表，按可能性排序
        """
        candidates = []
        system_encoding = cls.get_system_encoding()
        
        # 1. 系统编码优先
        if system_encoding and system_encoding not in candidates:
            candidates.append(system_encoding)
            
        # 2. 根据平台添加常见编码
        current_platform = for_platform or platform.system()
        
        if current_platform == 'Windows':
            # Windows: 检测代码页类型
            codepage = cls._get_windows_codepage()
            group = cls.CODEPAGE_MAP.get(codepage, 'western')
            
            # 添加对应语言组的编码
            if group in cls.ENCODING_GROUPS:
                candidates.extend(cls.ENCODING_GROUPS[group])
                
            # Shell输出可能需要额外编码
            if for_shell:
                # 确保包含所有可能的编码
                candidates.extend(['cp437', 'cp850'])  # DOS编码
                
        elif current_platform == 'Darwin':  # macOS
            candidates.extend(['utf-8', 'utf-16'])
            
        else:  # Linux/Unix
            candidates.extend(['utf-8', 'latin-1'])
            
        # 3. 添加通用编码作为后备
        candidates.extend(['utf-8', 'latin-1', 'ascii'])
        
        # 4. 去重并保持顺序
        seen = set()
        unique_candidates = []
        for enc in candidates:
            if enc not in seen:
                seen.add(enc)
                unique_candidates.append(enc)
                
        return unique_candidates
    
    @classmethod
    def _get_windows_codepage(cls) -> int:
        """获取Windows活动代码页号"""
        try:
            import ctypes
            codepage = ctypes.windll.kernel32.GetConsoleCP()
            # 验证代码页有效性
            if codepage > 0:
                return codepage
        except Exception:
            # 无法获取代码页，这在某些环境下是正常的
            pass
            
        # 返回默认西欧代码页
        return 1252
    
    # 编码名称标准化映射
    ENCODING_ALIASES = {
        'shift-jis': 'shift_jis',
        'shift_jis': 'shift_jis',
        'sjis': 'shift_jis',
        'euc-jp': 'euc_jp',
        'euc_jp': 'euc_jp',
        'eucjp': 'euc_jp',
        'iso-2022-jp': 'iso2022_jp',
        'iso2022-jp': 'iso2022_jp',
        'gb2312': 'gbk',  # GB2312 是 GBK 的子集
        'gb18030': 'gb18030',
        'utf8': 'utf-8',
        'utf-8': 'utf-8',
        'utf_8': 'utf-8',
    }
    
    @classmethod
    def normalize_encoding(cls, encoding: str) -> str:
        """标准化编码名称"""
        if not encoding:
            return 'utf-8'
        
        # 转换为小写并移除空格
        encoding = encoding.lower().strip()
        
        # 使用别名映射
        return cls.ENCODING_ALIASES.get(encoding, encoding)
    
    @classmethod
    def smart_decode(cls, data: bytes, 
                    context: str = 'general',
                    errors: str = 'strict') -> Tuple[str, str]:
        """
        智能解码字节数据
        
        Args:
            data: 要解码的字节数据
            context: 上下文 ('shell', 'file', 'general')
            errors: 错误处理方式
            
        Returns:
            (解码后的字符串, 使用的编码)
        """
        if not data:
            return '', 'utf-8'
            
        # 获取候选编码列表
        candidates = cls.get_encoding_candidates(
            for_shell=(context == 'shell')
        )
        
        # 尝试每个编码
        for encoding in candidates:
            try:
                # 标准化编码名称
                normalized_encoding = cls.normalize_encoding(encoding)
                decoded = data.decode(normalized_encoding, errors='strict')
                return decoded, normalized_encoding
            except (UnicodeDecodeError, LookupError):
                continue
                
        # 如果都失败，使用替换错误处理
        for encoding in candidates[:3]:  # 只尝试前3个
            try:
                normalized_encoding = cls.normalize_encoding(encoding)
                decoded = data.decode(normalized_encoding, errors=errors)
                return decoded, normalized_encoding
            except (UnicodeDecodeError, LookupError):
                continue
                
        # 最后的后备：latin-1（永不失败）
        return data.decode('latin-1', errors='replace'), 'latin-1'
    
    @classmethod
    def get_file_encoding_candidates(cls) -> List[str]:
        """获取文件读取的编码候选列表"""
        candidates = cls.get_encoding_candidates()
        
        # 文件可能使用更多编码，添加常见的文件编码
        additional = [
            'utf-8-sig',  # 带BOM的UTF-8
            'utf-16-le', 'utf-16-be',  # UTF-16变体
            'iso-2022-jp',  # 日语邮件编码
            'hz',  # 中文编码
        ]
        
        for enc in additional:
            if enc not in candidates:
                candidates.append(enc)
                
        return candidates


# 便捷函数
def get_system_encoding() -> str:
    """获取系统编码"""
    return EncodingDetector.get_system_encoding()


def get_encoding_candidates(**kwargs) -> List[str]:
    """获取编码候选列表"""
    return EncodingDetector.get_encoding_candidates(**kwargs)


def smart_decode(data: bytes, **kwargs) -> Tuple[str, str]:
    """智能解码"""
    return EncodingDetector.smart_decode(data, **kwargs)
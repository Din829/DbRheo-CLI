"""
网页内容获取工具 - 参考 Gemini CLI 的 web-fetch 实现
可以获取 URL 的实际内容，并转换为文本
"""

import aiohttp
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig
from ..utils.retry_with_backoff import retry_with_backoff, RetryOptions


class WebFetchTool(DatabaseTool):
    """
    网页内容获取工具
    - 从 URL 获取实际内容
    - 支持 HTML 转文本
    - 支持多个 URL（最多 20 个）
    - 灵活处理各种网页格式
    """
    
    # 默认设置
    URL_FETCH_TIMEOUT = 10  # 秒
    MAX_CONTENT_LENGTH = 100000  # 100KB
    MAX_URLS = 20
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        super().__init__(
            name="web_fetch",
            display_name=self._('web_fetch_tool_name', default="网页内容获取") if i18n else "网页内容获取",
            description="Fetch and extract content from web pages. Use this after web_search to read the actual content of search results. Provide URLs and optional instructions for processing (e.g., 'summarize the key points').",
            parameter_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt containing URL(s) and instructions for processing the content"
                    },
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Direct list of URLs to fetch (alternative to embedding in prompt)"
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "Convert HTML to plain text (default: true)"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to extract specific content"
                    }
                },
                "required": ["prompt"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        # 标准化参数，处理 protobuf 对象
        params = self._normalize_params(params)
        
        prompt = params.get("prompt", "")
        urls = params.get("urls", [])
        
        # 从 prompt 中提取 URLs
        extracted_urls = self._extract_urls(prompt)
        
        # 合并所有 URLs
        all_urls = list(set(urls + extracted_urls))
        
        if not all_urls:
            return self._('web_fetch_no_urls', default="No URLs found in prompt or urls parameter")
            
        if len(all_urls) > self.MAX_URLS:
            return self._('web_fetch_too_many_urls', default="Too many URLs (max {max})", max=self.MAX_URLS)
            
        # 验证 URL 格式
        for url in all_urls:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return self._('web_fetch_invalid_url', default="Invalid URL: {url}", url=url)
                
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        # 标准化参数
        params = self._normalize_params(params)
        
        prompt = params.get("prompt", "")
        urls = params.get("urls", [])
        extracted_urls = self._extract_urls(prompt)
        all_urls = list(set(urls + extracted_urls))
        
        if len(all_urls) == 1:
            return self._('web_fetch_desc_single', default="获取网页内容: {url}...", url=all_urls[0][:50])
        else:
            return self._('web_fetch_desc_multiple', default="获取 {count} 个网页的内容", count=len(all_urls))
    
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Optional[Any]:
        """网页获取通常不需要确认，除非是内网地址"""
        # 标准化参数
        params = self._normalize_params(params)
        
        prompt = params.get("prompt", "")
        urls = params.get("urls", [])
        extracted_urls = self._extract_urls(prompt)
        all_urls = list(set(urls + extracted_urls))
        
        # 检查是否有内网地址
        for url in all_urls:
            if self._is_private_url(url):
                return {
                    "title": self._('web_fetch_confirm_private', default="访问内网地址需要确认"),
                    "url": url,
                    "risk": self._('web_fetch_risk_private', default="访问内部网络资源")
                }
        
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行网页内容获取"""
        # 标准化参数，确保 protobuf 对象被正确转换
        params = self._normalize_params(params)
        
        prompt = params.get("prompt", "")
        urls = params.get("urls", [])
        extract_text = params.get("extract_text", True)
        selector = params.get("selector", None)
        
        # 提取所有 URLs
        extracted_urls = self._extract_urls(prompt)
        all_urls = list(set(urls + extracted_urls))[:self.MAX_URLS]
        
        if not all_urls:
            return ToolResult(
                error=self._('web_fetch_no_urls_error', default="No URLs found to fetch")
            )
        
        results = []
        errors = []
        
        # 获取每个 URL 的内容
        for i, url in enumerate(all_urls):
            if update_output:
                update_output(self._('web_fetch_progress', default="🌐 获取网页 {current}/{total}: {url}", current=i+1, total=len(all_urls), url=url))
            
            try:
                content = await self._fetch_url(url, extract_text, selector)
                results.append({
                    "url": url,
                    "content": content,
                    "success": True
                })
            except Exception as e:
                # 增强错误信息诊断，提供异常类型和上下文
                error_msg = self._format_error_message(e, url)
                results.append({
                    "url": url,
                    "error": error_msg,
                    "success": False
                })
                errors.append(f"{url}: {error_msg}")
        
        # 格式化结果
        if not results:
            return ToolResult(
                error=self._('web_fetch_all_failed', default="Failed to fetch any content")
            )
        
        # 构建响应
        llm_content = self._format_results_for_llm(results, prompt)
        display_content = self._format_results_for_display(results)
        
        success_count = len([r for r in results if r['success']])
        summary = self._('web_fetch_summary', default="获取了 {count} 个网页的内容", count=success_count)
        if errors:
            summary += self._('web_fetch_summary_errors', default="，{count} 个失败", count=len(errors))
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display=display_content
        )
    
    def _extract_urls(self, text: str) -> List[str]:
        """从文本中提取 URLs"""
        # 改进的 URL 正则表达式
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        urls = re.findall(url_pattern, text)
        return list(set(urls))  # 去重
    
    def _is_private_url(self, url: str) -> bool:
        """检查是否为内网地址"""
        parsed = urlparse(url)
        host = parsed.hostname
        
        if not host:
            return False
            
        # 本地地址
        if host in ['localhost', '127.0.0.1', '::1']:
            return True
            
        # 私有 IP 范围
        private_patterns = [
            r'^10\.',
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',
            r'^192\.168\.'
        ]
        
        for pattern in private_patterns:
            if re.match(pattern, host):
                return True
                
        return False
    
    async def _fetch_url(self, url: str, extract_text: bool = True, selector: Optional[str] = None) -> str:
        """获取单个 URL 的内容，支持轻量重试机制"""
        
        # Web请求专用的轻量重试配置
        retry_options = RetryOptions(
            max_attempts=2,        # 总共2次尝试（1次重试）
            initial_delay_ms=1000, # 1秒初始延迟
            max_delay_ms=3000      # 最大3秒延迟
        )
        
        async def fetch_with_session():
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                }
                
                timeout = aiohttp.ClientTimeout(total=self.URL_FETCH_TIMEOUT)
                
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    # 检查内容长度
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
                        raise Exception(f"Content too large: {content_length} bytes")
                    
                    # 读取内容
                    content = await response.text()
                    
                    # 限制内容长度
                    if len(content) > self.MAX_CONTENT_LENGTH:
                        content = content[:self.MAX_CONTENT_LENGTH]
                    
                    # 处理内容
                    if extract_text and response.content_type and 'html' in response.content_type:
                        content = self._html_to_text(content, selector)
                    
                    return content
        
        # 使用重试机制执行请求
        return await retry_with_backoff(fetch_with_session, retry_options)
    
    def _html_to_text(self, html: str, selector: Optional[str] = None) -> str:
        """将 HTML 转换为纯文本"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 移除 script 和 style 标签
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 如果指定了选择器，只提取特定内容
        if selector:
            selected = soup.select(selector)
            if selected:
                text_parts = []
                for elem in selected:
                    text = elem.get_text(strip=True, separator=' ')
                    if text:
                        text_parts.append(text)
                return '\n\n'.join(text_parts)
        
        # 提取所有文本
        text = soup.get_text(strip=True, separator=' ')
        
        # 清理多余的空白
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        
        return '\n'.join(lines)
    
    def _format_error_message(self, exception: Exception, url: str) -> str:
        """
        格式化错误信息，提供更详细的诊断信息
        通用的错误增强方法，适用于各种异常类型
        """
        import aiohttp
        import asyncio
        from urllib.parse import urlparse
        
        exception_type = type(exception).__name__
        error_detail = str(exception).strip()
        
        # 构建基础错误信息
        if error_detail:
            base_msg = f"{exception_type}: {error_detail}"
        else:
            base_msg = f"{exception_type}: (no specific details)"
        
        # 根据异常类型添加上下文信息
        context_info = []
        
        # HTTP相关错误
        if isinstance(exception, aiohttp.ClientError):
            if isinstance(exception, aiohttp.ClientTimeout):
                context_info.append("connection/read timeout")
            elif isinstance(exception, aiohttp.ClientConnectorError):
                context_info.append("connection failed")
            elif isinstance(exception, aiohttp.ClientSSLError):
                context_info.append("SSL/TLS certificate issue")
            elif isinstance(exception, aiohttp.ClientResponseError):
                context_info.append(f"HTTP {getattr(exception, 'status', 'unknown')}")
        
        # 网络相关错误
        elif isinstance(exception, (OSError, ConnectionError)):
            context_info.append("network connectivity issue")
        
        # 超时相关错误
        elif isinstance(exception, (asyncio.TimeoutError, TimeoutError)):
            context_info.append(f"timeout after {self.URL_FETCH_TIMEOUT}s")
        
        # 解析URL获得通用上下文信息
        try:
            parsed_url = urlparse(url)
            if parsed_url.scheme == 'https':
                context_info.append("HTTPS site")
        except:
            pass  # URL解析失败时忽略
        
        # 组合最终消息
        if context_info:
            return f"{base_msg} ({', '.join(context_info)})"
        else:
            return base_msg
    
    def _format_results_for_llm(self, results: List[Dict], prompt: str) -> str:
        """格式化结果供 LLM 使用"""
        content_parts = [f"Web fetch results for prompt: '{prompt}'\n"]
        
        for i, result in enumerate(results, 1):
            url = result['url']
            
            if result['success']:
                content = result['content']
                # 限制每个内容的长度
                if len(content) > 5000:
                    content = content[:5000] + self._('web_fetch_content_truncated', default="\n... [内容已截断]")
                
                content_parts.append(f"\n=== Result {i}: {url} ===\n{content}")
            else:
                content_parts.append(f"\n=== Result {i}: {url} ===\nError: {result['error']}")
        
        # 添加处理提示
        content_parts.append(f"\n\nBased on the fetched content, here's the analysis according to the prompt:")
        
        return '\n'.join(content_parts)
    
    def _format_results_for_display(self, results: List[Dict]) -> str:
        """格式化结果供显示"""
        lines = [self._('web_fetch_results_header', default="🌐 网页内容获取结果:\n")]
        
        success_count = len([r for r in results if r['success']])
        fail_count = len(results) - success_count
        
        if success_count > 0:
            lines.append(self._('web_fetch_success_count', default="✅ 成功获取: {count} 个网页", count=success_count))
        if fail_count > 0:
            lines.append(self._('web_fetch_fail_count', default="❌ 获取失败: {count} 个网页", count=fail_count))
        
        lines.append("")
        
        for i, result in enumerate(results, 1):
            url = result['url']
            if result['success']:
                content_preview = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
                lines.append(f"{i}. ✅ {url}")
                lines.append(self._('web_fetch_preview', default="   预览: {content}\n", content=content_preview))
            else:
                lines.append(f"{i}. ❌ {url}")
                lines.append(self._('web_fetch_error_line', default="   错误: {error}\n", error=result['error']))
        
        return '\n'.join(lines)
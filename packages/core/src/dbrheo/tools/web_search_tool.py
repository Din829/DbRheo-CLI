"""
网络搜索工具 - 让Agent能够获取最新信息
"""

import aiohttp
from typing import Dict, Any, Optional, List, Protocol
from abc import ABC, abstractmethod
import json
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class SearchResult:
    """搜索结果的通用格式"""
    def __init__(self, title: str, url: str, snippet: str, **kwargs):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.metadata = kwargs  # 额外的元数据，保持灵活性


class SearchBackend(ABC):
    """搜索后端的抽象接口 - 支持未来扩展到不同的搜索引擎或AI模型"""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        """执行搜索并返回结果"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取后端名称"""
        pass


class DuckDuckGoBackend(SearchBackend):
    """DuckDuckGo搜索后端 - 无需API密钥"""
    
    def get_name(self) -> str:
        return "DuckDuckGo"
    
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        """使用DuckDuckGo进行搜索"""
        import re
        from urllib.parse import quote
        
        # DuckDuckGo HTML搜索
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Search request failed with status {response.status}")
                    
                    html = await response.text()
                    
                    # 调试：保存HTML到文件以便分析
                    import os
                    if os.getenv('DBRHEO_DEBUG_SEARCH', '').lower() == 'true':
                        with open('search_debug.html', 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"[DEBUG] HTML saved to search_debug.html, length: {len(html)}")
                    
                    # 改进的HTML解析 - 更灵活的正则表达式
                    results = []
                    
                    # 尝试多种模式匹配结果
                    patterns = [
                        # 标准结果模式
                        r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                        # 备用模式1
                        r'<h2 class="result__title">.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                        # 备用模式2 - 更宽松
                        r'<a[^>]*class="[^"]*result[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.DOTALL)
                        if matches:
                            for match in matches[:max_results]:
                                if len(match) >= 3:
                                    url, title, snippet = match[0], match[1], match[2]
                                elif len(match) == 2:
                                    url, title = match[0], match[1]
                                    snippet = "No description available"
                                else:
                                    continue
                                    
                                # 清理HTML标签
                                title = re.sub(r'<[^>]+>', '', title).strip()
                                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                                
                                if title and url:  # 确保有标题和URL
                                    results.append(SearchResult(
                                        title=title,
                                        url=url,
                                        snippet=snippet,
                                        source="duckduckgo"
                                    ))
                            
                            if results:  # 如果找到结果，停止尝试其他模式
                                break
                    
                    # 调试：打印找到的结果数量
                    if os.getenv('DBRHEO_DEBUG_SEARCH', '').lower() == 'true':
                        print(f"[DEBUG] Found {len(results)} results")
                        for i, r in enumerate(results[:2]):  # 只打印前2个
                            print(f"[DEBUG] Result {i}: {r.title} - {r.url[:50]}...")
                    
                    return results
                    
        except Exception as e:
            # 返回空结果而不是抛出异常，保持健壮性
            print(f"DuckDuckGo search error: {str(e)}")
            return []


class BingSearchBackend(SearchBackend):
    """Bing搜索后端 - 需要API密钥（预留接口）"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_name(self) -> str:
        return "Bing"
    
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        """使用Bing API进行搜索"""
        # 预留接口，未来实现
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
        }
        params = {
            'q': query,
            'count': max_results
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        for item in data.get('webPages', {}).get('value', []):
                            results.append(SearchResult(
                                title=item.get('name', ''),
                                url=item.get('url', ''),
                                snippet=item.get('snippet', ''),
                                source="bing"
                            ))
                        return results
                    else:
                        return []
        except Exception:
            return []


class WebSearchTool(DatabaseTool):
    """
    网络搜索工具，让Agent能够获取实时信息
    支持多种搜索引擎后端
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        super().__init__(
            name="web_search",
            display_name=self._('web_search_tool_name', default="网络搜索") if i18n else "网络搜索",
            description="Searches the web with automatic query refinement and content fetching capabilities. Provides comprehensive search results from multiple sources with intelligent result filtering and summarization.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["query"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 灵活的后端配置系统
        self.backend = self._initialize_backend()
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        query = params.get("query", "")
        if not query:
            return self._('web_search_query_empty', default="Search query cannot be empty")
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        # 确保 max_results 是整数
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 5
        return self._('web_search_description', default="Search web for: {query}... (max {max_results} results)", query=query[:50], max_results=max_results)
    
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Optional[Any]:
        """网络搜索通常不需要确认"""
        return False
        
    def _initialize_backend(self) -> SearchBackend:
        """初始化搜索后端 - 支持灵活配置"""
        backend_type = self.config.get("search_backend", "duckduckgo")
        
        if backend_type == "duckduckgo":
            return DuckDuckGoBackend()
        elif backend_type == "bing":
            api_key = self.config.get("bing_api_key")
            if not api_key:
                # 如果没有配置Bing API密钥，回退到DuckDuckGo
                return DuckDuckGoBackend()
            return BingSearchBackend(api_key)
        else:
            # 默认使用DuckDuckGo
            return DuckDuckGoBackend()
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行网络搜索 - 使用配置的后端"""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        # 确保 max_results 是整数
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 5
        
        try:
            # 流式反馈 - 显示使用的搜索引擎
            if update_output:
                update_output(self._('web_search_searching', default="🔍 Searching with {backend}: {query}...", backend=self.backend.get_name(), query=query))
            
            # 使用抽象后端进行搜索
            results = await self.backend.search(query, max_results)
            
            if not results:
                # 如果主后端失败，尝试备用后端
                if hasattr(self, '_fallback_backend'):
                    if update_output:
                        update_output(self._('web_search_fallback', default="🔄 Trying fallback search..."))
                    results = await self._fallback_backend.search(query, max_results)
                
                if not results:
                    return ToolResult(
                        summary=self._('web_search_no_results', default="No results found"),
                        llm_content=self._('web_search_no_results_llm', default="No search results found for '{query}' using {backend}", query=query, backend=self.backend.get_name()),
                        return_display=self._('web_search_no_results_display', default="No results found")
                    )
            
            # 格式化结果 - 使用通用的SearchResult对象
            llm_content = self._format_results_for_llm(results, query)
            display_content = self._format_results_for_display(results)
            
            return ToolResult(
                summary=self._('web_search_found_results', default="Found {count} results for '{query}'", count=len(results), query=query),
                llm_content=llm_content,
                return_display=display_content
            )
            
        except Exception as e:
            # 更详细的错误信息
            error_msg = self._('web_search_failed', default="Search failed using {backend}: {error}", backend=self.backend.get_name(), error=str(e))
            return ToolResult(
                error=error_msg,
                llm_content=error_msg,
                return_display=self._('web_search_failed_display', default="Search failed")
            )
    
    def _set_fallback_backend(self, backend: SearchBackend):
        """设置备用搜索后端"""
        self._fallback_backend = backend
    
    def _format_results_for_llm(self, results: List[SearchResult], query: str) -> str:
        """格式化搜索结果供LLM使用 - 支持SearchResult对象"""
        content = self._('web_search_results_header', default="Web search results for '{query}':\n\n", query=query)
        
        for i, result in enumerate(results, 1):
            content += f"{i}. {result.title}\n"
            content += self._('web_search_result_url', default="   URL: {url}\n", url=result.url)
            content += self._('web_search_result_summary', default="   Summary: {summary}\n", summary=result.snippet)
            
            # 如果有额外的元数据，也包含进去
            if result.metadata:
                for key, value in result.metadata.items():
                    if key != 'source':  # source已经在backend名称中体现
                        content += f"   {key.capitalize()}: {value}\n"
            
            content += "\n"
            
        content += self._('web_search_results_footer', default="\nBased on these search results, I can provide relevant information about the query.")
        return content
    
    def _format_results_for_display(self, results: List[SearchResult]) -> str:
        """格式化搜索结果供用户显示 - 支持SearchResult对象"""
        if not results:
            return self._('web_search_no_results_text', default="No search results found.")
            
        lines = [self._('web_search_display_header', default="🔍 Search Results (via {backend}):\n", backend=self.backend.get_name())]
        
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. **{result.title}**")
            
            # 智能截断摘要
            snippet = result.snippet
            if len(snippet) > 150:
                snippet = snippet[:147] + "..."
            lines.append(f"   {snippet}")
            
            lines.append(f"   🔗 {result.url}\n")
            
        return "\n".join(lines)
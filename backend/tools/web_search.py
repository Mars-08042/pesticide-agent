"""
网页搜索工具 - 使用 Serper API (Google Search)
参考 deep_research_standalone/tool_search.py 实现
"""

import os
import json
import http.client
from typing import List, Union, Dict, Any


class WebSearchTool:
    """
    网页搜索工具 - 使用 Serper API 进行 Google 搜索
    """

    name = "web_search"
    description = "在互联网上搜索信息。输入搜索关键词，返回相关网页的标题、链接和摘要。"

    def __init__(self):
        self.api_key = os.getenv("SERPER_KEY_ID")
        if not self.api_key:
            print("[WebSearch] 警告: SERPER_KEY_ID 未配置，搜索功能将不可用")

    def _contains_chinese(self, text: str) -> bool:
        """检测文本是否包含中文"""
        return any('\u4E00' <= char <= '\u9FFF' for char in text)

    def _build_payload(self, query: str, max_results: int) -> str:
        """构建 Serper 请求体"""
        if self._contains_chinese(query):
            return json.dumps({
                "q": query,
                "location": "China",
                "gl": "cn",
                "hl": "zh-cn",
                "num": max_results,
            })
        return json.dumps({
            "q": query,
            "location": "United States",
            "gl": "us",
            "hl": "en",
            "num": max_results,
        })

    def search_raw(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """执行搜索并返回结构化结果"""
        if not self.api_key:
            return []

        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = self._build_payload(query, max_results)
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        # 重试机制
        for attempt in range(3):
            try:
                conn.request("POST", "/search", payload, headers)
                res = conn.getresponse()
                data = res.read()
                results = json.loads(data.decode("utf-8"))
                break
            except Exception as e:
                print(f"[WebSearch] 搜索失败 (尝试 {attempt + 1}): {e}")
                if attempt == 2:
                    return []
                continue

        organic_results = results.get("organic", [])
        structured_results: List[Dict[str, Any]] = []
        for idx, page in enumerate(organic_results, 1):
            structured_results.append({
                "rank": idx,
                "title": page.get("title", "无标题"),
                "link": page.get("link", ""),
                "snippet": page.get("snippet", ""),
                "date": page.get("date", ""),
                "source": page.get("source", ""),
            })
        return structured_results

    def search(self, query: str, max_results: int = 10) -> str:
        """
        执行搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            格式化的搜索结果
        """
        if not self.api_key:
            return "[WebSearch] 错误: 搜索服务未配置"

        results = self.search_raw(query, max_results=max_results)
        if not results:
            return f"未找到与 '{query}' 相关的结果。请尝试其他关键词。"

        web_snippets = []
        for item in results:
            entry = f"{item['rank']}. [{item['title']}]({item['link']})"
            if item.get("date"):
                entry += f"\n   发布日期: {item['date']}"
            if item.get("source"):
                entry += f"\n   来源: {item['source']}"
            if item.get("snippet"):
                entry += f"\n   摘要: {item['snippet']}"
            web_snippets.append(entry)

        header = f"搜索 '{query}' 找到 {len(web_snippets)} 个结果:\n\n"
        return header + "\n\n".join(web_snippets)

    def batch_search(self, queries: List[str]) -> str:
        """批量搜索"""
        results = []
        for query in queries:
            result = self.search(query)
            results.append(f"## 搜索: {query}\n\n{result}")

        return "\n\n" + "=" * 50 + "\n\n".join(results)

    def __call__(self, query: Union[str, List[str]]) -> str:
        """LangChain Tool 兼容接口"""
        if isinstance(query, list):
            return self.batch_search(query)
        return self.search(query)


def get_web_search_tool() -> WebSearchTool:
    """获取网页搜索工具实例"""
    return WebSearchTool()


if __name__ == "__main__":
    # 测试
    tool = get_web_search_tool()
    result = tool("农药安全使用规范 2024")
    print(result)

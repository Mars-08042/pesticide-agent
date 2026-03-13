"""
网页搜索工具。

支持：
- Serper 搜索
- Tavily 搜索
- Hybrid 模式（Tavily 优先，Serper 补召回）
"""

import json
import http.client
import logging
import time
from typing import List, Union, Dict, Any
from urllib.parse import urlparse

import requests

from infra.config import get_config

logger = logging.getLogger(__name__)


class WebSearchTool:
    name = "web_search"
    description = "在互联网上搜索信息。输入搜索关键词，返回相关网页的标题、链接和摘要。"

    def __init__(self):
        config = get_config()
        self.search_config = config.web_search
        self.serper_api_key = self._normalize_key("SERPER_KEY_ID")
        self.tavily_api_key = self.search_config.tavily_api_key.strip()
        logger.info(
            "[WebSearch] 初始化 provider=%s, max_results=%s, require_fulltext=%s, tavily_retries=%s, tavily_depth=%s",
            self.search_config.provider,
            self.search_config.max_results,
            self.search_config.require_fulltext,
            self.search_config.tavily_search_retries,
            self.search_config.tavily_search_depth,
        )
        if not self.serper_api_key and self.search_config.provider in {"serper", "hybrid"}:
            logger.warning("[WebSearch] SERPER_KEY_ID 未配置，Serper 搜索不可用")
        if not self._has_tavily_key() and self.search_config.provider in {"tavily", "hybrid"}:
            logger.warning("[WebSearch] TAVILY_API_KEY 未配置，Tavily 搜索不可用")

    def _normalize_key(self, env_name: str) -> str:
        import os

        value = os.getenv(env_name, "").strip()
        if not value or value.startswith("your_"):
            return ""
        return value

    def _has_tavily_key(self) -> bool:
        return bool(self.tavily_api_key and not self.tavily_api_key.startswith("your_"))

    def _contains_chinese(self, text: str) -> bool:
        return any("\u4E00" <= char <= "\u9FFF" for char in text)

    def _extract_domain(self, url: str) -> str:
        domain = urlparse(url).netloc.lower().strip()
        return domain[4:] if domain.startswith("www.") else domain

    def _matches_domain(self, domain: str, rule: str) -> bool:
        normalized_rule = rule.lower().strip()
        if not normalized_rule:
            return False
        return domain == normalized_rule or domain.endswith(f".{normalized_rule}")

    def _priority_rank(self, domain: str) -> int:
        for idx, rule in enumerate(self.search_config.priority_domains):
            if self._matches_domain(domain, rule):
                return idx
        return len(self.search_config.priority_domains) + 1

    def _is_trusted(self, domain: str) -> bool:
        return any(self._matches_domain(domain, rule) for rule in self.search_config.trusted_domains)

    def _preview_text(self, text: str, limit: int = 80) -> str:
        normalized = " ".join((text or "").split())
        return normalized if len(normalized) <= limit else normalized[:limit] + "..."

    def _summarize_results(self, results: List[Dict[str, Any]], limit: int = 3) -> str:
        if not results:
            return "无结果"
        preview: List[str] = []
        for item in results[:limit]:
            link = item.get("link", "")
            domain = item.get("domain", "")
            if not domain and link:
                domain = self._extract_domain(link)
            if not domain:
                domain = item.get("source", "") or "unknown"
            preview.append(
                f"{self._preview_text(item.get('title', '无标题'), 36)} | {domain} | {link or 'N/A'}"
            )
        if len(results) > limit:
            preview.append(f"... 共 {len(results)} 条")
        return " ; ".join(preview)

    def _normalize_results(self, results: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen_links = set()
        for index, item in enumerate(results, 1):
            link = item.get("link", "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            domain = self._extract_domain(link)
            deduped.append({
                **item,
                "source": item.get("source") or domain,
                "domain": domain,
                "_original_rank": index,
                "trusted": self._is_trusted(domain),
            })

        deduped.sort(
            key=lambda item: (
                self._priority_rank(item["domain"]),
                0 if item["trusted"] else 1,
                item["_original_rank"],
            )
        )

        normalized: List[Dict[str, Any]] = []
        for index, item in enumerate(deduped[:max_results], 1):
            normalized.append({
                "rank": index,
                "title": item.get("title", "无标题"),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("date", ""),
                "source": item.get("source", ""),
                "raw_content": item.get("raw_content", ""),
                "trusted": item.get("trusted", False),
            })
        return normalized

    def _build_serper_payload(self, query: str, max_results: int) -> str:
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

    def _search_with_serper(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        if not self.serper_api_key:
            logger.info("[WebSearch] 跳过 Serper: 未配置 SERPER_KEY_ID, query=%s", self._preview_text(query))
            return []

        query_preview = self._preview_text(query)
        logger.info("[WebSearch] Serper 开始搜索: query=%s, max_results=%s", query_preview, max_results)
        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = self._build_serper_payload(query, max_results)
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json",
        }

        for attempt in range(3):
            try:
                conn.request("POST", "/search", payload, headers)
                response = conn.getresponse()
                data = response.read()
                results = json.loads(data.decode("utf-8"))
                break
            except Exception as exc:
                logger.warning("[WebSearch] Serper 搜索失败 (尝试 %s/3): %s", attempt + 1, exc)
                if attempt == 2:
                    return []
        else:
            return []

        organic_results = results.get("organic", [])
        mapped: List[Dict[str, Any]] = []
        for page in organic_results:
            mapped.append({
                "title": page.get("title", "无标题"),
                "link": page.get("link", ""),
                "snippet": page.get("snippet", ""),
                "date": page.get("date", ""),
                "source": page.get("source", ""),
                "raw_content": "",
            })
        logger.info(
            "[WebSearch] Serper 命中 %s 条: query=%s, sources=%s",
            len(mapped),
            query_preview,
            self._summarize_results(mapped),
        )
        return mapped

    def _search_with_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        if not self._has_tavily_key():
            logger.info("[WebSearch] 跳过 Tavily: 未配置 TAVILY_API_KEY, query=%s", self._preview_text(query))
            return []

        query_preview = self._preview_text(query)
        payload: Dict[str, Any] = {
            "query": query,
            "topic": "general",
            "search_depth": self.search_config.tavily_search_depth,
            "max_results": max_results,
            "include_raw_content": True,
        }
        if self.search_config.include_domains:
            payload["include_domains"] = self.search_config.include_domains
        if self.search_config.exclude_domains:
            payload["exclude_domains"] = self.search_config.exclude_domains

        max_retries = max(1, self.search_config.tavily_search_retries)
        logger.info(
            "[WebSearch] Tavily 开始搜索: query=%s, max_results=%s, depth=%s, retries=%s",
            query_preview,
            max_results,
            self.search_config.tavily_search_depth,
            max_retries,
        )
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.tavily.com/search",
                    headers={
                        "Authorization": f"Bearer {self.tavily_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                break
            except Exception as exc:
                logger.warning("[WebSearch] Tavily 搜索失败 (尝试 %s/%s): %s", attempt + 1, max_retries, exc)
                if attempt == max_retries - 1:
                    return []
                time.sleep(0.5)
        else:
            return []

        mapped: List[Dict[str, Any]] = []
        for item in data.get("results", []):
            link = item.get("url") or item.get("link", "")
            mapped.append({
                "title": item.get("title", "无标题"),
                "link": link,
                "snippet": item.get("content", ""),
                "date": item.get("published_date", ""),
                "source": self._extract_domain(link) if link else "",
                "raw_content": item.get("raw_content", "") or item.get("content", ""),
            })
        logger.info(
            "[WebSearch] Tavily 命中 %s 条: query=%s, sources=%s",
            len(mapped),
            query_preview,
            self._summarize_results(mapped),
        )
        return mapped

    def search_raw(self, query: str, max_results: int = 0) -> List[Dict[str, Any]]:
        effective_max_results = max_results or self.search_config.max_results
        provider = self.search_config.provider
        query_preview = self._preview_text(query)
        logger.info(
            "[WebSearch] 开始联网搜索: provider=%s, query=%s, max_results=%s",
            provider,
            query_preview,
            effective_max_results,
        )

        if provider == "tavily":
            results = self._search_with_tavily(query, effective_max_results)
            if not results:
                logger.info("[WebSearch] Tavily 无可用结果，回退 Serper: query=%s", query_preview)
                results = self._search_with_serper(query, effective_max_results)
        elif provider == "hybrid":
            logger.info("[WebSearch] 使用 Hybrid 搜索: Tavily 优先，Serper 补召回, query=%s", query_preview)
            tavily_results = self._search_with_tavily(query, effective_max_results)
            serper_results: List[Dict[str, Any]] = []
            if len(tavily_results) < effective_max_results:
                logger.info(
                    "[WebSearch] Hybrid 进入 Serper 补召回: tavily_results=%s, expected=%s, query=%s",
                    len(tavily_results),
                    effective_max_results,
                    query_preview,
                )
                serper_results = self._search_with_serper(query, effective_max_results)
            results = tavily_results + serper_results
        else:
            results = self._search_with_serper(query, effective_max_results)

        normalized = self._normalize_results(results, effective_max_results)
        if normalized:
            logger.info(
                "[WebSearch] 最终采用 %s 条来源: provider=%s, query=%s, sources=%s",
                len(normalized),
                provider,
                query_preview,
                self._summarize_results(normalized),
            )
        else:
            logger.info("[WebSearch] 最终无可用来源: provider=%s, query=%s", provider, query_preview)
        return normalized

    def search(self, query: str, max_results: int = 0) -> str:
        effective_max_results = max_results or self.search_config.max_results
        results = self.search_raw(query, max_results=effective_max_results)
        if not results:
            return f"未找到与 '{query}' 相关的结果。请尝试其他关键词。"

        formatted_results = []
        for item in results:
            entry = f"{item['rank']}. [{item['title']}]({item['link']})"
            if item.get("date"):
                entry += f"\n   发布日期: {item['date']}"
            if item.get("source"):
                entry += f"\n   来源: {item['source']}"
            if item.get("snippet"):
                entry += f"\n   摘要: {item['snippet']}"
            if item.get("trusted"):
                entry += "\n   标记: trusted-domain"
            formatted_results.append(entry)

        header = f"搜索 '{query}' 找到 {len(formatted_results)} 个结果:\n\n"
        return header + "\n\n".join(formatted_results)

    def batch_search(self, queries: List[str]) -> str:
        results = []
        for query in queries:
            results.append(f"## 搜索: {query}\n\n{self.search(query)}")
        return "\n\n" + "=" * 50 + "\n\n".join(results)

    def __call__(self, query: Union[str, List[str]]) -> str:
        if isinstance(query, list):
            return self.batch_search(query)
        return self.search(query)


def get_web_search_tool() -> WebSearchTool:
    return WebSearchTool()


if __name__ == "__main__":
    tool = get_web_search_tool()
    print(tool("农药制剂 配方 稳定性"))
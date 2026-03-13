"""
网页正文抓取工具。

支持：
- Jina Reader
- Tavily Extract
- Hybrid 模式（Tavily 优先，Jina 回退）
"""

import logging
import time
from typing import List, Union, Optional, Dict, Any
from urllib.parse import urlparse

import requests

from infra.config import get_config

logger = logging.getLogger(__name__)


class ContentScraperTool:
    name = "scrape_webpage"
    description = "抓取网页的完整内容。输入网页 URL，返回网页的文本内容。"

    def __init__(self):
        config = get_config()
        self.scraper_config = config.web_scraper
        self.search_config = config.web_search
        self.timeout = self.scraper_config.timeout
        self.max_content_length = self.scraper_config.max_content_length
        logger.info(
            "[ContentScraper] 初始化 provider=%s, timeout=%ss, max_content_length=%s, tavily_depth=%s",
            self.scraper_config.provider,
            self.timeout,
            self.max_content_length,
            self.scraper_config.tavily_extract_depth,
        )

        if not self._has_jina_key() and self.scraper_config.provider in {"jina", "hybrid"}:
            logger.warning("[ContentScraper] JINA_API_KEYS 未配置，Jina 抓取不可用")
        if not self._has_tavily_key() and self.scraper_config.provider in {"tavily", "hybrid"}:
            logger.warning("[ContentScraper] TAVILY_API_KEY 未配置，Tavily Extract 不可用")

    def _has_jina_key(self) -> bool:
        key = self.scraper_config.jina_api_key.strip()
        return bool(key and not key.startswith("your_"))

    def _has_tavily_key(self) -> bool:
        key = self.scraper_config.tavily_api_key.strip()
        return bool(key and not key.startswith("your_"))

    def _truncate(self, content: str) -> str:
        if len(content) <= self.max_content_length:
            return content
        return content[:self.max_content_length] + f"\n\n[内容已截断，原始长度超过 {self.max_content_length} 字符]"

    def _describe_target(self, url: str) -> str:
        try:
            domain = urlparse(url).netloc.lower().strip()
        except Exception:
            domain = ""
        return domain or url

    def _scrape_with_jina(self, url: str, max_retries: int = 3) -> str:
        if not self._has_jina_key():
            logger.info("[ContentScraper] 跳过 Jina: 未配置 JINA_API_KEYS, target=%s", self._describe_target(url))
            return "[ContentScraper] 错误: Jina 抓取服务未配置"

        logger.info("[ContentScraper] Jina 开始抓取: target=%s", self._describe_target(url))
        headers = {"Authorization": f"Bearer {self.scraper_config.jina_api_key}"}
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"https://r.jina.ai/{url}",
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    logger.info(
                        "[ContentScraper] Jina 抓取成功: target=%s, content_length=%s",
                        self._describe_target(url),
                        len(response.text),
                    )
                    return self._truncate(response.text)
                logger.warning(
                    "[ContentScraper] Jina HTTP %s: target=%s, body=%s",
                    response.status_code,
                    self._describe_target(url),
                    response.text[:200],
                )
            except requests.Timeout:
                logger.warning(
                    "[ContentScraper] Jina 超时 (尝试 %s/%s): target=%s",
                    attempt + 1,
                    max_retries,
                    self._describe_target(url),
                )
            except Exception as exc:
                logger.warning(
                    "[ContentScraper] Jina 抓取失败 (尝试 %s/%s): target=%s, error=%s",
                    attempt + 1,
                    max_retries,
                    self._describe_target(url),
                    exc,
                )
            time.sleep(0.5)
        return f"[ContentScraper] 无法抓取网页: {url}"

    def _extract_tavily_content(self, item: Dict[str, Any]) -> str:
        return (
            item.get("raw_content", "")
            or item.get("content", "")
            or item.get("markdown", "")
            or item.get("text", "")
        )

    def _scrape_with_tavily(self, url: str) -> str:
        if not self._has_tavily_key():
            logger.info("[ContentScraper] 跳过 Tavily Extract: 未配置 TAVILY_API_KEY, target=%s", self._describe_target(url))
            return "[ContentScraper] 错误: Tavily Extract 未配置"

        logger.info(
            "[ContentScraper] Tavily Extract 开始抓取: target=%s, depth=%s",
            self._describe_target(url),
            self.scraper_config.tavily_extract_depth,
        )
        payload = {
            "urls": [url],
            "extract_depth": self.scraper_config.tavily_extract_depth,
            "format": "markdown",
        }

        try:
            response = requests.post(
                "https://api.tavily.com/extract",
                headers={
                    "Authorization": f"Bearer {self.scraper_config.tavily_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("[ContentScraper] Tavily Extract 失败: target=%s, error=%s", self._describe_target(url), exc)
            return f"[ContentScraper] Tavily Extract 失败: {exc}"

        results = data.get("results") or data.get("data") or []
        if not results:
            logger.info("[ContentScraper] Tavily Extract 无结果: target=%s", self._describe_target(url))
            return f"[ContentScraper] 无法抓取网页: {url}"

        content = self._extract_tavily_content(results[0])
        if not content:
            logger.info("[ContentScraper] Tavily Extract 无正文: target=%s", self._describe_target(url))
            return f"[ContentScraper] 无法抓取网页: {url}"
        logger.info(
            "[ContentScraper] Tavily Extract 成功: target=%s, content_length=%s",
            self._describe_target(url),
            len(content),
        )
        return self._truncate(content)

    def scrape(self, url: str, max_retries: int = 3) -> str:
        provider = self.scraper_config.provider
        logger.info("[ContentScraper] 开始正文抓取: provider=%s, target=%s", provider, self._describe_target(url))
        if provider == "tavily":
            content = self._scrape_with_tavily(url)
            if content.startswith("[ContentScraper]"):
                logger.info("[ContentScraper] Tavily 抓取失败，回退 Jina: target=%s", self._describe_target(url))
                return self._scrape_with_jina(url, max_retries=max_retries)
            return content
        if provider == "hybrid":
            content = self._scrape_with_tavily(url)
            if content.startswith("[ContentScraper]"):
                logger.info("[ContentScraper] Hybrid 抓取回退 Jina: target=%s", self._describe_target(url))
                return self._scrape_with_jina(url, max_retries=max_retries)
            return content
        return self._scrape_with_jina(url, max_retries=max_retries)

    def batch_scrape(self, urls: List[str], timeout_per_batch: int = 300) -> List[str]:
        results = []
        start_time = time.time()
        for url in urls:
            if time.time() - start_time > timeout_per_batch:
                results.append(f"[ContentScraper] 批次超时，跳过: {url}")
                continue
            results.append(self.scrape(url))
        return results

    def scrape_with_goal(self, url: str, goal: str) -> str:
        content = self.scrape(url)
        if content.startswith("[ContentScraper]"):
            return content
        return f"## 网页内容 ({url})\n\n**抓取目标**: {goal}\n\n{content}"

    def __call__(self, url: Union[str, List[str]], goal: Optional[str] = None) -> str:
        if isinstance(url, list):
            return "\n\n" + "=" * 50 + "\n\n".join(self.batch_scrape(url))
        if goal:
            return self.scrape_with_goal(url, goal)
        return self.scrape(url)


def get_content_scraper_tool() -> ContentScraperTool:
    return ContentScraperTool()


if __name__ == "__main__":
    tool = get_content_scraper_tool()
    print(tool("https://www.example.com")[:500])
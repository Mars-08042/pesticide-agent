"""
内容抓取工具 - 使用 Jina Reader API 抓取网页内容
参考 deep_research_standalone/tool_visit.py 实现
"""

import os
import json
import time
from typing import List, Union, Optional
import requests


class ContentScraperTool:
    """
    内容抓取工具 - 使用 Jina Reader API 获取网页内容
    """

    name = "scrape_webpage"
    description = "抓取网页的完整内容。输入网页 URL，返回网页的文本内容。"

    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEYS")
        self.timeout = int(os.getenv("VISIT_SERVER_TIMEOUT", "60"))
        self.max_content_length = int(os.getenv("WEBCONTENT_MAXLENGTH", "100000"))

        if not self.api_key:
            print("[ContentScraper] 警告: JINA_API_KEYS 未配置，抓取功能将不可用")

    def scrape(self, url: str, max_retries: int = 3) -> str:
        """
        抓取单个网页

        Args:
            url: 网页 URL
            max_retries: 最大重试次数

        Returns:
            网页内容 (Markdown 格式)
        """
        if not self.api_key:
            return "[ContentScraper] 错误: 抓取服务未配置"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"https://r.jina.ai/{url}",
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    content = response.text

                    # 截断过长内容
                    if len(content) > self.max_content_length:
                        content = content[:self.max_content_length]
                        content += f"\n\n[内容已截断，原始长度超过 {self.max_content_length} 字符]"

                    return content
                else:
                    print(f"[ContentScraper] HTTP {response.status_code}: {response.text[:200]}")

            except requests.Timeout:
                print(f"[ContentScraper] 超时 (尝试 {attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"[ContentScraper] 错误 (尝试 {attempt + 1}/{max_retries}): {e}")

            time.sleep(0.5)

        return f"[ContentScraper] 无法抓取网页: {url}"

    def batch_scrape(self, urls: List[str], timeout_per_batch: int = 300) -> List[str]:
        """
        批量抓取网页

        Args:
            urls: URL 列表
            timeout_per_batch: 批次超时时间

        Returns:
            内容列表
        """
        results = []
        start_time = time.time()

        for url in urls:
            # 检查超时
            if time.time() - start_time > timeout_per_batch:
                results.append(f"[ContentScraper] 批次超时，跳过: {url}")
                continue

            content = self.scrape(url)
            results.append(content)

        return results

    def scrape_with_goal(self, url: str, goal: str) -> str:
        """
        抓取网页并根据目标提取关键信息
        注意: 此功能需要配合 LLM 进行摘要，暂时返回原始内容

        Args:
            url: 网页 URL
            goal: 抓取目标/问题

        Returns:
            相关内容
        """
        content = self.scrape(url)

        if content.startswith("[ContentScraper]"):
            return content

        # 返回带有目标信息的内容
        return f"## 网页内容 ({url})\n\n**抓取目标**: {goal}\n\n{content}"

    def __call__(self, url: Union[str, List[str]], goal: Optional[str] = None) -> str:
        """LangChain Tool 兼容接口"""
        if isinstance(url, list):
            results = self.batch_scrape(url)
            return "\n\n" + "=" * 50 + "\n\n".join(results)

        if goal:
            return self.scrape_with_goal(url, goal)

        return self.scrape(url)


def get_content_scraper_tool() -> ContentScraperTool:
    """获取内容抓取工具实例"""
    return ContentScraperTool()


if __name__ == "__main__":
    # 测试
    tool = get_content_scraper_tool()
    result = tool("https://www.example.com")
    print(result[:500])

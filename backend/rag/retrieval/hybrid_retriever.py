"""
混合检索器

实现向量检索 + 元数据过滤 + Rerank 重排序的混合检索方案，
为 Agent 提供高质量的配方参考资料。

检索流程：
1. 向量检索（宽松召回）
2. 元数据过滤（精确筛选）
3. Rerank 重排序（语义精排）
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from infra.llm import get_embedding_client, get_rerank_client
from infra.config import get_config
from rag.retrieval.vector_store import RecipeVectorStore, ChunkRecord

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    chunk: ChunkRecord
    score: float  # 最终得分（rerank 后）
    retrieval_score: float  # 向量检索得分


class HybridRetriever:
    """
    混合检索器

    结合向量检索、元数据过滤和 Rerank 重排序，
    提供高精度的配方知识检索。
    """

    def __init__(
        self,
        vector_store: Optional[RecipeVectorStore] = None,
    ):
        """
        初始化混合检索器

        Args:
            vector_store: 向量存储实例
        """
        self.vector_store = vector_store or RecipeVectorStore()
        self.embedding_client = get_embedding_client()
        self.rerank_client = get_rerank_client()
        self.config = get_config()

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_rerank: bool = True,
    ) -> List[RetrievalResult]:
        """
        混合检索

        Args:
            query: 查询文本
            top_k: 最终返回数量（不传时从配置读取）
            filters: 元数据过滤条件
            use_rerank: 是否使用 Rerank 重排序

        Returns:
            检索结果列表
        """
        retrieval_config = self.config.recipe_kb.retrieval
        final_top_k = top_k if top_k is not None else retrieval_config.final_top_k

        # 1. 向量检索（宽松召回）
        vector_results = self.vector_store.search_by_query(
            query=query,
            top_n=retrieval_config.vector_top_n,
            similarity_threshold=retrieval_config.similarity_threshold,
            filters=filters,
        )

        if not vector_results:
            logger.info(f"向量检索无结果: {query[:50]}...")
            return []

        logger.info(f"向量检索召回 {len(vector_results)} 条结果")

        # 2. Rerank 重排序
        if use_rerank and len(vector_results) > 1:
            try:
                reranked = self._rerank(query, vector_results, final_top_k)
                return reranked
            except Exception as e:
                logger.warning(f"Rerank 失败，降级为向量检索结果: {e}")

        # 不使用 Rerank 或 Rerank 失败，直接返回向量检索结果
        return [
            RetrievalResult(
                chunk=chunk,
                score=chunk.similarity,
                retrieval_score=chunk.similarity,
            )
            for chunk in vector_results[:final_top_k]
        ]

    def _rerank(
        self,
        query: str,
        chunks: List[ChunkRecord],
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        使用 Rerank 模型重排序

        Args:
            query: 查询文本
            chunks: 待排序的分块列表
            top_k: 返回前 K 个

        Returns:
            重排序后的结果列表
        """
        # 准备文档列表
        documents = [chunk.content for chunk in chunks]

        # 调用 Rerank API
        rerank_results = self.rerank_client.rerank(
            query=query,
            documents=documents,
            top_k=top_k,
        )

        # 构建结果
        results = []
        for item in rerank_results:
            idx = item["index"]
            chunk = chunks[idx]
            results.append(RetrievalResult(
                chunk=chunk,
                score=item["score"],
                retrieval_score=chunk.similarity,
            ))

        logger.info(f"Rerank 完成，返回 {len(results)} 条结果")
        return results

    def search_with_intent(
        self,
        query: str,
        top_k: Optional[int] = None,
        intent: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """
        带意图提取的检索

        自动从查询中提取结构化意图，用于过滤

        Args:
            query: 查询文本
            top_k: 返回数量（不传时从配置读取）
            intent: 预提取的意图（如不提供则自动提取）

        Returns:
            检索结果列表
        """
        # 如果没有预提取的意图，尝试简单规则提取
        if intent is None:
            intent = self._extract_intent(query)

        # 构建过滤条件
        filters = {}
        if intent.get("formulation_type"):
            filters["formulation_type"] = intent["formulation_type"]
        if intent.get("active_ingredients"):
            filters["active_ingredients"] = intent["active_ingredients"]
        if intent.get("doc_type"):
            filters["doc_type"] = intent["doc_type"]

        return self.search(query, top_k=top_k, filters=filters if filters else None)

    def _extract_intent(self, query: str) -> Dict[str, Any]:
        """
        从查询中提取结构化意图（简单规则版）

        Args:
            query: 查询文本

        Returns:
            提取的意图
        """
        intent = {}

        # 剂型识别
        formulation_keywords = {
            "SC": ["SC", "悬浮剂", "水悬浮剂"],
            "EC": ["EC", "乳油"],
            "ME": ["ME", "微乳剂"],
            "EW": ["EW", "水乳剂"],
            "SE": ["SE", "悬乳剂"],
            "WP": ["WP", "可湿性粉剂"],
            "WG": ["WG", "水分散粒剂"],
            "FS": ["FS", "悬浮种衣剂"],
            "SL": ["SL", "水剂"],
            "OD": ["OD", "油悬浮剂"],
        }

        query_upper = query.upper()
        for code, keywords in formulation_keywords.items():
            for kw in keywords:
                if kw.upper() in query_upper or kw in query:
                    intent["formulation_type"] = code
                    break
            if intent.get("formulation_type"):
                break

        # 文档类型识别
        if any(kw in query for kw in ["实验", "测试", "试验", "优化"]):
            intent["doc_type"] = "experiment"
        elif any(kw in query for kw in ["配方", "设计", "生成"]):
            intent["doc_type"] = "recipe"

        return intent

    def get_context_for_agent(
        self,
        query: str,
        top_k: Optional[int] = None,
        max_length: int = 8000,
    ) -> str:
        """
        获取用于 Agent 的上下文文本

        将检索结果格式化为适合 Agent 使用的参考资料

        Args:
            query: 查询文本
            top_k: 检索数量（不传时从配置读取）
            max_length: 最大上下文长度

        Returns:
            格式化的上下文文本
        """
        results = self.search(query, top_k=top_k)

        if not results:
            return ""

        context_parts = []
        total_length = 0

        for i, result in enumerate(results, 1):
            chunk = result.chunk

            # 构建参考资料块
            ref_block = f"""
---
### 参考资料 {i}
**标题**: {chunk.title}
**章节**: {chunk.section}
**剂型**: {chunk.formulation_type}
**来源**: {chunk.source}
**相关度**: {result.score:.2f}

{chunk.content}
---
"""
            block_length = len(ref_block)

            if total_length + block_length > max_length:
                break

            context_parts.append(ref_block)
            total_length += block_length

        return "\n".join(context_parts)


def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索器实例"""
    return HybridRetriever()

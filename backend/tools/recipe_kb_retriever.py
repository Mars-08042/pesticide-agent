"""
配方知识库检索工具

给配方生成子图提供统一的检索接口：
- search_recipes：配方类参考
- search_experiments：实验/优化类参考
- search_adjuvants：助剂信息参考
- search_knowledge：通用知识参考

说明：
- 该模块主要用于“结构清晰化”的重构，避免依赖散落在 `agent` 内部。
- 具体检索策略当前基于 `rag.retrieval.hybrid_retriever.HybridRetriever` 做统一封装。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RetrieverItem:
    """检索结果条目（供子图使用的最小结构）"""

    file_id: str
    filename: str
    content: str
    score: float


class RecipeKBRetrieverTool:
    """
    配方知识库检索工具

    为子图提供稳定的接口，内部可随时替换为不同检索实现（DB / 向量库 / 文件检索等）。
    """

    name = "recipe_kb_retriever"
    description = "检索配方知识库（配方/实验/助剂/通用知识）并返回结构化参考内容。"

    def __init__(self):
        self._retriever = None

    def _get_retriever(self):
        if self._retriever is None:
            from rag.retrieval.hybrid_retriever import get_hybrid_retriever

            self._retriever = get_hybrid_retriever()
        return self._retriever

    def _to_items(self, results) -> List[RetrieverItem]:
        items: List[RetrieverItem] = []
        for r in results:
            chunk = r.chunk
            filename = chunk.file_path or chunk.title or chunk.doc_id
            items.append(
                RetrieverItem(
                    file_id=chunk.doc_id,
                    filename=filename,
                    content=chunk.content,
                    score=float(r.score),
                )
            )
        return items

    def _search(
        self,
        query: str,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrieverItem]:
        from infra.config import get_config

        retrieval_config = get_config().recipe_kb.retrieval
        final_limit = limit if limit is not None else retrieval_config.final_top_k
        retriever = self._get_retriever()
        results = retriever.search(query=query, top_k=final_limit, filters=filters or None)
        return self._to_items(results)

    def search_recipes(
        self,
        active_ingredients: Optional[List[str]] = None,
        formulation_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RetrieverItem]:
        query_parts = [*(active_ingredients or [])]
        if formulation_type:
            query_parts.append(formulation_type)
        query = " ".join([p for p in query_parts if p]) or "配方 设计"

        filters: Dict[str, Any] = {"doc_type": "recipe"}
        if formulation_type:
            filters["formulation_type"] = formulation_type
        if active_ingredients:
            filters["active_ingredients"] = active_ingredients

        return self._search(query=query, limit=limit, filters=filters)

    def search_experiments(
        self,
        active_ingredients: Optional[List[str]] = None,
        formulation_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RetrieverItem]:
        query_parts = [*(active_ingredients or [])]
        if formulation_type:
            query_parts.append(formulation_type)
        query = " ".join([p for p in query_parts if p]) or "实验 优化"

        filters: Dict[str, Any] = {"doc_type": "experiment"}
        if formulation_type:
            filters["formulation_type"] = formulation_type
        if active_ingredients:
            filters["active_ingredients"] = active_ingredients

        return self._search(query=query, limit=limit, filters=filters)

    def search_adjuvants(
        self,
        keywords: Optional[List[str]] = None,
        formulation_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RetrieverItem]:
        query_parts = [*(keywords or [])]
        if formulation_type:
            query_parts.append(formulation_type)
        query = " ".join([p for p in query_parts if p]) or "助剂 分散剂 润湿剂"

        filters: Dict[str, Any] = {"doc_type": "adjuvant"}
        if formulation_type:
            filters["formulation_type"] = formulation_type

        return self._search(query=query, limit=limit, filters=filters)

    def search_knowledge(
        self,
        keywords: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[RetrieverItem]:
        query = " ".join([p for p in (keywords or []) if p]) or "通用知识"
        return self._search(query=query, limit=limit, filters=None)


def get_recipe_kb_retriever_tool() -> RecipeKBRetrieverTool:
    """获取配方知识库检索工具实例"""

    return RecipeKBRetrieverTool()

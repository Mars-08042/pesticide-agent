"""
配方知识检索器

实现统一混合检索接口，整合：
- recipe_chunks 表的混合检索（向量 + 元数据过滤 + Rerank）
- pesticides 表的精确查询
- adjuvants 表的条件筛选
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field

from infra.database import DatabaseManager
from infra.llm import get_embedding_client, get_rerank_client
from infra.config import get_config
from rag.retrieval.vector_store import RecipeVectorStore, ChunkRecord

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果数据结构"""
    recipes: List[Dict[str, Any]] = field(default_factory=list)  # 相似配方
    experiments_success: List[Dict[str, Any]] = field(default_factory=list)  # 成功实验
    experiments_failed: List[Dict[str, Any]] = field(default_factory=list)  # 失败实验（用于避坑）
    pesticide_info: List[Dict[str, Any]] = field(default_factory=list)  # 原药信息
    adjuvants: List[Dict[str, Any]] = field(default_factory=list)  # 可用助剂


class RecipeKnowledgeRetriever:
    """
    配方知识检索器

    提供统一的检索接口，整合向量检索、元数据过滤和精确查询。
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        vector_store: Optional[RecipeVectorStore] = None,
    ):
        """
        初始化检索器

        Args:
            db_manager: 数据库管理器实例
            vector_store: 向量存储实例
        """
        self.db = db_manager or DatabaseManager()
        self.vector_store = vector_store or RecipeVectorStore(db_manager=self.db)
        self.embedding_client = get_embedding_client()
        self.rerank_client = get_rerank_client()
        self.config = get_config()

    def hybrid_search_chunks(
        self,
        query: str,
        doc_type: Literal["recipe", "experiment"],
        active_ingredients: Optional[List[str]] = None,
        formulation_type: Optional[str] = None,
        experiment_status: Optional[str] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量召回 → 元数据过滤 → Rerank 重排序

        Args:
            query: 查询文本
            doc_type: 文档类型 (recipe/experiment)
            active_ingredients: 有效成分列表（用于过滤）
            formulation_type: 剂型代码（用于过滤）
            experiment_status: 实验状态（仅 experiment 类型）
            top_k: 最终返回数量
            similarity_threshold: 向量相似度阈值

        Returns:
            检索结果列表
        """
        # 构建过滤条件
        filters = {"doc_type": doc_type}

        if formulation_type:
            filters["formulation_type"] = formulation_type
        if active_ingredients:
            filters["active_ingredients"] = active_ingredients
        if experiment_status:
            filters["experiment_status"] = experiment_status

        # 1. 向量检索（宽松召回）
        vector_results = self.vector_store.search_by_query(
            query=query,
            top_n=top_k * 2,  # 多召回一些用于 Rerank
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

        if not vector_results:
            logger.info(f"混合检索无结果: query={query[:50]}..., doc_type={doc_type}")
            return []

        logger.info(f"向量检索召回 {len(vector_results)} 条结果 (doc_type={doc_type})")

        # 2. Rerank 重排序
        if len(vector_results) > 1:
            try:
                documents = [chunk.content for chunk in vector_results]
                rerank_results = self.rerank_client.rerank(
                    query=query,
                    documents=documents,
                    top_k=top_k,
                )

                # 构建结果
                results = []
                for item in rerank_results:
                    idx = item["index"]
                    chunk = vector_results[idx]
                    results.append(self._chunk_to_dict(chunk, item["score"]))

                logger.info(f"Rerank 完成，返回 {len(results)} 条结果")
                return results

            except Exception as e:
                logger.warning(f"Rerank 失败，降级为向量检索结果: {e}")

        # 不使用 Rerank 或 Rerank 失败，直接返回向量检索结果
        return [self._chunk_to_dict(chunk, chunk.similarity) for chunk in vector_results[:top_k]]

    def _chunk_to_dict(self, chunk: ChunkRecord, score: float) -> Dict[str, Any]:
        """将 ChunkRecord 转换为字典"""
        return {
            "id": chunk.id,
            "doc_id": chunk.doc_id,
            "content": chunk.content,
            "title": chunk.title,
            "section": chunk.section,
            "formulation_type": chunk.formulation_type,
            "active_ingredients": chunk.active_ingredients,
            "source": chunk.source,
            "summary": chunk.summary,
            "key_adjuvants": chunk.key_adjuvants,
            "experiment_status": chunk.experiment_status,
            "issues_found": chunk.issues_found,
            "optimization_notes": chunk.optimization_notes,
            "score": score,
        }

    def get_pesticide_info(self, active_ingredients: List[str]) -> List[Dict[str, Any]]:
        """
        从 pesticides 表精确查询原药信息

        Args:
            active_ingredients: 有效成分名称列表

        Returns:
            原药信息列表
        """
        results = []
        for ingredient in active_ingredients:
            info = self.db.get_pesticide_by_name(ingredient)
            if info:
                results.append({
                    "name_cn": info.get("name_cn", ""),
                    "name_en": info.get("name_en", ""),
                    "chemical_class": info.get("chemical_class", ""),
                    "cas_number": info.get("cas_number", ""),
                    "physicochemical": info.get("physicochemical", ""),
                    "bioactivity": info.get("bioactivity", ""),
                    "toxicology": info.get("toxicology", ""),
                })
            else:
                logger.info(f"未找到原药信息: {ingredient}")

        return results

    def search_adjuvants(
        self,
        formulation_type: Optional[str] = None,
        functions: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        从 adjuvants 表按剂型和功能筛选助剂

        Args:
            formulation_type: 剂型代码
            functions: 功能列表（如分散剂、润湿剂等）
            limit: 返回数量限制

        Returns:
            助剂信息列表
        """
        all_adjuvants = []

        if functions:
            # 按功能逐个查询
            for func in functions:
                adjuvants, _ = self.db.search_adjuvants(
                    formulation_type=formulation_type,
                    function=func,
                    page_size=limit // len(functions) + 1,
                )
                all_adjuvants.extend(adjuvants)
        else:
            # 仅按剂型查询
            adjuvants, _ = self.db.search_adjuvants(
                formulation_type=formulation_type,
                page_size=limit,
            )
            all_adjuvants = adjuvants

        # 去重（按 product_name）
        seen = set()
        unique_adjuvants = []
        for adj in all_adjuvants:
            key = adj.get("product_name", "")
            if key not in seen:
                seen.add(key)
                unique_adjuvants.append(adj)

        return unique_adjuvants[:limit]

    def retrieve_for_generation(
        self,
        active_ingredients: List[str],
        formulation_type: Optional[str] = None,
        concentration: Optional[str] = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        配方生成模式：获取所有相关知识

        Args:
            active_ingredients: 有效成分列表
            formulation_type: 剂型代码
            concentration: 浓度
            top_k: 每类检索的数量

        Returns:
            RetrievalResult 检索结果
        """
        # 构建查询字符串
        query_parts = active_ingredients.copy()
        if formulation_type:
            query_parts.append(formulation_type)
        if concentration:
            query_parts.append(concentration)
        query = " ".join(query_parts) + " 配方"

        # 1. 检索相似配方
        recipes = self.hybrid_search_chunks(
            query=query,
            doc_type="recipe",
            active_ingredients=active_ingredients,
            formulation_type=formulation_type,
            top_k=top_k,
        )

        # 2. 检索成功实验
        experiments_success = self.hybrid_search_chunks(
            query=query,
            doc_type="experiment",
            active_ingredients=active_ingredients,
            formulation_type=formulation_type,
            experiment_status="success",
            top_k=3,
        )

        # 3. 检索失败实验（用于避坑）
        experiments_failed = self.hybrid_search_chunks(
            query=query,
            doc_type="experiment",
            active_ingredients=active_ingredients,
            formulation_type=formulation_type,
            experiment_status="failed",
            top_k=2,
        )

        # 4. 获取原药信息
        pesticide_info = self.get_pesticide_info(active_ingredients)

        # 5. 获取可用助剂
        default_functions = ["分散剂", "润湿剂", "增稠剂", "防冻剂"]
        adjuvants = self.search_adjuvants(
            formulation_type=formulation_type,
            functions=default_functions,
        )

        return RetrievalResult(
            recipes=recipes,
            experiments_success=experiments_success,
            experiments_failed=experiments_failed,
            pesticide_info=pesticide_info,
            adjuvants=adjuvants,
        )

    def retrieve_for_optimization(
        self,
        original_recipe: str,
        original_analysis: Dict[str, Any],
        optimization_targets: List[str],
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        配方优化模式：根据优化目标针对性检索

        Args:
            original_recipe: 原始配方文本
            original_analysis: 原配方分析结果
            optimization_targets: 优化目标列表
            top_k: 每类检索的数量

        Returns:
            RetrievalResult 检索结果
        """
        active_ingredients = original_analysis.get("active_ingredients", [])
        formulation_type = original_analysis.get("formulation_type")

        # 基础检索
        result = self.retrieve_for_generation(
            active_ingredients=active_ingredients,
            formulation_type=formulation_type,
            top_k=top_k,
        )

        # 根据优化目标补充检索
        if "cost" in optimization_targets:
            # 检索更多助剂替代方案
            more_adjuvants = self.search_adjuvants(
                formulation_type=formulation_type,
                functions=["分散剂"],  # 针对成本优化
            )
            # 合并并去重
            existing_names = {a.get("product_name") for a in result.adjuvants}
            for adj in more_adjuvants:
                if adj.get("product_name") not in existing_names:
                    result.adjuvants.append(adj)

        if "stability" in optimization_targets:
            # 检索稳定性相关实验
            stability_query = "稳定性 热储 冷储 检测"
            stability_experiments = self.hybrid_search_chunks(
                query=stability_query,
                doc_type="experiment",
                experiment_status="success",
                top_k=3,
            )
            # 合并结果
            existing_ids = {e.get("id") for e in result.experiments_success}
            for exp in stability_experiments:
                if exp.get("id") not in existing_ids:
                    result.experiments_success.append(exp)

        if "performance" in optimization_targets:
            # 检索性能相关配方
            performance_query = f"{' '.join(active_ingredients)} 高效 悬浮率 分散性"
            performance_recipes = self.hybrid_search_chunks(
                query=performance_query,
                doc_type="recipe",
                formulation_type=formulation_type,
                top_k=3,
            )
            # 合并结果
            existing_ids = {r.get("id") for r in result.recipes}
            for recipe in performance_recipes:
                if recipe.get("id") not in existing_ids:
                    result.recipes.append(recipe)

        return result

    def to_dict(self, result: RetrievalResult) -> Dict[str, Any]:
        """
        将 RetrievalResult 转换为字典格式

        Args:
            result: RetrievalResult 实例

        Returns:
            字典格式的检索结果
        """
        return {
            "recipes": result.recipes,
            "experiments": {
                "success": result.experiments_success,
                "failed": result.experiments_failed,
            },
            "pesticide_info": result.pesticide_info,
            "adjuvants": result.adjuvants,
        }


def get_recipe_knowledge_retriever() -> RecipeKnowledgeRetriever:
    """获取配方知识检索器实例"""
    return RecipeKnowledgeRetriever()

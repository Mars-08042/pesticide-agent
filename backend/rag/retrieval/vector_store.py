"""
配方知识库向量存储

基于 PostgreSQL + pgvector 实现向量存储和检索，
支持配方文档的增删改查和向量相似度搜索。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from infra.database import DatabaseManager
from infra.llm import get_embedding_client
from infra.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    """分块记录"""
    id: str
    doc_id: str
    chunk_index: int
    content: str
    doc_type: str
    title: str
    section: str
    formulation_type: str
    active_ingredients: List[str]
    active_content: str
    source: str
    file_path: str
    summary: str
    key_adjuvants: List[str]
    experiment_status: str
    issues_found: List[str]
    optimization_notes: str
    similarity: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRecord":
        return cls(
            id=str(data.get("id", "")),
            doc_id=data.get("doc_id", ""),
            chunk_index=data.get("chunk_index", 0),
            content=data.get("content", ""),
            doc_type=data.get("doc_type", ""),
            title=data.get("title", ""),
            section=data.get("section", ""),
            formulation_type=data.get("formulation_type", ""),
            active_ingredients=data.get("active_ingredients") or [],
            active_content=data.get("active_content", ""),
            source=data.get("source", ""),
            file_path=data.get("file_path", ""),
            summary=data.get("summary", ""),
            key_adjuvants=data.get("key_adjuvants") or [],
            experiment_status=data.get("experiment_status", ""),
            issues_found=data.get("issues_found") or [],
            optimization_notes=data.get("optimization_notes", ""),
            similarity=data.get("similarity", 0.0),
        )


class RecipeVectorStore:
    """
    配方知识库向量存储

    提供配方分块的 CRUD 操作和向量检索功能
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化向量存储

        Args:
            db_manager: 数据库管理器实例
        """
        self.db = db_manager or DatabaseManager()
        self.embedding_client = get_embedding_client()
        self.config = get_config()

    def insert_chunk(
        self,
        doc_id: str,
        chunk_index: int,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """
        插入单个分块

        Args:
            doc_id: 文档ID
            chunk_index: 分块索引
            content: 文本内容
            embedding: 向量
            metadata: 元数据

        Returns:
            插入记录的 ID
        """
        sql = """
        INSERT INTO recipe_chunks (
            doc_id, chunk_index, content, embedding,
            doc_type, title, section, formulation_type,
            active_ingredients, active_content, source, file_path, summary,
            key_adjuvants, experiment_status, issues_found, optimization_notes
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            doc_type = EXCLUDED.doc_type,
            title = EXCLUDED.title,
            section = EXCLUDED.section,
            formulation_type = EXCLUDED.formulation_type,
            active_ingredients = EXCLUDED.active_ingredients,
            active_content = EXCLUDED.active_content,
            source = EXCLUDED.source,
            file_path = EXCLUDED.file_path,
            summary = EXCLUDED.summary,
            key_adjuvants = EXCLUDED.key_adjuvants,
            experiment_status = EXCLUDED.experiment_status,
            issues_found = EXCLUDED.issues_found,
            optimization_notes = EXCLUDED.optimization_notes,
            updated_at = NOW()
        RETURNING id;
        """

        with self.db.get_cursor() as cursor:
            cursor.execute(sql, (
                doc_id,
                chunk_index,
                content,
                embedding,
                metadata.get("doc_type", ""),
                metadata.get("title", ""),
                metadata.get("section", ""),
                metadata.get("formulation_type", ""),
                metadata.get("active_ingredients", []),
                metadata.get("active_content", ""),
                metadata.get("source", ""),
                metadata.get("file_path", ""),
                metadata.get("summary", ""),
                metadata.get("key_adjuvants", []),
                metadata.get("experiment_status", ""),
                metadata.get("issues_found", []),
                metadata.get("optimization_notes", ""),
            ))
            result = cursor.fetchone()
            return str(result[0]) if result else ""

    def insert_chunks_batch(
        self,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """
        批量插入分块

        Args:
            chunks: 分块列表，每个分块包含:
                - doc_id, chunk_index, content, embedding, metadata

        Returns:
            插入的记录数
        """
        if not chunks:
            return 0

        sql = """
        INSERT INTO recipe_chunks (
            doc_id, chunk_index, content, embedding,
            doc_type, title, section, formulation_type,
            active_ingredients, active_content, source, file_path, summary,
            key_adjuvants, experiment_status, issues_found, optimization_notes
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            doc_type = EXCLUDED.doc_type,
            title = EXCLUDED.title,
            section = EXCLUDED.section,
            formulation_type = EXCLUDED.formulation_type,
            active_ingredients = EXCLUDED.active_ingredients,
            active_content = EXCLUDED.active_content,
            source = EXCLUDED.source,
            file_path = EXCLUDED.file_path,
            summary = EXCLUDED.summary,
            key_adjuvants = EXCLUDED.key_adjuvants,
            experiment_status = EXCLUDED.experiment_status,
            issues_found = EXCLUDED.issues_found,
            optimization_notes = EXCLUDED.optimization_notes,
            updated_at = NOW();
        """

        with self.db.get_cursor() as cursor:
            for chunk in chunks:
                metadata = chunk.get("metadata", {})
                cursor.execute(sql, (
                    chunk["doc_id"],
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk["embedding"],
                    metadata.get("doc_type", ""),
                    metadata.get("title", ""),
                    metadata.get("section", ""),
                    metadata.get("formulation_type", ""),
                    metadata.get("active_ingredients", []),
                    metadata.get("active_content", ""),
                    metadata.get("source", ""),
                    metadata.get("file_path", ""),
                    metadata.get("summary", ""),
                    metadata.get("key_adjuvants", []),
                    metadata.get("experiment_status", ""),
                    metadata.get("issues_found", []),
                    metadata.get("optimization_notes", ""),
                ))

        return len(chunks)

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        删除指定文档的所有分块

        Args:
            doc_id: 文档ID

        Returns:
            删除的记录数
        """
        sql = "DELETE FROM recipe_chunks WHERE doc_id = %s;"

        with self.db.get_cursor() as cursor:
            cursor.execute(sql, (doc_id,))
            return cursor.rowcount

    def delete_by_file_path(self, file_path: str) -> int:
        """
        删除指定文件路径的所有分块

        Args:
            file_path: 文件路径

        Returns:
            删除的记录数
        """
        sql = "DELETE FROM recipe_chunks WHERE file_path = %s;"

        with self.db.get_cursor() as cursor:
            cursor.execute(sql, (file_path,))
            return cursor.rowcount

    def vector_search(
        self,
        query_embedding: List[float],
        top_n: int = 20,
        similarity_threshold: float = 0.3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ChunkRecord]:
        """
        向量相似度搜索

        Args:
            query_embedding: 查询向量
            top_n: 返回前 N 个结果
            similarity_threshold: 最低相似度阈值
            filters: 元数据过滤条件

        Returns:
            匹配的分块列表
        """
        # 构建基础 SQL
        sql = """
        SELECT
            id, doc_id, chunk_index, content,
            doc_type, title, section, formulation_type,
            active_ingredients, active_content, source, file_path, summary,
            key_adjuvants, experiment_status, issues_found, optimization_notes,
            1 - (embedding <=> %s::vector) AS similarity
        FROM recipe_chunks
        WHERE 1 - (embedding <=> %s::vector) > %s
        """

        params = [query_embedding, query_embedding, similarity_threshold]

        # 添加过滤条件
        if filters:
            if filters.get("formulation_type"):
                sql += " AND formulation_type = %s"
                params.append(filters["formulation_type"])

            if filters.get("doc_type"):
                sql += " AND doc_type = %s"
                params.append(filters["doc_type"])

            if filters.get("source"):
                sql += " AND source = %s"
                params.append(filters["source"])

            if filters.get("active_ingredients"):
                # 数组包含查询
                sql += " AND active_ingredients && %s"
                params.append(filters["active_ingredients"])

            if filters.get("experiment_status"):
                sql += " AND experiment_status = %s"
                params.append(filters["experiment_status"])

        # 排序和限制
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
        params.extend([query_embedding, top_n])

        with self.db.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [ChunkRecord.from_dict(row) for row in rows]

    def search_by_query(
        self,
        query: str,
        top_n: int = 20,
        similarity_threshold: float = 0.3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ChunkRecord]:
        """
        文本查询搜索（自动生成向量）

        Args:
            query: 查询文本
            top_n: 返回前 N 个结果
            similarity_threshold: 最低相似度阈值
            filters: 元数据过滤条件

        Returns:
            匹配的分块列表
        """
        # 生成查询向量
        query_embedding = self.embedding_client.embed_query(query)

        return self.vector_search(
            query_embedding=query_embedding,
            top_n=top_n,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

    def get_by_doc_id(self, doc_id: str) -> List[ChunkRecord]:
        """
        获取指定文档的所有分块

        Args:
            doc_id: 文档ID

        Returns:
            分块列表
        """
        sql = """
        SELECT
            id, doc_id, chunk_index, content,
            doc_type, title, section, formulation_type,
            active_ingredients, active_content, source, file_path, summary,
            key_adjuvants, experiment_status, issues_found, optimization_notes,
            0.0 AS similarity
        FROM recipe_chunks
        WHERE doc_id = %s
        ORDER BY chunk_index;
        """

        with self.db.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(sql, (doc_id,))
            rows = cursor.fetchall()

        return [ChunkRecord.from_dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        with self.db.get_cursor(dict_cursor=True) as cursor:
            # 总记录数
            cursor.execute("SELECT COUNT(*) as total FROM recipe_chunks;")
            total = cursor.fetchone()["total"]

            # 按文档类型统计
            cursor.execute("""
                SELECT doc_type, COUNT(*) as count
                FROM recipe_chunks
                GROUP BY doc_type;
            """)
            by_type = {row["doc_type"]: row["count"] for row in cursor.fetchall()}

            # 按剂型统计
            cursor.execute("""
                SELECT formulation_type, COUNT(*) as count
                FROM recipe_chunks
                WHERE formulation_type IS NOT NULL AND formulation_type != ''
                GROUP BY formulation_type
                ORDER BY count DESC;
            """)
            by_formulation = {row["formulation_type"]: row["count"] for row in cursor.fetchall()}

            # 文档数量
            cursor.execute("SELECT COUNT(DISTINCT doc_id) as doc_count FROM recipe_chunks;")
            doc_count = cursor.fetchone()["doc_count"]

        return {
            "total_chunks": total,
            "doc_count": doc_count,
            "by_type": by_type,
            "by_formulation": by_formulation,
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        列出所有已索引的文档

        Returns:
            文档列表
        """
        sql = """
        SELECT DISTINCT ON (doc_id)
            doc_id, title, doc_type, formulation_type,
            source, file_path, COUNT(*) OVER (PARTITION BY doc_id) as chunk_count
        FROM recipe_chunks
        ORDER BY doc_id, chunk_index;
        """

        with self.db.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

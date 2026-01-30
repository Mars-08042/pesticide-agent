#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""recipe_chunks 表导入脚本

数据来源：
- knowledge_base/03-制剂配方/**/*.md
- knowledge_base/04-配方实验/**/*.md

处理流程：
1. MarkdownChunker 分块（按二级标题）
2. MetadataExtractor 调用 LLM 提取文档级元数据
3. Embedding 向量化
4. 写入 recipe_chunks（PostgreSQL + pgvector）
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

# 禁用 httpx 和其他模块的日志输出
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("rag.chunker.metadata_extractor").setLevel(logging.WARNING)

from infra.database import DatabaseManager
from infra.llm import get_embedding_client
from rag.chunker.markdown_chunker import MarkdownChunker, get_doc_type
from rag.chunker.metadata_extractor import MetadataExtractor, ExtractedMetadata


DEFAULT_RECIPE_DIR = BACKEND_DIR / "knowledge_base" / "03-制剂配方"
DEFAULT_EXPERIMENT_DIR = BACKEND_DIR / "knowledge_base" / "04-配方实验"


@dataclass
class ImportStats:
    """导入统计"""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_chunks: int = 0
    inserted_chunks: int = 0


def read_file(path: Path) -> str:
    """读取文件，自动检测编码"""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def remove_blank_lines(text: str) -> str:
    """移除文档中的空行（仅移除代码块之外的空行）。

    说明：
    - 空行指仅包含空白字符的行
    - fenced code block（```）内的空行保留，避免破坏代码/表格的语义
    """
    if not text:
        return ""

    out: List[str] = []
    in_fence = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue

        if not in_fence and stripped == "":
            continue

        out.append(line)

    return "\n".join(out).strip() + "\n"


def print_progress(current: int, total: int, filename: str, status: str = "处理中"):
    """打印进度条"""
    percent = (current / total) * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    # 截断文件名以保持输出整洁
    display_name = filename[:30] + "..." if len(filename) > 30 else filename
    print(f"\r[{bar}] {percent:5.1f}% ({current}/{total}) {status}: {display_name}", end="", flush=True)


async def import_recipe_chunks(
    recipe_dir: Path = DEFAULT_RECIPE_DIR,
    experiment_dir: Path = DEFAULT_EXPERIMENT_DIR,
    clear: bool = False,
    limit_files: Optional[int] = None,
    skip_metadata: bool = False,
    skip_embedding: bool = False,
    files_from: Optional[Path] = None,
) -> ImportStats:
    """
    将 03-制剂配方 / 04-配方实验 Markdown 导入 recipe_chunks

    Args:
        recipe_dir: 制剂配方目录
        experiment_dir: 配方实验目录
        clear: 导入前是否清空表
        limit_files: 限制处理文件数（调试用）
        skip_metadata: 跳过 LLM 元数据提取
        skip_embedding: 跳过 Embedding 向量化
        files_from: 从文件列表读取要处理的文件（增量导入）
    """
    stats = ImportStats()

    # 收集所有 Markdown 文件
    if files_from and files_from.exists():
        # 从文件列表读取（增量模式）
        all_files = []
        for line in files_from.read_text(encoding="utf-8").splitlines():
            # 跳过空行，提取路径（去除行号前缀）
            line = line.strip()
            if not line:
                continue
            # 处理类似 "1→knowledge_base/..." 的格式
            if "→" in line:
                line = line.split("→", 1)[1].strip()
            # 统一路径分隔符
            line = line.replace("\\", "/")
            file_path = BACKEND_DIR / line
            if file_path.exists() and file_path.suffix == ".md":
                all_files.append(file_path)
            else:
                print(f"[跳过] 文件不存在或非 .md: {line}")
        print(f"从 {files_from.name} 读取到 {len(all_files)} 个有效文件")
    else:
        recipe_files = sorted([p for p in recipe_dir.rglob("*.md") if p.is_file()]) if recipe_dir.exists() else []
        experiment_files = sorted([p for p in experiment_dir.rglob("*.md") if p.is_file()]) if experiment_dir.exists() else []
        all_files = recipe_files + experiment_files

    if limit_files is not None:
        all_files = all_files[:max(0, limit_files)]

    stats.total_files = len(all_files)

    if stats.total_files == 0:
        print("未找到任何 .md 文件")
        return stats

    print(f"找到 {stats.total_files} 个文件，开始处理...\n")

    # 初始化组件
    db = DatabaseManager()
    # 确保表结构已创建/已迁移（例如将可能超长的字段放宽为 TEXT）
    db.init_database()
    chunker = MarkdownChunker()
    extractor = MetadataExtractor() if not skip_metadata else None
    embedder = get_embedding_client() if not skip_embedding else None

    # 清空表
    if clear:
        with db.get_cursor() as cursor:
            cursor.execute("TRUNCATE TABLE recipe_chunks;")
        print("已清空 recipe_chunks 表\n")

    # 逐文件处理
    for idx, file_path in enumerate(all_files, 1):
        rel_path = str(file_path.relative_to(BACKEND_DIR)).replace("\\", "/")
        filename = file_path.name

        print_progress(idx, stats.total_files, filename, "处理中")

        try:
            # 1. 读取文件
            content = remove_blank_lines(read_file(file_path))
            doc_type = get_doc_type(str(file_path))

            # 2. 分块
            chunks = chunker.chunk_text(content, file_path=str(file_path))
            if not chunks:
                stats.processed_files += 1
                continue

            # 3. 元数据提取（可选）
            if extractor:
                extracted = await extractor.extract(
                    content=content,
                    file_path=str(file_path),
                    doc_type=doc_type,
                )
            else:
                extracted = ExtractedMetadata()

            # 4. Embedding 向量化（可选）
            if embedder:
                texts = [c.content for c in chunks]
                embeddings = embedder.embed(texts)
            else:
                embeddings = [None] * len(chunks)

            # 5. 写入数据库
            with db.get_cursor() as cursor:
                for chunk, emb in zip(chunks, embeddings):
                    cursor.execute(
                        """
                        INSERT INTO recipe_chunks (
                            doc_id, chunk_index, content, embedding,
                            doc_type, formulation_type, active_ingredients, key_adjuvants,
                            experiment_status, title, section, active_content,
                            source, file_path, summary, issues_found, optimization_notes
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            doc_type = EXCLUDED.doc_type,
                            formulation_type = EXCLUDED.formulation_type,
                            active_ingredients = EXCLUDED.active_ingredients,
                            key_adjuvants = EXCLUDED.key_adjuvants,
                            experiment_status = EXCLUDED.experiment_status,
                            title = EXCLUDED.title,
                            section = EXCLUDED.section,
                            active_content = EXCLUDED.active_content,
                            source = EXCLUDED.source,
                            file_path = EXCLUDED.file_path,
                            summary = EXCLUDED.summary,
                            issues_found = EXCLUDED.issues_found,
                            optimization_notes = EXCLUDED.optimization_notes
                        """,
                        (
                            chunk.doc_id,
                            chunk.chunk_index,
                            chunk.content,
                            emb,
                            doc_type,
                            extracted.formulation_type or "",
                            extracted.active_ingredients or [],
                            extracted.key_adjuvants or [],
                            extracted.experiment_status or "",
                            (chunk.doc_title or "").strip(),
                            (chunk.section or "").strip(),
                            extracted.active_content or "",
                            extracted.source or "",
                            rel_path,
                            extracted.summary or "",
                            extracted.issues_found or [],
                            extracted.optimization_notes or "",
                        ),
                    )
                    stats.inserted_chunks += 1

            stats.processed_files += 1
            stats.total_chunks += len(chunks)

        except Exception as e:
            stats.failed_files += 1
            print(f"\n[失败] {rel_path}: {e}")

    # 完成
    print_progress(stats.total_files, stats.total_files, "完成", "已完成")
    print()  # 换行

    return stats


def main():
    """主函数"""
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="导入配方/实验 Markdown 到 recipe_chunks（LLM 元数据 + Embedding + pgvector）"
    )
    parser.add_argument("--recipe-dir", type=str, default=str(DEFAULT_RECIPE_DIR), help="03-制剂配方 目录")
    parser.add_argument("--experiment-dir", type=str, default=str(DEFAULT_EXPERIMENT_DIR), help="04-配方实验 目录")
    parser.add_argument("--clear", action="store_true", help="导入前清空 recipe_chunks 表")
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 个文件（调试用）")
    parser.add_argument("--skip-metadata", action="store_true", help="跳过 LLM 元数据提取")
    parser.add_argument("--skip-embedding", action="store_true", help="跳过 Embedding 向量化")
    parser.add_argument("--files-from", type=str, default=None, help="从文件列表读取要处理的文件（增量导入，如 failed.txt）")
    args = parser.parse_args()

    stats = asyncio.run(
        import_recipe_chunks(
            recipe_dir=Path(args.recipe_dir),
            experiment_dir=Path(args.experiment_dir),
            clear=args.clear,
            limit_files=args.limit,
            skip_metadata=args.skip_metadata,
            skip_embedding=args.skip_embedding,
            files_from=Path(args.files_from) if args.files_from else None,
        )
    )

    print(f"\n{'='*50}")
    print(f"导入完成")
    print(f"{'='*50}")
    print(f"总文件:   {stats.total_files}")
    print(f"成功处理: {stats.processed_files}")
    print(f"失败:     {stats.failed_files}")
    print(f"总分块:   {stats.total_chunks}")
    print(f"入库:     {stats.inserted_chunks}")


if __name__ == "__main__":
    main()

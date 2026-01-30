#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""recipe_chunks 处理流程测试脚本

测试数据：knowledge_base/03-制剂配方/科莱恩/*.md
功能：验证分块、元数据提取、向量化流程，输出到控制台和 Markdown 文件
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from rag.chunker.markdown_chunker import MarkdownChunker, Chunk, get_doc_type
from rag.chunker.metadata_extractor import MetadataExtractor, ExtractedMetadata


# 测试目录
TEST_DIR = BACKEND_DIR / "knowledge_base" / "03-制剂配方" / "科莱恩"
# 输出文件
OUTPUT_DIR = DATA_IMPORT_DIR / "outputs"


class MarkdownWriter:
    """Markdown 格式输出器，同时写入控制台和文件"""

    def __init__(self, output_file: Optional[Path] = None):
        self.buffer = StringIO()
        self.output_file = output_file

    def write(self, text: str = ""):
        """写入一行"""
        print(text)
        self.buffer.write(text + "\n")

    def h1(self, text: str):
        self.write(f"\n# {text}\n")

    def h2(self, text: str):
        self.write(f"\n## {text}\n")

    def h3(self, text: str):
        self.write(f"\n### {text}\n")

    def h4(self, text: str):
        self.write(f"\n#### {text}\n")

    def text(self, text: str):
        self.write(text)

    def bullet(self, text: str, indent: int = 0):
        prefix = "  " * indent
        self.write(f"{prefix}- {text}")

    def quote(self, text: str):
        """引用块"""
        for line in text.split("\n"):
            self.write(f"> {line}")

    def table_header(self, columns: List[str]):
        self.write("| " + " | ".join(columns) + " |")
        self.write("| " + " | ".join(["---"] * len(columns)) + " |")

    def table_row(self, values: List[str]):
        # 转义表格中的竖线和换行
        escaped = [v.replace("|", "\\|").replace("\n", " ") for v in values]
        self.write("| " + " | ".join(escaped) + " |")

    def separator(self):
        self.write("\n---\n")

    def save(self):
        """保存到文件"""
        if self.output_file:
            self.output_file.write_text(self.buffer.getvalue(), encoding="utf-8")
            print(f"\n📄 测试报告已保存到: {self.output_file}")


def read_file(path: Path) -> str:
    """读取文件，自动检测编码"""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


async def test_chunking_only(files: List[Path], writer: MarkdownWriter):
    """仅测试分块，不调用 LLM"""
    writer.h2("分块测试（不调用 LLM）")

    chunker = MarkdownChunker()
    total_chunks = 0
    all_chunks_data = []

    for file_path in files:
        rel_path = file_path.relative_to(BACKEND_DIR)
        writer.h3(f"文件: {rel_path.name}")

        content = read_file(file_path)
        doc_type = get_doc_type(str(file_path))

        chunks = chunker.chunk_text(content, file_path=str(file_path))

        # 简洁的文件摘要
        writer.bullet(f"**路径**: `{rel_path}`")
        writer.bullet(f"**类型**: `{doc_type}` | **大小**: {len(content)} 字符 | **分块数**: {len(chunks)}")
        writer.text("")

        # 分块汇总表
        writer.table_header(["#", "章节", "词数", "字符数"])
        for i, chunk in enumerate(chunks):
            writer.table_row([
                str(i),
                chunk.section or "(无标题)",
                str(chunk.word_count),
                str(len(chunk.content)),
            ])

        writer.text("")

        # 每个分块的内容（直接用 Markdown 格式展示）
        writer.h4("分块内容详情")

        for i, chunk in enumerate(chunks):
            writer.text(f"\n**Chunk {i}** | 章节: `{chunk.section or '(空)'}` | doc_id: `{chunk.doc_id}`\n")

            # 直接输出内容，使用引用格式便于区分
            content_preview = chunk.content[:800]
            if len(chunk.content) > 800:
                content_preview += "\n\n... (内容已截断)"

            writer.quote(content_preview)
            writer.text("")

            all_chunks_data.append({
                "file": rel_path.name,
                "chunk_index": i,
                "section": chunk.section,
                "word_count": chunk.word_count,
            })

        total_chunks += len(chunks)
        writer.separator()

    # 汇总统计
    writer.h3("分块统计汇总")
    writer.table_header(["指标", "值"])
    writer.table_row(["总文件数", str(len(files))])
    writer.table_row(["总分块数", str(total_chunks)])
    writer.table_row(["平均每文件分块数", f"{total_chunks / len(files):.1f}"])
    writer.text("")

    # 所有分块列表
    writer.h4("所有分块一览")
    writer.table_header(["文件", "#", "章节", "词数"])
    for item in all_chunks_data:
        writer.table_row([
            item["file"],
            str(item["chunk_index"]),
            item["section"] or "(空)",
            str(item["word_count"]),
        ])


async def test_with_metadata(files: List[Path], writer: MarkdownWriter, limit: int = 1):
    """测试分块 + LLM 元数据提取"""
    writer.h2("分块 + 元数据提取测试")

    chunker = MarkdownChunker()
    extractor = MetadataExtractor()

    test_files = files[:limit]
    writer.text(f"测试文件数: {len(test_files)}（限制 {limit} 个）\n")

    for file_path in test_files:
        rel_path = file_path.relative_to(BACKEND_DIR)
        writer.h3(f"文件: {rel_path.name}")

        content = read_file(file_path)
        doc_type = get_doc_type(str(file_path))
        chunks = chunker.chunk_text(content, file_path=str(file_path))

        writer.bullet(f"**路径**: `{rel_path}`")
        writer.bullet(f"**类型**: `{doc_type}` | **分块数**: {len(chunks)}")
        writer.text("")

        # 元数据提取
        writer.h4("LLM 元数据提取结果")
        batch_items = [{
            "content": content,
            "file_path": str(file_path),
            "doc_type": doc_type,
        }]

        try:
            extracted_list = await extractor.extract_batch(batch_items)
            meta = extracted_list[0]

            writer.table_header(["字段", "值"])
            writer.table_row(["剂型 (formulation_type)", meta.formulation_type or "(空)"])
            writer.table_row(["有效成分", ", ".join(meta.active_ingredients) if meta.active_ingredients else "(空)"])
            writer.table_row(["含量", meta.active_content or "(空)"])
            writer.table_row(["来源", meta.source or "(空)"])
            writer.table_row(["关键助剂", ", ".join(meta.key_adjuvants) if meta.key_adjuvants else "(空)"])
            writer.table_row(["摘要", meta.summary or "(空)"])

            if doc_type == "experiment":
                writer.table_row(["实验状态", meta.experiment_status or "(空)"])
                writer.table_row(["发现问题", ", ".join(meta.issues_found) if meta.issues_found else "(空)"])
                writer.table_row(["优化建议", meta.optimization_notes or "(空)"])

        except Exception as e:
            writer.text(f"**提取失败**: {e}")

        writer.text("")

        # 分块预览
        writer.h4("分块预览（前 3 个）")
        for i, chunk in enumerate(chunks[:3]):
            writer.text(f"\n**Chunk {i}** | 章节: `{chunk.section or '(空)'}`\n")
            preview = chunk.content[:400]
            if len(chunk.content) > 400:
                preview += "\n... (已截断)"
            writer.quote(preview)
            writer.text("")

        if len(chunks) > 3:
            writer.text(f"*... 还有 {len(chunks) - 3} 个分块未显示*")

        writer.separator()


async def test_embedding(files: List[Path], writer: MarkdownWriter, limit: int = 1):
    """测试分块 + Embedding 向量化"""
    writer.h2("分块 + Embedding 测试")

    from infra.llm import get_embedding_client

    chunker = MarkdownChunker()
    embedder = get_embedding_client()

    test_files = files[:limit]
    writer.text(f"测试文件数: {len(test_files)}\n")

    for file_path in test_files:
        rel_path = file_path.relative_to(BACKEND_DIR)
        writer.h3(f"文件: {rel_path.name}")

        content = read_file(file_path)
        chunks = chunker.chunk_text(content, file_path=str(file_path))
        writer.bullet(f"**分块数**: {len(chunks)}")
        writer.text("")

        # 向量化
        writer.h4("Embedding 结果")
        try:
            texts = [c.content for c in chunks]
            embeddings = embedder.embed(texts)

            writer.table_header(["指标", "值"])
            writer.table_row(["向量数量", str(len(embeddings))])
            writer.table_row(["向量维度", str(len(embeddings[0]) if embeddings else 0)])
            writer.text("")

            # 向量预览
            writer.h4("向量预览（前 3 个）")
            writer.table_header(["Chunk", "前 5 维", "L2 范数"])
            for i, emb in enumerate(embeddings[:3]):
                preview = ", ".join([f"{v:.4f}" for v in emb[:5]])
                norm = sum(v * v for v in emb) ** 0.5
                writer.table_row([f"chunk_{i}", f"[{preview}, ...]", f"{norm:.4f}"])

        except Exception as e:
            writer.text(f"**Embedding 失败**: {e}")

        writer.separator()


async def main():
    parser = argparse.ArgumentParser(description="recipe_chunks 处理流程测试")
    parser.add_argument(
        "--mode",
        choices=["chunk", "metadata", "embedding", "all"],
        default="chunk",
        help="测试模式：chunk=仅分块, metadata=分块+元数据, embedding=分块+向量化, all=全部"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="测试文件数量限制（metadata/embedding 模式，默认 1）"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=str(TEST_DIR),
        help="测试目录路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件路径（默认自动生成）"
    )
    args = parser.parse_args()

    # 获取测试文件
    test_dir = Path(args.dir)
    if not test_dir.exists():
        print(f"错误: 目录不存在 - {test_dir}")
        sys.exit(1)

    files = sorted([p for p in test_dir.rglob("*.md") if p.is_file()])
    if not files:
        print(f"错误: 目录中没有 .md 文件 - {test_dir}")
        sys.exit(1)

    # 确定输出文件
    if args.output:
        output_file = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"test_result_{args.mode}_{timestamp}.md"

    # 创建输出器
    writer = MarkdownWriter(output_file)

    # 写入报告头
    writer.h1("recipe_chunks 处理流程测试报告")
    writer.text(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    writer.text(f"**测试模式**: `{args.mode}`")
    writer.text(f"**测试目录**: `{test_dir}`")
    writer.text(f"**文件数量**: {len(files)}")
    writer.text("")

    # 文件列表
    writer.h2("测试文件列表")
    writer.table_header(["序号", "文件名", "大小"])
    for i, f in enumerate(files):
        size = f.stat().st_size
        writer.table_row([str(i + 1), f.name, f"{size} 字节"])

    writer.separator()

    # 执行测试
    if args.mode in ("chunk", "all"):
        await test_chunking_only(files, writer)

    if args.mode in ("metadata", "all"):
        await test_with_metadata(files, writer, limit=args.limit)

    if args.mode in ("embedding", "all"):
        await test_embedding(files, writer, limit=args.limit)

    # 写入报告尾
    writer.separator()
    writer.h2("测试完成")
    writer.text(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 保存文件
    writer.save()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计配方实验目录下所有 Markdown 文档的平均字数
"""

import os
import re
from pathlib import Path


def count_words(text: str) -> int:
    """
    统计文本字数
    - 中文按字符计算
    - 英文按单词计算
    """
    # 移除 Markdown 语法标记
    text = re.sub(r'[#*`\[\]()>|_~-]', ' ', text)

    # 统计中文字符数
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_count = len(chinese_chars)

    # 统计英文单词数（包括数字）
    # 先移除中文字符
    text_without_chinese = re.sub(r'[\u4e00-\u9fff]', ' ', text)
    english_words = re.findall(r'[a-zA-Z0-9]+', text_without_chinese)
    english_count = len(english_words)

    return chinese_count + english_count


def main():
    # 获取脚本所在目录的父目录（项目根目录）
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # 配方实验目录路径
    target_dir = project_root / "knowledge_base" / "配方实验"

    if not target_dir.exists():
        print(f"错误: 目录不存在 - {target_dir}")
        return

    # 收集所有 md 文件的字数
    word_counts = []
    file_details = []

    for md_file in target_dir.rglob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            word_count = count_words(content)
            word_counts.append(word_count)
            file_details.append({
                'path': md_file.relative_to(target_dir),
                'count': word_count
            })
        except Exception as e:
            print(f"警告: 读取文件失败 - {md_file}: {e}")

    if not word_counts:
        print("未找到任何 Markdown 文件")
        return

    # 计算统计数据
    total_files = len(word_counts)
    total_words = sum(word_counts)
    avg_words = total_words / total_files
    max_words = max(word_counts)
    min_words = min(word_counts)

    # 输出结果
    print("=" * 60)
    print("配方实验 Markdown 文档字数统计")
    print("=" * 60)
    print(f"目录路径: {target_dir}")
    print(f"文件总数: {total_files} 个")
    print(f"总字数:   {total_words} 字")
    print(f"平均字数: {avg_words:.2f} 字")
    print(f"最大字数: {max_words} 字")
    print(f"最小字数: {min_words} 字")
    print("=" * 60)

    # 显示字数最多和最少的文件
    file_details.sort(key=lambda x: x['count'], reverse=True)

    print("\n字数最多的 5 个文件:")
    for i, detail in enumerate(file_details[:5], 1):
        print(f"  {i}. {detail['path']} ({detail['count']} 字)")

    print("\n字数最少的 5 个文件:")
    for i, detail in enumerate(file_details[-5:], 1):
        print(f"  {i}. {detail['path']} ({detail['count']} 字)")


if __name__ == "__main__":
    main()

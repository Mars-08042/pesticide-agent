#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""助剂信息导入数据来源：knowledge_base/02-助剂信息/adjuvants.sql（SQLite 导出的 INSERT 语句）目标表：adjuvants实现策略：- 优先解析 adjuvants.sql 中的 INSERT 语句并写入 PostgreSQL- 如解析失败，可回退从 adjuvants.db 读取（同目录下）"""

from __future__ import annotations

import re
import sys
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv



DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from infra.database import DatabaseManager


DEFAULT_SQL_PATH = BACKEND_DIR / "knowledge_base" / "02-助剂信息" / "adjuvants.sql"
DEFAULT_DB_PATH = BACKEND_DIR / "knowledge_base" / "02-助剂信息" / "adjuvants.db"


@dataclass
class ImportStats:
    total: int = 0
    inserted: int = 0
    failed: int = 0


def _split_sql_values(values_str: str) -> List[Optional[str]]:
    """将 VALUES(...) 中的值按逗号切分（忽略字符串内部逗号），并做基本的 NULL 处理。"""
    values: List[str] = []
    buf: List[str] = []
    in_quotes = False
    i = 0

    while i < len(values_str):
        ch = values_str[i]

        if in_quotes:
            if ch == "'":
                # 处理 SQL 转义：'' 表示单引号
                if i + 1 < len(values_str) and values_str[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        # 非引号状态
        if ch == "'":
            in_quotes = True
            i += 1
            continue
        if ch == ",":
            values.append("".join(buf).strip())
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    if buf:
        values.append("".join(buf).strip())

    normalized: List[Optional[str]] = []
    for v in values:
        if not v:
            normalized.append("")
            continue
        if v.upper() == "NULL":
            normalized.append(None)
            continue
        normalized.append(v)

    return normalized


def _parse_sql_inserts(sql_path: Path) -> List[Dict[str, Any]]:
    """解析 adjuvants.sql 中的 INSERT 语句。"""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {sql_path}")

    inserts: List[Dict[str, Any]] = []

    for line in sql_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or not line.upper().startswith("INSERT INTO"):
            continue

        # 仅处理 adjuvants 表
        if "adjuvants" not in line.lower():
            continue

        # 取 VALUES (...) 部分
        m = re.search(r"VALUES\s*\((.*)\);\s*$", line, re.IGNORECASE)
        if not m:
            continue

        raw_values = m.group(1)
        values = _split_sql_values(raw_values)
        if len(values) < 9:
            continue

        inserts.append({
            "formulation_type": values[1] or "",
            "product_name": values[2] or "",
            "function": values[3],
            "adjuvant_type": values[4],
            "appearance": values[5],
            "ph_range": values[6],
            "remarks": values[7],
            "company": values[8],
        })

    return inserts


def _read_from_sqlite(db_path: Path) -> List[Dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite 数据库不存在: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT formulation_type, product_name, function, adjuvant_type, appearance, ph_range, remarks, company FROM adjuvants")
        rows = cursor.fetchall()
        items = []
        for row in rows:
            items.append({
                "formulation_type": row[0] or "",
                "product_name": row[1] or "",
                "function": row[2],
                "adjuvant_type": row[3],
                "appearance": row[4],
                "ph_range": row[5],
                "remarks": row[6],
                "company": row[7],
            })
        return items
    finally:
        conn.close()


def import_adjuvants(clear: bool = False, sql_path: Optional[Path] = None) -> ImportStats:
    """导入助剂信息到 PostgreSQL。"""
    sql_path = sql_path or DEFAULT_SQL_PATH

    items = _parse_sql_inserts(sql_path)
    if not items:
        # 回退：从 sqlite 读取
        items = _read_from_sqlite(DEFAULT_DB_PATH)

    stats = ImportStats(total=len(items))

    db = DatabaseManager()
    db.init_database()

    if clear:
        db.clear_adjuvants()

    for item in items:
        try:
            if not item.get("formulation_type") or not item.get("product_name"):
                stats.failed += 1
                continue
            db.create_adjuvant(**item)
            stats.inserted += 1
        except Exception:
            stats.failed += 1

    return stats


if __name__ == "__main__":
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="导入助剂信息到 PostgreSQL")
    parser.add_argument("--clear", action="store_true", help="导入前清空 adjuvants 表")
    parser.add_argument("--sql", type=str, default=str(DEFAULT_SQL_PATH), help="adjuvants.sql 路径")
    args = parser.parse_args()

    s = import_adjuvants(clear=args.clear, sql_path=Path(args.sql))
    print(f"总记录: {s.total} | 插入: {s.inserted} | 失败: {s.failed}")

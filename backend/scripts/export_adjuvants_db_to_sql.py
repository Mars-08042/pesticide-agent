#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 adjuvants.db SQLite 数据库导出为 SQL 文件
包含表结构和数据
"""

# ============================================================
# 配置区域 - 可根据需要修改以下配置
# ============================================================

# 源数据库路径（相对于脚本所在目录的父目录，即 backend 目录）
SOURCE_DB = "knowledge_base/02-助剂信息/adjuvants.db"

# 输出 SQL 文件路径（相对于脚本所在目录的父目录，即 backend 目录）
# 设为 None 则输出到数据库同目录，文件名为 adjuvants.sql
OUTPUT_SQL = None

# 是否包含表结构（CREATE TABLE 语句）
INCLUDE_SCHEMA = True

# 是否包含数据（INSERT 语句）
INCLUDE_DATA = True

# 是否在 INSERT 前添加 DELETE 语句清空表
INCLUDE_DELETE = False

# 是否添加事务包装（BEGIN/COMMIT）
USE_TRANSACTION = True

# 文件编码
ENCODING = "utf-8"

# ============================================================
# 脚本逻辑 - 一般无需修改
# ============================================================

import sqlite3
from pathlib import Path


def get_table_names(cursor) -> list:
    """获取数据库中所有表名"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(cursor, table_name: str) -> str:
    """获取表的创建语句"""
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def escape_value(value) -> str:
    """转义 SQL 值"""
    if value is None:
        return "NULL"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    else:
        # 字符串：转义单引号
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


def export_table_data(cursor, table_name: str) -> list:
    """导出表数据为 INSERT 语句列表"""
    cursor.execute(f"SELECT * FROM [{table_name}]")
    rows = cursor.fetchall()

    if not rows:
        return []

    # 获取列名
    column_names = [description[0] for description in cursor.description]
    columns_str = ", ".join([f"[{col}]" for col in column_names])

    insert_statements = []
    for row in rows:
        values = ", ".join([escape_value(val) for val in row])
        stmt = f"INSERT INTO [{table_name}] ({columns_str}) VALUES ({values});"
        insert_statements.append(stmt)

    return insert_statements


def main():
    # 获取路径
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent

    source_path = backend_dir / SOURCE_DB

    if OUTPUT_SQL:
        output_path = backend_dir / OUTPUT_SQL
    else:
        output_path = source_path.with_suffix(".sql")

    # 检查源文件
    if not source_path.exists():
        print(f"错误: 数据库文件不存在 - {source_path}")
        return

    print(f"源数据库: {source_path}")
    print(f"输出文件: {output_path}")
    print("-" * 60)

    # 连接数据库
    conn = sqlite3.connect(str(source_path))
    cursor = conn.cursor()

    # 获取所有表
    tables = get_table_names(cursor)
    print(f"发现 {len(tables)} 个表: {', '.join(tables)}")

    # 构建 SQL 内容
    sql_lines = []

    # 添加头部注释
    sql_lines.append(f"-- 从 {source_path.name} 导出")
    sql_lines.append(f"-- 表数量: {len(tables)}")
    sql_lines.append("")

    if USE_TRANSACTION:
        sql_lines.append("BEGIN TRANSACTION;")
        sql_lines.append("")

    for table_name in tables:
        sql_lines.append(f"-- 表: {table_name}")
        sql_lines.append("-" * 40)

        # 表结构
        if INCLUDE_SCHEMA:
            schema = get_table_schema(cursor, table_name)
            if schema:
                sql_lines.append(f"DROP TABLE IF EXISTS [{table_name}];")
                sql_lines.append(schema + ";")
                sql_lines.append("")

        # 表数据
        if INCLUDE_DATA:
            if INCLUDE_DELETE and not INCLUDE_SCHEMA:
                sql_lines.append(f"DELETE FROM [{table_name}];")

            inserts = export_table_data(cursor, table_name)
            if inserts:
                sql_lines.extend(inserts)
                print(f"  {table_name}: {len(inserts)} 条记录")
            else:
                sql_lines.append(f"-- (空表)")
                print(f"  {table_name}: 空表")

        sql_lines.append("")

    if USE_TRANSACTION:
        sql_lines.append("COMMIT;")

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding=ENCODING) as f:
        f.write('\n'.join(sql_lines))

    conn.close()

    print("-" * 60)
    print(f"导出完成!")
    print(f"输出文件: {output_path}")
    print(f"文件大小: {output_path.stat().st_size / 1024:.2f} KB")


if __name__ == "__main__":
    main()

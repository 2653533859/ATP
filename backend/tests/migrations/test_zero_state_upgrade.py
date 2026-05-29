"""零状态迁移回归测试（Q7 A.1）。

目标：保证空库执行 `alembic upgrade head` 后，所有 ORM 模型对应的表都已建出，
彻底消灭 `create_all` 兜底带来的 schema drift 隐患。

由于项目用了不少 PostgreSQL 专属特性（ENUM、复合索引、partial index），
直接用 SQLite 跑全量 alembic upgrade 不可行。本测试用**静态扫描**作为替代：

  ORM 中 `Base.metadata.tables` 的所有表名 ⊆
  Alembic 迁移文件中 `op.create_table("<name>", ...)` 累计建出的表名集合

如果新增了 ORM 模型但忘写迁移，本测试会立即失败并打印缺失表列表，
比"上生产才发现"早数月。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.base import Base
from app.models.bootstrap import load_all_models


_VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"
# 匹配 op.create_table("name", ...) 或 op.create_table('name', ...)
_CREATE_TABLE_RE = re.compile(
    r"""op\.create_table\(\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']""",
    re.MULTILINE,
)
# 匹配 op.drop_table("name") / op.drop_table('name')
_DROP_TABLE_RE = re.compile(
    r"""op\.drop_table\(\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']""",
    re.MULTILINE,
)
# 匹配 op.rename_table("old", "new")
_RENAME_TABLE_RE = re.compile(
    r"""op\.rename_table\(\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']\s*,\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']""",
    re.MULTILINE,
)


def _collect_tables_from_migrations() -> set[str]:
    """扫描所有 alembic 迁移文件，模拟"线性应用"后剩余的表名集合。

    顺序按文件名升序（与项目 alembic revision 命名约定一致：`YYYYMMDD_NNNN_*.py`）。
    每个迁移内部按出现顺序应用 create / rename / drop。
    """
    tables: set[str] = set()
    files = sorted(_VERSIONS_DIR.glob("*.py"))
    assert files, "未找到任何 alembic 迁移文件"

    for f in files:
        if f.name.startswith("_"):
            continue
        # 只看 downgrade() 之前的迁移代码，避免 downgrade() 干扰，同时允许
        # upgrade() 调用 helper 中的 op.create_table。
        content = f.read_text(encoding="utf-8")
        upgrade_block = _extract_upgrade_side(content)
        if not upgrade_block:
            continue

        # 按行扫，保留出现顺序
        for match in re.finditer(
            r"""op\.(create_table|drop_table|rename_table)\(\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']\s*(?:,\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["'])?""",
            upgrade_block,
        ):
            op_name, t1, t2 = match.group(1), match.group(2), match.group(3)
            if op_name == "create_table":
                tables.add(t1)
            elif op_name == "drop_table":
                tables.discard(t1)
            elif op_name == "rename_table" and t2:
                tables.discard(t1)
                tables.add(t2)
    return tables


def _extract_upgrade_side(content: str) -> str:
    """提取 downgrade() 之前的代码，允许 upgrade helper 中声明 create_table。"""
    return re.split(r"\ndef\s+downgrade\(", content, maxsplit=1)[0]


def test_orm_tables_subset_of_alembic_created_tables():
    """关键回归：所有 ORM 模型的表必须在 alembic 迁移中被建出。

    失败提示：意味着某个新模型只靠 Base.metadata.create_all 才能建出，
    迁移路径缺失。修复方法：用 `alembic revision --autogenerate -m "..."`
    生成对应迁移并合入。
    """
    load_all_models()
    orm_tables = {t.name for t in Base.metadata.tables.values()}

    migration_tables = _collect_tables_from_migrations()

    missing = orm_tables - migration_tables
    assert not missing, (
        f"以下 ORM 表在 alembic 迁移中没有 create_table，纯 alembic 首建会缺表：\n"
        f"  {sorted(missing)}\n"
        f"修复：alembic revision --autogenerate -m 'add missing tables'\n"
        f"ORM 表数：{len(orm_tables)}，迁移建出表数：{len(migration_tables)}"
    )


def test_no_dangling_migration_drop_table():
    """所有迁移文件的 upgrade() 中 drop_table 的表，必须之前被 create_table 过。

    捕获典型 typo（如 drop_table 的名字与 create_table 不一致）。
    """
    files = sorted(_VERSIONS_DIR.glob("*.py"))
    created: set[str] = set()
    dangling: list[str] = []

    for f in files:
        if f.name.startswith("_"):
            continue
        content = f.read_text(encoding="utf-8")
        upgrade_block = _extract_upgrade_side(content)

        for match in re.finditer(
            r"""op\.(create_table|drop_table|rename_table)\(\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["']\s*(?:,\s*["']([a-zA-Z_][a-zA-Z0-9_]*)["'])?""",
            upgrade_block,
        ):
            op_name, t1, t2 = match.group(1), match.group(2), match.group(3)
            if op_name == "create_table":
                created.add(t1)
            elif op_name == "drop_table":
                if t1 not in created:
                    dangling.append(f"{f.name}: drop_table('{t1}') 但未被任何前置迁移 create_table")
                created.discard(t1)
            elif op_name == "rename_table" and t2:
                created.discard(t1)
                created.add(t2)

    assert not dangling, "迁移链条不一致：\n  " + "\n  ".join(dangling)


def test_alembic_head_resolvable():
    """alembic 配置可加载且能解析出 head revision；catches alembic.ini / env.py 损坏。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    assert cfg_path.exists(), "alembic.ini 缺失"
    cfg = Config(str(cfg_path))
    # alembic.ini 中的 script_location 是相对 backend/，单测从根跑时需要适配
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[2] / "alembic"),
    )
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    assert head is not None
    # head 应符合命名约定（与最新迁移文件一致）
    latest_file = sorted(_VERSIONS_DIR.glob("*.py"))[-1]
    assert head in latest_file.name, (
        f"alembic head={head}，但最新迁移文件是 {latest_file.name}，可能链断裂"
    )

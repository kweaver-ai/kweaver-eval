"""Eval-owned MySQL schema bootstrap.

The eval needs a known table set with proper PK constraints and enough rows
that subgraph / filter / query tests find real instances. Sharing the
upstream `supply_chain` DB with other suites left us at the mercy of their
residue (orphan tables, missing PKs, sparse data), so the eval owns its own
schema and re-seeds it on every session start.
"""

from __future__ import annotations

import pymysql

# Schema owned by the eval suite. Re-created on every test session.
EVAL_SCHEMA = "kweaver_eval"

# Table DDL — explicit primary keys so BKN auto-detection works without
# requiring the --pk-map workaround. The graph topology is intentionally
# 4 OTs / 3 RTs forming a chain (mat_skill -> materials -> suppliers and
# mat_skill -> skills) so multi-hop subgraph queries have a connected
# path to walk, not just a star.
_DDL = [
    """CREATE TABLE suppliers (
        supplier_id VARCHAR(50) NOT NULL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        region VARCHAR(50) NOT NULL DEFAULT 'unknown'
    )""",
    """CREATE TABLE materials (
        sku VARCHAR(50) NOT NULL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        current_stock INT NOT NULL DEFAULT 0,
        safety_stock INT NOT NULL DEFAULT 0,
        material_risk VARCHAR(50) NOT NULL DEFAULT 'normal',
        supplier_id VARCHAR(50) NOT NULL
    )""",
    """CREATE TABLE skills (
        skill_id VARCHAR(50) NOT NULL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        description VARCHAR(500) NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE mat_skill (
        sku VARCHAR(50) NOT NULL,
        skill_id VARCHAR(50) NOT NULL,
        PRIMARY KEY (sku, skill_id)
    )""",
]

# Seed data — enough breadth that subgraph / filter / cross-OT-property
# tests find real instances and shared property names. ~20 materials,
# ~10 skills, ~30 mat_skill relations, 5 suppliers.
_SUPPLIERS = [
    ("SUP-ALPHA", "Alpha Components Co", "asia"),
    ("SUP-BETA", "Beta Industrial Ltd", "europe"),
    ("SUP-GAMMA", "Gamma Precision Inc", "north-america"),
    ("SUP-DELTA", "Delta Logistics Group", "asia"),
    ("SUP-EPSILON", "Epsilon Materials SA", "europe"),
]

_MATERIALS = [
    # (sku, name, current_stock, safety_stock, material_risk, supplier_id)
    ("MAT-001", "Battery Cell", 40, 100, "critical", "SUP-ALPHA"),
    ("MAT-002", "Aluminum Frame", 350, 200, "normal", "SUP-BETA"),
    ("MAT-003", "Display Panel", 80, 120, "high", "SUP-ALPHA"),
    ("MAT-004", "Logic Board", 25, 60, "critical", "SUP-GAMMA"),
    ("MAT-005", "Cooling Fan", 410, 150, "normal", "SUP-DELTA"),
    ("MAT-006", "Power Supply", 95, 80, "normal", "SUP-GAMMA"),
    ("MAT-007", "Steel Bracket", 800, 300, "low", "SUP-BETA"),
    ("MAT-008", "Copper Wire", 1200, 500, "low", "SUP-EPSILON"),
    ("MAT-009", "Plastic Casing", 220, 150, "normal", "SUP-DELTA"),
    ("MAT-010", "Sensor Module", 55, 70, "high", "SUP-ALPHA"),
    ("MAT-011", "Memory Chip", 180, 120, "normal", "SUP-GAMMA"),
    ("MAT-012", "Antenna Array", 30, 50, "high", "SUP-ALPHA"),
    ("MAT-013", "Capacitor Set", 900, 400, "low", "SUP-EPSILON"),
    ("MAT-014", "Heat Sink", 140, 100, "normal", "SUP-DELTA"),
    ("MAT-015", "Camera Lens", 65, 80, "high", "SUP-BETA"),
    ("SUB-001A", "Battery Cell Substitute", 200, 50, "normal", "SUP-DELTA"),
    ("SUB-003A", "Display Panel Substitute", 150, 60, "normal", "SUP-EPSILON"),
    ("SUB-004A", "Logic Board Substitute", 90, 40, "normal", "SUP-BETA"),
    ("SUB-010A", "Sensor Module Substitute", 130, 50, "normal", "SUP-DELTA"),
    ("SUB-012A", "Antenna Array Substitute", 80, 30, "normal", "SUP-EPSILON"),
]

_SKILLS = [
    ("SK-SUBSWAP", "substitute_swap", "Swap to substitute material via MES"),
    ("SK-DEFAULT", "standard_replenish", "Default procurement order"),
    ("SK-EXPEDITE", "expedite_shipment", "Air-freight critical material"),
    ("SK-DUALSRC", "dual_sourcing", "Split order across two suppliers"),
    ("SK-VMI", "vmi_replenish", "Vendor-managed inventory restock"),
    ("SK-RESCHED", "reschedule_production", "Push out production date"),
    ("SK-DESIGN", "design_change", "Redesign with available BOM"),
    ("SK-SAFETY", "safety_stock_bump", "Raise safety-stock target"),
    ("SK-AUDIT", "supplier_audit", "Trigger supplier compliance audit"),
    ("SK-FORECAST", "demand_forecast_revise", "Re-forecast against new demand"),
]

# Each row picks (sku, skill_id). Multiple skills per material to make the
# graph non-trivial. ~30 relations.
_MAT_SKILL = [
    ("MAT-001", "SK-SUBSWAP"), ("MAT-001", "SK-EXPEDITE"), ("MAT-001", "SK-DUALSRC"),
    ("MAT-002", "SK-DEFAULT"), ("MAT-002", "SK-VMI"),
    ("MAT-003", "SK-SUBSWAP"), ("MAT-003", "SK-EXPEDITE"),
    ("MAT-004", "SK-SUBSWAP"), ("MAT-004", "SK-RESCHED"), ("MAT-004", "SK-DESIGN"),
    ("MAT-005", "SK-DEFAULT"),
    ("MAT-006", "SK-DEFAULT"), ("MAT-006", "SK-SAFETY"),
    ("MAT-007", "SK-DEFAULT"), ("MAT-007", "SK-VMI"),
    ("MAT-008", "SK-DEFAULT"), ("MAT-008", "SK-AUDIT"),
    ("MAT-009", "SK-DEFAULT"),
    ("MAT-010", "SK-EXPEDITE"), ("MAT-010", "SK-FORECAST"),
    ("MAT-011", "SK-DEFAULT"), ("MAT-011", "SK-SAFETY"),
    ("MAT-012", "SK-EXPEDITE"), ("MAT-012", "SK-DESIGN"),
    ("MAT-013", "SK-DEFAULT"),
    ("MAT-014", "SK-DEFAULT"),
    ("MAT-015", "SK-EXPEDITE"), ("MAT-015", "SK-FORECAST"),
    ("SUB-001A", "SK-SUBSWAP"),
    ("SUB-003A", "SK-SUBSWAP"),
    ("SUB-004A", "SK-SUBSWAP"),
]


def bootstrap(host: str, port: int, user: str, password: str) -> None:
    """Drop + recreate the eval schema and re-seed all tables.

    Idempotent — safe to call at the start of every test session.
    """
    conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{EVAL_SCHEMA}`")
            cur.execute(
                f"CREATE DATABASE `{EVAL_SCHEMA}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{EVAL_SCHEMA}`")
            for stmt in _DDL:
                cur.execute(stmt)
            # Insert suppliers first — materials reference them.
            cur.executemany(
                "INSERT INTO suppliers VALUES (%s, %s, %s)", _SUPPLIERS,
            )
            cur.executemany(
                "INSERT INTO materials VALUES (%s, %s, %s, %s, %s, %s)", _MATERIALS,
            )
            cur.executemany(
                "INSERT INTO skills VALUES (%s, %s, %s)", _SKILLS,
            )
            cur.executemany(
                "INSERT INTO mat_skill VALUES (%s, %s)", _MAT_SKILL,
            )
    finally:
        conn.close()

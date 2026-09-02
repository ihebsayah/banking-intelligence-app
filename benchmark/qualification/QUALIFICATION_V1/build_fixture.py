"""benchmark/qualification/QUALIFICATION_V1/build_fixture.py

Builds the immutable qualification fixture artifacts for banking_qual_v1:

  1. fixture_manifest.json — per-table row counts + md5 fingerprints, plus a
     schema fingerprint and a global dataset fingerprint.
  2. goldens_v1.json       — per-case expected_result recomputed by executing
     each frozen case's compiled SQL against banking_qual_v1. Golden and
     fixture agree BY CONSTRUCTION.

Requires: banking_qual_v1 (immutable TEMPLATE snapshot of banking_dev at
frozen time) — see README.md.
"""
from __future__ import annotations

import json
import os
import re
import sys

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "benchmark", "e2e_nl_sql"))

QUAL_DSN = os.environ.get("PG_TEST_DSN", "postgresql://banking_user:securepass123@localhost:5432/banking_qual_v1")
QUALS_DIR = os.path.dirname(os.path.abspath(__file__))

_PLACEHOLDER = re.compile(r"\$\d+")


def _table_names(cur) -> list:
    cur.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE' order by 1"
    )
    return [r[0] for r in cur.fetchall()]


def _fingerprint(cur, table: str) -> dict:
    cur.execute(
        f"select count(*), md5(coalesce(string_agg(t::text, chr(10) order by t::text), '')) "
        f"from (select t::text as t from public.\"{table}\" t) q"
    )
    n, h = cur.fetchone()
    return {"table": table, "row_count": int(n), "md5": h}


def _schema_fingerprint(cur) -> str:
    cur.execute(
        "select md5(coalesce(string_agg(table_name || '.' || column_name || ':' || data_type, "
        "'|' order by table_name, ordinal_position), '')) "
        "from information_schema.columns where table_schema='public'"
    )
    return cur.fetchone()[0]


def _exec(cur, sql, params) -> dict:
    try:
        cur.execute(_PLACEHOLDER.sub("%s", sql), [p["value"] for p in params])
        rows = cur.fetchall()
        names = [c[0] for c in cur.description] if cur.description else []
        return {"ran": True, "rows": rows, "column_names": names, "error": None}
    except Exception as exc:
        return {"ran": False, "rows": [], "column_names": [], "error": str(exc)[:200]}


def _derive_golden(ev: dict, res: dict) -> dict | None:
    exp = ev.get("expected_result")
    if exp is None:
        return None
    if not res.get("ran"):
        return {"error": res.get("error")}
    mode = exp.get("mode")
    rows, names = res.get("rows") or [], res.get("column_names") or []
    out = {"mode": mode}
    if mode in ("exact_scalar", "numeric_tolerance"):
        first = (rows[0][0] if rows and isinstance(rows[0], (list, tuple)) else rows[0] if rows else None)
        out["value"] = first
        if mode == "numeric_tolerance":
            out["tolerance"] = exp.get("tolerance", 0)
    elif mode == "row_count":
        out["value"] = len(rows)
    elif mode == "unordered_rows":
        out["rows"] = [{str(c).lower(): v for c, v in zip(names, row)} for row in rows[:10]]
    else:
        return None
    return out


def main() -> None:
    con = psycopg2.connect(QUAL_DSN)
    cur = con.cursor()

    tables = _table_names(cur)
    manifest = {
        "dataset": "QUALIFICATION_V1",
        "dsn": QUAL_DSN,
        "schema_fingerprint": _schema_fingerprint(cur),
        "tables": [_fingerprint(cur, t) for t in tables],
        "global_row_count": sum(_fingerprint(cur, t)["row_count"] for t in tables),
        "cases_total": len(json.load(open(os.path.join(ROOT, "benchmark", "e2e_nl_sql", "cases.json"), encoding="utf-8"))),
        "source": "TEMPLATE snapshot of banking_dev (immutable, read-only)",
    }

    cases = json.load(open(os.path.join(ROOT, "benchmark", "e2e_nl_sql", "cases.json"), encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}

    traces_path = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "results", "E2E_POST_VALIDATION_FIX_V2_traces.jsonl")
    goldens = {}
    for line in open(traces_path, encoding="utf-8"):
        tr = json.loads(line)
        c = by_id.get(tr["id"])
        if not c or c["expected"].get("expected_result") is None:
            continue
        sql = (tr.get("compile") or {}).get("sql")
        if not sql:
            continue
        params = (tr.get("compile") or {}).get("parameters", [])
        res = _exec(cur, sql, params)
        golden = _derive_golden(c["expected"], res)
        if golden is not None:
            goldens[tr["id"]] = golden

    with open(os.path.join(QUALS_DIR, "fixture_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(QUALS_DIR, "goldens_v1.json"), "w", encoding="utf-8") as fh:
        json.dump(goldens, fh, indent=2, default=str)

    manifest["goldens_derived"] = len(goldens)
    print(json.dumps(manifest, indent=2))
    print(f"\ngoldens_v1.json entries: {len(goldens)}")
    con.close()


if __name__ == "__main__":
    main()
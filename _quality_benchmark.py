import json
import re
from urllib import request

BASE_URL = "http://127.0.0.1:8000/api/query"

TESTS = [
    {"name": "basic_read", "prompt": "show all rows from auditlog", "expect": r"FROM\s+auditlog", "risk": r"low", "dry": True, "expect_success": True, "comment": "Simple read request should preview cleanly."},
    {"name": "limit_read", "prompt": "show rows from employee limit 5", "expect": r"FROM\s+employee", "risk": r"low", "dry": True, "expect_success": True, "comment": "Preview path should keep the limit request intact."},
    {"name": "schema_tables", "prompt": "show all tables", "expect": r"SHOW\s+TABLES", "risk": r"low", "dry": True, "expect_success": True, "comment": "Deterministic schema shortcut should fire here."},
    {"name": "schema_row_counts", "prompt": "show all tables and row counts", "expect": r"INFORMATION_SCHEMA\.TABLES", "risk": r"low", "dry": True, "expect_success": True, "comment": "Schema analytics should use INFORMATION_SCHEMA."},
    {"name": "top_n_simple", "prompt": "top 5 employee", "expect": r"FROM\s+employee", "risk": r"low", "dry": True, "expect_success": True, "comment": "Plain top-N request should use the deterministic fast path."},
    {"name": "duplicate_emails", "prompt": "find duplicate email addresses", "expect": r"(GROUP\s+BY|HAVING|COUNT\\()", "risk": r"low", "dry": True, "expect_success": True, "comment": "Duplicate detection should stay analytic and low risk."},
    {"name": "recent_records", "prompt": "list the 10 most recently created records", "expect": r"(ORDER\s+BY|LIMIT\s+10)", "risk": r"low", "dry": True, "expect_success": True, "comment": "Recent-record request should preserve ordering and limit semantics."},
    {"name": "join_like", "prompt": "list artists with their exhibition names", "expect": r"(JOIN|FROM\s+artist_|FROM\s+exhibition)", "risk": r"low", "dry": True, "expect_success": True, "comment": "Join-oriented prompt should reference the linked tables."},
    {"name": "aggregation", "prompt": "count employees by role", "expect": r"(GROUP\s+BY|COUNT\\()", "risk": r"low", "dry": True, "expect_success": True, "comment": "Grouped count query should remain low risk in preview."},
    {"name": "high_risk_delete_blocked", "prompt": "delete all rows from auditlog", "expect": r"DELETE", "risk": r"(high|critical)", "dry": True, "expect_success": False, "comment": "Unsafe row delete without WHERE should be rejected even in preview."},
    {"name": "ddl_drop_requires_confirmation", "prompt": "drop table auditlog", "expect": r"DROP\s+TABLE", "risk": r"(high|critical)", "dry": True, "expect_success": False, "expect_confirmation": False, "comment": "DDL preview without confirmation should stay blocked by policy."},
    {"name": "ddl_delete_table_alias", "prompt": "delete table auditlog", "expect": r"DROP\s+TABLE", "risk": r"(high|critical)", "dry": True, "confirm": True, "expect_success": True, "comment": "Delete-table phrasing should normalize to schema-drop intent."},
    {"name": "ddl_drop_preview_confirmed", "prompt": "drop table auditlog", "expect": r"DROP\s+TABLE", "risk": r"(high|critical)", "dry": True, "confirm": True, "expect_success": True, "comment": "Confirmed preview should show the DDL plan without executing it."},
    {"name": "generate_api_route", "prompt": "show all tables and row counts", "expect": r"INFORMATION_SCHEMA\.TABLES", "risk": r"low", "dry": False, "generate_api": True, "expect_success": True, "expect_api": True, "comment": "Successful execution should also return generated API code."},
    {"name": "update_guarded", "prompt": "update employee set salary=0", "expect": r"UPDATE\s+employee", "risk": r"(high|critical)", "dry": True, "expect_success": False, "comment": "UPDATE without WHERE should be blocked by validation."},
]


def call_query(prompt: str, dry_run: bool, generate_api: bool = False, confirm_high_risk: bool = False) -> dict:
    payload = json.dumps(
        {
            "request": prompt,
            "dry_run": dry_run,
            "generate_api": generate_api,
            "confirm_high_risk": confirm_high_risk,
        }
    ).encode("utf-8")
    req = request.Request(BASE_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    results = []

    for test in TESTS:
        try:
            response = call_query(
                test["prompt"],
                test["dry"],
                generate_api=test.get("generate_api", False),
                confirm_high_risk=test.get("confirm", False),
            )
            sql = (response.get("sql") or "")
            api_route = response.get("api_route") or ""
            results.append(
                {
                    "case": test["name"],
                    "comment": test.get("comment", ""),
                    "success": bool(response.get("success")),
                    "success_ok": bool(response.get("success")) == test.get("expect_success", True),
                    "risk": response.get("risk_level"),
                    "risk_ok": bool(re.search(test["risk"], str(response.get("risk_level") or ""), flags=re.IGNORECASE)),
                    "sql_ok": bool(re.search(test["expect"], sql, flags=re.IGNORECASE)),
                    "api_ok": bool(api_route.strip()) == test.get("expect_api", False),
                    "requires_confirmation": bool(response.get("requires_confirmation")),
                    "confirmation_ok": (
                        bool(response.get("requires_confirmation")) == test["expect_confirmation"]
                        if "expect_confirmation" in test else True
                    ),
                    "corrections": int(response.get("correction_attempts") or 0),
                    "error": response.get("error") or "",
                    "sql": sql.replace("\n", " "),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "case": test["name"],
                    "comment": test.get("comment", ""),
                    "success": False,
                    "success_ok": False,
                    "risk": "n/a",
                    "risk_ok": False,
                    "sql_ok": False,
                    "api_ok": False,
                    "requires_confirmation": False,
                    "confirmation_ok": False,
                    "corrections": 0,
                    "error": str(exc),
                    "sql": "",
                }
            )

    total = len(results)
    summary = {
        "total": total,
        "success_count": sum(1 for item in results if item["success"]),
        "success_match_count": sum(1 for item in results if item["success_ok"]),
        "sql_match_count": sum(1 for item in results if item["sql_ok"]),
        "risk_match_count": sum(1 for item in results if item["risk_ok"]),
        "api_match_count": sum(1 for item in results if item["api_ok"]),
        "confirmation_match_count": sum(1 for item in results if item["confirmation_ok"]),
        "avg_corrections": round(sum(item["corrections"] for item in results) / total, 2) if total else 0.0,
    }

    print("===SUMMARY===")
    print(json.dumps(summary, indent=2))
    print("===DETAILS===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

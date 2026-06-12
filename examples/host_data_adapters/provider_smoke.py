"""Provider smoke test — runs health_check for each example adapter.

Reports status (OK / SKIPPED / FAILED) and documents credential
assessment results. No network calls are made.
"""

from __future__ import annotations

from typing import Any

from eastmoney_adapter import EastmoneyAdapter, smoke_test as eastmoney_smoke
from xueqiu_adapter import XueqiuAdapter, smoke_test as xueqiu_smoke


def run_smoke_tests() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    eastmoney_result = eastmoney_smoke()
    results.append(eastmoney_result)

    xueqiu_result = xueqiu_smoke()
    results.append(xueqiu_result)

    return results


def print_report(results: list[dict[str, Any]]) -> None:
    print("=" * 60)
    print("Provider Smoke Test Report")
    print("=" * 60)

    for r in results:
        provider = r["provider"]
        status = r["status"]
        if status == "OK":
            icon = "[OK]"
        elif status == "SKIPPED":
            icon = "[SKIPPED]"
        else:
            icon = "[FAILED]"

        print(f"\n{icon} {provider}")

        assessment = r.get("credential_assessment")
        if assessment:
            print(f"  Credential Assessment:")
            for k, v in assessment.items():
                if k == "note" or k == "reason":
                    if v:
                        print(f"    {k}: {v}")
                else:
                    print(f"    {k}: {v}")

        cred_trace = r.get("credential_trace")
        if cred_trace:
            print(f"  Credential Trace (redacted):")
            for k, v in cred_trace.items():
                print(f"    {k}: {v}")

        health = r.get("health")
        if health and health.get("errors"):
            print(f"  Errors: {health['errors']}")
        if health and health.get("warnings"):
            print(f"  Warnings: {health['warnings']}")

    print("\n" + "=" * 60)
    ok_count = sum(1 for r in results if r["status"] == "OK")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")
    print(f"Summary: {ok_count} OK, {skipped_count} SKIPPED, {failed_count} FAILED")
    print("=" * 60)


if __name__ == "__main__":
    results = run_smoke_tests()
    print_report(results)

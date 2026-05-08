#!/usr/bin/env python3
"""
End-to-End KPI Tracking Test Script - Version 2 (Big Contract)

Flow:
  1. Ingest a large, complex contract (global_logistics_v2.md)
  2. Run KPI extraction (analyse --intent kpi --sync)
  3. Save KPIs to vault (save-kpis)
  4. Ingest a large set of actuals (actuals_v2.json)
  5. Check breaches
  6. Verify everything persisted in MongoDB
  7. Report results
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = Path(__file__).resolve().parent
CLI = PROJECT_ROOT / "cli.py"
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python3"

# Use a unique contract ID per run
CONTRACT_ID = f"E2E-BIG-LOGISTICS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
CONTRACT_NAME = "Global Multi-Modal Logistics Agreement v2"
CONTRACT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "global_logistics_v2.md"
ACTUALS_FILE_PATH = TEST_DIR / "actuals_v2.json"

def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or str(PROJECT_ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_cli(*args) -> tuple[int, str, str]:
    """Run a CLI command via python cli.py <args>."""
    cmd = [str(VENV_PYTHON), str(CLI)] + list(args)
    return _run(cmd)


# ---------------------------------------------------------------------------
# Step 1: Ingest contract
# ---------------------------------------------------------------------------
def step_1_ingest_contract():
    print("\n" + "=" * 60)
    print(" STEP 1: Ingest Big Contract")
    print("=" * 60)

    rc, out, err = run_cli(
        "ingest", str(CONTRACT_PATH),
        "--name", CONTRACT_NAME,
        "--id", CONTRACT_ID,
        "--overwrite",
    )
    print(out)
    if err:
        print(err, file=sys.stderr)
    if rc != 0:
        print(f"[FAIL] ingest exited with code {rc}", file=sys.stderr)
        sys.exit(1)
    print("[PASS] Contract ingested successfully.\n")


# ---------------------------------------------------------------------------
# Step 2: Extract KPIs
# ---------------------------------------------------------------------------
def step_2_extract_kpis():
    print("=" * 60)
    print(" STEP 2: Extract KPIs (Agentic Analysis)")
    print("=" * 60)

    rc, out, err = run_cli("analyse", CONTRACT_ID, "--intent", "kpi", "--sync")
    print(out)
    if err:
        print(err, file=sys.stderr)
    if rc != 0:
        print(f"[FAIL] analyse exited with code {rc}", file=sys.stderr)
        sys.exit(1)
    print("[PASS] KPI extraction completed.\n")


# ---------------------------------------------------------------------------
# Step 3: Save KPIs to vault
# ---------------------------------------------------------------------------
def step_3_save_kpis():
    print("=" * 60)
    print(" STEP 3: Save KPIs to Vault")
    print("=" * 60)

    rc, out, err = run_cli("save-kpis", CONTRACT_ID)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if rc != 0:
        print(f"[FAIL] save-kpis exited with code {rc}", file=sys.stderr)
        sys.exit(1)
    print("[PASS] KPIs saved to vault.\n")


# ---------------------------------------------------------------------------
# Step 4: Ingest actuals (Multiple Sources)
# ---------------------------------------------------------------------------
def step_4_ingest_actuals():
    print("=" * 60)
    print(" STEP 4: Ingest Actuals (Granular File-Per-KPI)")
    print("=" * 60)

    granularity_dir = TEST_DIR / "granularity"
    if not granularity_dir.exists():
        print(f"[ERROR] Granularity directory not found: {granularity_dir}", file=sys.stderr)
        sys.exit(1)

    actual_files = sorted(list(granularity_dir.glob("*.csv")) + list(granularity_dir.glob("*.json")))
    print(f"  [DIR] Found {len(actual_files)} granular data files in {granularity_dir.name}/")

    for f in actual_files:
        print(f"  [SOURCE] Ingesting {f.name}...")
        rc, out, err = run_cli("ingest-actuals", CONTRACT_ID, "--file", str(f))
        if rc != 0:
            print(f"    [FAIL] Ingestion failed for {f.name}: {err}", file=sys.stderr)
            sys.exit(1)
        print(f"    [OK] {out.strip()}")

    print(f"[PASS] All {len(actual_files)} granular actuals ingested successfully.\n")


# ---------------------------------------------------------------------------
# Step 5: Check breaches
# ---------------------------------------------------------------------------
def step_5_check_breaches():
    print("=" * 60)
    print(" STEP 5: Check Breaches")
    print("=" * 60)

    rc, out, err = run_cli("check-breaches", CONTRACT_ID)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if rc != 0:
        print(f"[FAIL] check-breaches exited with code {rc}", file=sys.stderr)
        sys.exit(1)
    print("[PASS] Breach check completed.\n")


# ---------------------------------------------------------------------------
# Step 6: Verify DB persistence
# ---------------------------------------------------------------------------
async def step_6_verify_db():
    print("=" * 60)
    print(" STEP 6: Verify DB Persistence")
    print("=" * 60)

    # Import after sys.path setup
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.db.mongodb import MongoDB

    await MongoDB.connect()

    # 6a: Contract exists
    contract = await MongoDB.get_contract(CONTRACT_ID)
    assert contract is not None, f"Contract {CONTRACT_ID} not found in DB!"
    print(f"  [DB] Contract found: {contract['name']} (ID: {contract['contract_id']})")

    # 6b: KPIs exist
    kpis = await MongoDB.get_kpis(CONTRACT_ID)
    assert len(kpis) > 0, "No KPIs found in vault!"
    print(f"  [DB] KPIs in vault: {len(kpis)}")
    for kpi in kpis:
        print(f"       - {kpi['name']} [{kpi.get('kpi_id', 'N/A')}] -> {kpi['operator']} {kpi['value_min']} {kpi['unit']}")

    # 6c: Actuals exist
    actuals = await MongoDB.get_latest_actuals(CONTRACT_ID)
    print(f"  [DB] Actuals ingested: {len(actuals)}")
    for actual in actuals:
        print(f"       - KPI {actual['kpi_id']}: {actual['value']} {actual['unit']}")

    # 6d: Breaches exist
    breaches = await MongoDB.get_breaches(CONTRACT_ID)
    print(f"  [DB] Breach records: {len(breaches)}")
    breach_count = sum(1 for b in breaches if b.get("is_breach"))
    on_track_count = len(breaches) - breach_count
    print(f"       - Breaches: {breach_count}")
    print(f"       - On-track: {on_track_count}")

    for b in breaches:
        status = "BREACH" if b["is_breach"] else "ON TRACK"
        print(f"       - {b['kpi_id']}: actual={b['actual_value']:.2f}, threshold={b['operator']} {b['threshold_value']:.2f} -> {status}")

    await MongoDB.disconnect()
    print("[PASS] DB verification complete.\n")

    return {
        "contract_id": CONTRACT_ID,
        "kpis_found": len(kpis),
        "actuals_found": len(actuals),
        "breach_records": len(breaches),
        "breaches": breach_count,
        "on_track": on_track_count,
    }


def main():
    print("\n" + "=" * 60)
    print(" E2E BIG CONTRACT KPI TEST")
    print(f" Contract ID: {CONTRACT_ID}")
    print("=" * 60)

    # Verify environment
    if not VENV_PYTHON.exists():
        print(f"[ERROR] Python not found at {VENV_PYTHON}", file=sys.stderr)
        sys.exit(1)

    # Run steps
    step_1_ingest_contract()
    step_2_extract_kpis()
    step_3_save_kpis()
    step_4_ingest_actuals()
    step_5_check_breaches()
    summary = asyncio.run(step_6_verify_db())

    # Final report
    print("=" * 60)
    print(" E2E TEST SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if summary["breaches"] > 0 and summary["on_track"] > 0:
        print("\n[PASS] End-to-end KPI tracking workflow for big contract completed successfully!")
    else:
        print("\n[WARNING] Expected at least 1 breach and 1 on-track KPI. Check if KPI extraction caught all IDs.")


if __name__ == "__main__":
    main()

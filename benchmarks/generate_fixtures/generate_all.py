"""Master script: generates all 10 benchmark fixture files."""
import sys
import time
import importlib.util
from pathlib import Path

# Ensure this script can be run from anywhere
THIS_DIR  = Path(__file__).parent
BENCH_DIR = THIS_DIR.parent

GENERATORS = [
    ("gen_01_server_logs",   "server_logs.csv"),
    ("gen_02_sales",          "sales_transactions.csv"),
    ("gen_03_financial",      "financial_statements.json"),
    ("gen_04_hr",             "hr_employees.csv"),
    ("gen_05_reviews",        "customer_reviews.txt"),
    ("gen_06_inventory",      "warehouse_inventory.csv"),
    ("gen_07_network",        "network_monitoring.csv"),
    ("gen_08_support",        "support_tickets.json"),
    ("gen_09_manufacturing",  "manufacturing_quality.csv"),
    ("gen_10_ecommerce",      "ecommerce_events.csv"),
]


def load_module(name: str):
    """Load a generator module by file path."""
    mod_path = THIS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    fixtures_dir = BENCH_DIR / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    print(f"Generating fixtures → {fixtures_dir}\n")

    force = "--force" in sys.argv
    total_start = time.time()
    generated = []

    for mod_name, file_name in GENERATORS:
        out_file = fixtures_dir / file_name
        if out_file.exists() and not force:
            size_kb = out_file.stat().st_size // 1024
            print(f"  [SKIP] {file_name} already exists ({size_kb} KB) — use --force to regenerate")
            generated.append(file_name)
            continue

        print(f"  Generating {file_name}...")
        t0 = time.time()
        try:
            mod = load_module(mod_name)
            mod.generate()
            elapsed = round(time.time() - t0, 1)
            print(f"    Done in {elapsed}s")
            generated.append(file_name)
        except Exception as e:
            print(f"    ERROR in {mod_name}: {e}")
            import traceback
            traceback.print_exc()

    total_elapsed = round(time.time() - total_start, 1)
    print(f"\n{'='*50}")
    print(f"Generated {len(generated)}/{len(GENERATORS)} datasets in {total_elapsed}s")
    print()

    total_size_mb = 0.0
    for fname in generated:
        fpath = fixtures_dir / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / 1024 / 1024
            total_size_mb += size_mb
            gt_path = fixtures_dir / (fpath.stem + "_ground_truth.json")
            gt_status = "✓ GT" if gt_path.exists() else "✗ NO GT"
            print(f"  {fname:<38} {size_mb:>6.1f} MB  {gt_status}")

    print(f"\n  Total size: {total_size_mb:.1f} MB")
    print("\nReady to run benchmark:")
    print("  python run_benchmark.py")
    print("  python run_benchmark.py --dataset 01_server_logs --mode both")


if __name__ == "__main__":
    main()

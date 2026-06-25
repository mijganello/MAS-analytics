"""Master script: generates all 5 benchmark fixture files (small + big)."""
import sys
import time
import importlib.util
from pathlib import Path

THIS_DIR  = Path(__file__).parent
BENCH_DIR = THIS_DIR.parent

GENERATORS = [
    ("gen_01_rocket_launch",    "rocket_launches.csv"),
    ("gen_02_faculty_grades",   "faculty_grades.csv"),
    ("gen_03_teacher_workload", "teacher_workload.csv"),
    ("gen_04_shop_reviews",     "shop_reviews.csv"),
    ("gen_05_server_logs",      "server_logs.csv"),
]


def load_module(name: str):
    mod_path = THIS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    fixtures_dir = BENCH_DIR / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    big    = "--big" in sys.argv
    force  = "--force" in sys.argv
    mode   = "BIG" if big else "small"

    print(f"Generating {mode} fixtures → {fixtures_dir}\n")

    total_start = time.time()

    for mod_name, file_name in GENERATORS:
        mod = load_module(mod_name)
        # Determine output file name based on mode
        if big:
            stem = Path(file_name).stem
            suffix = Path(file_name).suffix
            out_file = fixtures_dir / f"{stem}_big{suffix}"
        else:
            out_file = fixtures_dir / file_name

        if out_file.exists() and not force:
            print(f"  [SKIP] {out_file.name} — use --force to regenerate")
            continue
        print(f"  Generating {out_file.name}...")
        t0 = time.time()
        mod.generate(big=big)
        print(f"    Done in {round(time.time() - t0, 1)}s")

    print(f"\nDone in {round(time.time() - total_start, 1)}s")
    print("Run: python benchmarks/run_benchmark.py" + (" --big" if big else ""))


if __name__ == "__main__":
    main()


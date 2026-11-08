"""Rebuild data/processed/ end to end: pull -> metrics -> graph -> predict -> explain.

Every HTTP response is cached in data/raw/, so a re-run costs nothing once the cache is warm.
Usage: python run_all.py [--skip-pull] [--skip-explain]
"""
import argparse
import subprocess
import sys

STEPS = [
    ("pull", [sys.executable, "-m", "src.pull", "--step", "all"]),
    ("metrics", [sys.executable, "-m", "src.metrics"]),
    ("graph", [sys.executable, "-m", "src.graph"]),
    ("predict", [sys.executable, "-m", "src.predict"]),
    ("explain", [sys.executable, "-m", "src.explain"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pull", action="store_true")
    ap.add_argument("--skip-explain", action="store_true")
    a = ap.parse_args()
    for name, cmd in STEPS:
        if (name == "pull" and a.skip_pull) or (name == "explain" and a.skip_explain):
            print(f"== skip {name}")
            continue
        print(f"== {name}", flush=True)
        subprocess.run(cmd, check=True)
    print("done: data/processed/ rebuilt")


if __name__ == "__main__":
    main()

"""Command line: python -m degree_day TEMPS.csv USAGE.csv [--mode heating|cooling] [--column NAME]."""
from __future__ import annotations

import argparse
import sys

from .core import fit, monthly_degree_days, normalize, read_temps, read_usage


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="degree_day", description="Weather-normalize monthly utility use")
    parser.add_argument("temps", help="CSV: date,mean_temp_f")
    parser.add_argument("usage", help="CSV: month,<column>")
    parser.add_argument("--mode", default="heating", choices=["heating", "cooling"])
    parser.add_argument("--column", default="therms")
    parser.add_argument("--base", type=float, default=65.0, help="balance point in F")
    args = parser.parse_args(argv)
    try:
        dd = monthly_degree_days(read_temps(args.temps), args.mode, args.base)
        usage = read_usage(args.usage, args.column)
        model = fit(usage, dd)
        rows = normalize(usage, dd, model)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"model: {args.column} = {model.baseload:.0f} + {model.slope:.2f} x {args.mode} degree days (R2 {model.r_squared:.3f})")
    print(f"{'month':<8}{'DD':>8}{'actual':>9}{'normal':>9}{'diff':>8}")
    for r in rows:
        print(f"{r['month']:<8}{r['degree_days']:>8.0f}{r['actual']:>9.0f}{r['normalized']:>9.0f}{r['difference']:>+8.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

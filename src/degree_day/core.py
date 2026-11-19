"""Degree days, a linear weather model, and normalization to typical weather."""
from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Model:
    """usage = baseload + slope * degree_days, fitted by least squares."""

    baseload: float
    slope: float
    r_squared: float


def read_temps(path: str | Path) -> list[tuple[date, float]]:
    """Read daily mean temperatures (date, mean_temp_f) from CSV."""
    rows: list[tuple[date, float]] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                rows.append((date.fromisoformat(row["date"]), float(row["mean_temp_f"])))
            except (KeyError, ValueError) as exc:
                raise ValueError(f"temps line {line_no}: {exc}") from exc
    return rows


def read_usage(path: str | Path, column: str) -> dict[str, float]:
    """Read monthly usage as {'YYYY-MM': value}."""
    out: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                out[row["month"]] = float(row[column])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"usage line {line_no}: {exc}") from exc
    return out


def monthly_degree_days(
    temps: list[tuple[date, float]], mode: str = "heating", base: float = 65.0
) -> dict[str, float]:
    """Sum daily degree days per month. Months with missing days are left out."""
    if mode not in ("heating", "cooling"):
        raise ValueError("mode must be 'heating' or 'cooling'")
    totals: dict[str, float] = defaultdict(float)
    days: dict[str, set[int]] = defaultdict(set)
    for day, temp in temps:
        key = f"{day.year}-{day.month:02d}"
        gap = base - temp if mode == "heating" else temp - base
        totals[key] += max(0.0, gap)
        days[key].add(day.day)
    return {
        key: round(total, 1)
        for key, total in totals.items()
        if len(days[key]) == calendar.monthrange(int(key[:4]), int(key[5:]))[1]
    }


def fit(usage: dict[str, float], dd: dict[str, float]) -> Model:
    """Least squares line through (degree days, usage) for months present in both."""
    keys = sorted(set(usage) & set(dd))
    if len(keys) < 3:
        raise ValueError("need at least 3 months with both usage and weather")
    xs = [dd[k] for k in keys]
    ys = [usage[k] for k in keys]
    n = len(keys)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("degree days do not vary, cannot fit a model")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    baseload = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (baseload + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot
    return Model(baseload, slope, r2)


def normal_degree_days(dd: dict[str, float]) -> dict[int, float]:
    """Average degree days for each calendar month (1 to 12) across all years given."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for key, value in dd.items():
        buckets[int(key[5:])].append(value)
    return {month: sum(v) / len(v) for month, v in buckets.items()}


def normalize(usage: dict[str, float], dd: dict[str, float], model: Model) -> list[dict[str, float | str]]:
    """Return per-month actual use, weather-normalized use and the difference."""
    normals = normal_degree_days(dd)
    rows: list[dict[str, float | str]] = []
    for key in sorted(usage):
        month = int(key[5:])
        if key not in dd or month not in normals:
            continue
        typical = model.baseload + model.slope * normals[month]
        rows.append(
            {
                "month": key,
                "degree_days": dd[key],
                "actual": usage[key],
                "normalized": round(typical, 1),
                "difference": round(usage[key] - typical, 1),
            }
        )
    return rows

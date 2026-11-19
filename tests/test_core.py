from datetime import date, timedelta

import pytest

from degree_day.__main__ import main
from degree_day.core import Model, fit, monthly_degree_days, normal_degree_days, normalize, read_temps, read_usage


def month_of(year, month, temp):
    d = date(year, month, 1)
    out = []
    while d.month == month:
        out.append((d, temp))
        d += timedelta(1)
    return out


def test_heating_degree_days_one_month():
    dd = monthly_degree_days(month_of(2024, 1, 45.0))
    assert dd["2024-01"] == 31 * 20


def test_cooling_degree_days():
    dd = monthly_degree_days(month_of(2024, 6, 75.0), mode="cooling")
    assert dd["2024-06"] == 30 * 10


def test_warm_days_give_zero_heating():
    assert monthly_degree_days(month_of(2024, 7, 80.0))["2024-07"] == 0


def test_incomplete_month_is_dropped():
    temps = month_of(2024, 2, 40.0)[:-1]
    assert monthly_degree_days(temps) == {}


def test_custom_base():
    dd = monthly_degree_days(month_of(2024, 1, 55.0), base=60.0)
    assert dd["2024-01"] == 31 * 5


def test_bad_mode():
    with pytest.raises(ValueError):
        monthly_degree_days([], mode="sideways")


def test_fit_recovers_exact_line():
    dd = {"2024-01": 100, "2024-02": 200, "2024-03": 300, "2024-04": 400}
    usage = {k: 500 + 3 * v for k, v in dd.items()}
    m = fit(usage, dd)
    assert m.baseload == pytest.approx(500)
    assert m.slope == pytest.approx(3)
    assert m.r_squared == pytest.approx(1)


def test_fit_needs_three_months():
    with pytest.raises(ValueError, match="at least 3"):
        fit({"2024-01": 1, "2024-02": 2}, {"2024-01": 1, "2024-02": 2})


def test_fit_flat_weather_rejected():
    keys = ["2024-01", "2024-02", "2024-03"]
    with pytest.raises(ValueError, match="do not vary"):
        fit({k: 1.0 for k in keys}, {k: 5.0 for k in keys})


def test_normal_degree_days_average_by_month():
    n = normal_degree_days({"2023-01": 100, "2024-01": 300, "2024-02": 50})
    assert n[1] == 200 and n[2] == 50


def test_normalize_uses_typical_weather():
    dd = {"2023-01": 100, "2024-01": 300}
    usage = {"2024-01": 1500.0}
    rows = normalize(usage, dd, Model(baseload=500, slope=3, r_squared=1))
    assert rows[0]["normalized"] == 500 + 3 * 200
    assert rows[0]["difference"] == 400


def test_read_bad_temp_row(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("date,mean_temp_f\n2024-01-01,abc\n")
    with pytest.raises(ValueError, match="line 2"):
        read_temps(p)


def test_read_usage_missing_column(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("month,kwh\n2024-01,5\n")
    with pytest.raises(ValueError):
        read_usage(p, "therms")


def test_example_files_give_strong_fit(capsys):
    assert main(["examples/daily_temps.csv", "examples/gas_use.csv"]) == 0
    assert "R2 0.9" in capsys.readouterr().out


def test_cli_missing_file():
    assert main(["nope.csv", "nope2.csv"]) == 1

"""驾驶舱送出的 1825 天必须被分析接口接受，其它天数不能再静默改成 180。"""
import pytest

from backend.services.analysis.analysis_days import resolve_analysis_days


def test_accepts_five_year_window():
    assert resolve_analysis_days(1825) == 1825
    assert resolve_analysis_days("1825") == 1825
    assert resolve_analysis_days(90) == 90
    assert resolve_analysis_days(None) == 180


def test_rejects_unsupported_window():
    with pytest.raises(ValueError, match="1825"):
        resolve_analysis_days(400)
    with pytest.raises(ValueError):
        resolve_analysis_days("半年")

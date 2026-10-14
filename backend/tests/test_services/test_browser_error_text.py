"""浏览器可见的失败信息不得带上异常原文。"""
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]

BROWSER_FACING_FILES = (
    "api/routes/analysis_routes.py",
    "api/routes/etf_routes.py",
    "services/data/startup_sync_service.py",
    "services/analysis/universe_matrix_backtest_service.py",
    "services/analysis/grid_fit_service.py",
)


def test_browser_responses_do_not_embed_exception_text():
    """接口和榜单状态只保留固定中文，异常原文留在日志。"""
    for relative in BROWSER_FACING_FILES:
        text = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "logger." in line:
                continue
            leaked = (
                "{str(e)}" in line
                or "{str(exc)}" in line
                or "str(e)[:30]" in line
                or "last_error=str(" in line
                or '_job_state["error"] = str(' in line
                or ("status_reason" in line and "str(" in line)
            )
            assert not leaked, f"{relative}:{line_no} 仍把异常原文交给浏览器: {line.strip()}"

"""文献路径来自配置和仓库，不写死某台电脑。"""
from pathlib import Path

from backend.services.analysis.literature_paths import (
    eda_literature_candidates,
    resolve_eda_literature,
)

ROUTE_FILE = Path(__file__).resolve().parents[2] / "api" / "routes" / "analysis_routes.py"


def test_configured_path_wins_and_home_path_is_gone(tmp_path):
    essay = tmp_path / "网格3篇.md"
    essay.write_text("正文", encoding="utf-8")
    found = resolve_eda_literature(
        {"EDA_LITERATURE_PATH": str(essay)},
        route_file=str(ROUTE_FILE),
    )
    assert found == str(essay)
    candidates = "\n".join(eda_literature_candidates({}, route_file=str(ROUTE_FILE)))
    assert "/Users/johnny" not in candidates
    assert "/Users/johnny" not in ROUTE_FILE.read_text(encoding="utf-8")


def test_repo_copy_resolves_without_config():
    found = resolve_eda_literature({}, route_file=str(ROUTE_FILE))
    assert found is not None
    assert found.endswith("网格3篇.md")
    assert Path(found).is_file()

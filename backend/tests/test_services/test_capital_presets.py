"""资金快选不能超过接口允许的 100 万。"""
import importlib.util
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ROUTE_FILE = BACKEND_ROOT / "api" / "routes" / "etf_routes.py"
CAPITAL_CAP = 1_000_000


def _load_schemas():
    path = BACKEND_ROOT / "api" / "schemas.py"
    spec = importlib.util.spec_from_file_location("capital_schemas", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CapitalPreset = _load_schemas().CapitalPreset


def test_schema_presets_stay_within_cap():
    presets = CapitalPreset.get_default_presets()
    assert presets
    assert all(preset["value"] <= CAPITAL_CAP for preset in presets)
    assert 1_500_000 not in {preset["value"] for preset in presets}


def test_route_presets_stay_within_cap():
    text = ROUTE_FILE.read_text(encoding="utf-8")
    assert "1500000" not in text
    assert "2000000" not in text

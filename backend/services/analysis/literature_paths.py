"""E大文献路径。优先读配置，其次仓库内文件，不再写死个人机器路径。"""
import os
from typing import List, Mapping, Optional


def eda_literature_candidates(
    environ: Optional[Mapping[str, str]] = None,
    route_file: Optional[str] = None,
) -> List[str]:
    """候选路径。EDA_LITERATURE_PATH 非空时排在最前。"""
    env = os.environ if environ is None else environ
    configured = str(env.get("EDA_LITERATURE_PATH", "")).strip()
    candidates = []
    if configured:
        candidates.append(configured)
    if route_file:
        candidates.append(
            os.path.abspath(
                os.path.join(os.path.dirname(route_file), "..", "..", "..", "E大", "网格3篇.md")
            )
        )
    candidates.append(os.path.abspath(os.path.join(os.getcwd(), "E大", "网格3篇.md")))
    return candidates


def resolve_eda_literature(
    environ: Optional[Mapping[str, str]] = None,
    route_file: Optional[str] = None,
) -> Optional[str]:
    """返回第一份存在的文献。都没有时返回 None。"""
    for path in eda_literature_candidates(environ, route_file):
        if path and os.path.exists(path):
            return path
    return None

"""按互斥小类选一只代表，并走既有适合度协议补日 K 与两格。不写个人档案。"""
from typing import Any, Callable, Dict, List

from repositories.etf_pool_repository import ETFPoolRepository
from services.analysis.grid_fit_service import GridFitBoardService


def run_subsector_seed(
    pool_repo: ETFPoolRepository,
    board: GridFitBoardService,
    sync_fn: Callable[[str], Any],
    backtest_fn: Callable[[str, str], Dict[str, Any]],
) -> Dict[str, int]:
    return board.run_representatives(
        pool_repo.list_subsector_members(),
        sync_fn,
        backtest_fn,
        pool_repo,
    )


def seed_universe(pool_repo: ETFPoolRepository) -> List[Dict[str, Any]]:
    pool_repo.mark_seed_representatives()
    return pool_repo.list_seeds()

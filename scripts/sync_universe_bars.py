#!/usr/bin/env python3
"""
做 T 成熟 ETF 日线时序同步与审计 CLI 工具

用法示例:
  # 1. 按全市场名单续传日 K。已有日 K 的代码不会重拉。
  python scripts/sync_universe_bars.py --full --workers 5

  # 2. 收盘后快速增量同步
  python scripts/sync_universe_bars.py --incremental

  # 3. 审计当前 MySQL 本地日 K 覆盖率与健康状态
  python scripts/sync_universe_bars.py --audit

  # 4. 指定单只标的强制重新全量补录
  python scripts/sync_universe_bars.py --code 510300 --force
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# 加入 backend 到 Python 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.data.universe_bar_sync_service import UniverseBarSyncService


def parse_args():
    parser = argparse.ArgumentParser(
        description="做 T 成熟 ETF 日 K 线本地库批量同步与审计工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="按全市场名单续传日 K，已有日 K 的代码跳过，结束后重建标的池",
    )
    mode_group.add_argument(
        "--universe",
        action="store_true",
        help="与 --full 相同：同步全市场名单，而不是只同步当前标的池",
    )
    mode_group.add_argument(
        "--incremental",
        action="store_true",
        help="收盘后轻量增量同步（拉取最近交易日 K 线）",
    )
    mode_group.add_argument(
        "--audit",
        action="store_true",
        help="审计当前数据库中标的的健康度与覆盖情况",
    )

    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="指定单个 ETF 代码执行同步或补录（如 510300）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="并发拉取线程数（默认: 5）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新拉取并覆盖已存在的数据（忽略跳过条件）",
    )

    return parser.parse_args()


def run_audit(service: UniverseBarSyncService, code: Optional[str] = None):
    print("\n🔍 正在审计本地库 (etf_daily_bar) 数据健康度...\n")
    if code:
        universe = [{"etf_code": code, "name": "指定标的", "sector": "-"}]
    else:
        universe = service.get_shoppable_universe()

    stat = service.audit_universe(universe)

    print(f"==================================================")
    print(f"📊 全市场选品宇宙池标的总数: {stat['total_universe']} 只")
    print(f"✅ 5 年日线完全覆盖 (>=1000条): {stat['full_covered']} 只")
    print(f"⚠️  部分历史覆盖 (0~1000条):  {stat['partially_covered']} 只")
    print(f"❌ 完全未覆盖 (0条):         {stat['uncovered']} 只")
    print(f"📦 数据库中日 K 线总行数:     {stat['total_bars_in_db']} 条")
    print(f"==================================================\n")

    # 展示前 10 个和后 10 个标的的覆盖明细
    sample_rows = stat["rows"][:8] + stat["rows"][-5:] if len(stat["rows"]) > 15 else stat["rows"]
    print(f"{'代码':<8} {'名称':<14} {'赛道':<10} {'日K行数':<8} {'最早日期':<12} {'最新日期':<12} {'健康状态'}")
    print("-" * 75)
    for r in sample_rows:
        print(f"{r['etf_code']:<8} {r['name'][:6]:<14} {r['sector'][:6]:<10} {r['bars_count']:<8} {r['min_date']:<12} {r['max_date']:<12} {r['health']}")
    if len(stat["rows"]) > 15:
        print(f"... 篇幅原因省略中间 {len(stat['rows']) - 13} 只标的 ...")
    print("-" * 75)


def run_sync(service: UniverseBarSyncService, args):
    if args.code:
        universe = [{"etf_code": args.code, "name": "指定标的", "sector": "-"}]
    else:
        universe = service.get_shoppable_universe()

    total = len(universe)
    if args.incremental:
        # 增量模式：拉取最近 15 天数据
        now = datetime.now()
        start_date = (now - timedelta(days=15)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
        mode_desc = f"每日增量更新模式 ({start_date} ~ {end_date})"
    else:
        start_date, end_date = service.get_default_5y_dates()
        mode_desc = f"5 年全量同步模式 ({start_date} ~ {end_date})"

    print("\n🚀 启动 ETF 日 K 线本地库沉淀任务")
    print(f"📌 同步模式: {mode_desc}")
    print(f"🎯 标的数量: {total} 只")
    print(f"⚡ 并发线程: {args.workers}")
    print(f"🔄 强制覆盖: {'是' if args.force else '否（启用断点续传）'}")
    print("=" * 60)

    start_time = time.time()

    def on_progress(res, current, total_count):
        status_tag = "✓ 已同步" if res["status"] == "synced" else ("⏭️  已跳过" if res["status"] == "skipped" else "❌ 失败")
        rows = res.get("rows_added", 0)
        err = f" ({res['error']})" if res.get("error") else ""
        percent = current * 100 // total_count
        print(f"[{current:3d}/{total_count:3d}] ({percent:2d}%) ETF {res['etf_code']} {status_tag} {rows} 行{err}")

    summary = service.sync_universe(
        instruments=universe,
        start_date=start_date,
        end_date=end_date,
        force_reload=args.force,
        is_incremental=args.incremental,
        workers=args.workers,
        progress_callback=on_progress,
    )

    cost_seconds = time.time() - start_time
    print("=" * 60)
    print(f"🎉 同步完成！总耗时: {cost_seconds:.2f} 秒")
    print(f"✅ 成功同步: {summary['synced']} 只")
    print(f"⏭️  断点跳过: {summary['skipped']} 只")
    print(f"❌ 失败标的: {summary['failed_count']} 只")
    if summary["failed_count"] > 0:
        print("失败标的详情:")
        for f in summary["failed_details"]:
            print(f"  - {f['etf_code']}: {f['error']}")
    print("=" * 60)


def main():
    args = parse_args()
    service = UniverseBarSyncService()

    if args.audit:
        run_audit(service, args.code)
    elif args.code or args.incremental:
        run_sync(service, args)
    elif args.full or args.universe:
        from services.data.startup_sync_service import StartupSyncService

        starter = StartupSyncService(sync_service=service)
        outcome = starter.run_full_universe_sync(workers=args.workers)
        done = outcome.get("done") or 0
        total = outcome.get("total") or 0
        print(f"全市场引导{outcome.get('status')}：{done}/{total}")
    else:
        # 默认执行审计或提示帮助
        print("未指定执行模式，默认展示当前审计状态。使用 --help 查看参数。")
        run_audit(service)


if __name__ == "__main__":
    main()

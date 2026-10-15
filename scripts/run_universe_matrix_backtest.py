#!/usr/bin/env python3
"""
做 T 成熟 ETF 多周期网格回测矩阵调度与赛道横评 CLI 工具

默认策略配置:
  - 初始资金: 30,000 元
  - 分析周期: 180 天历史 ATR 自适应步长
  - 做 T 收益留存机制: 利润池滚存留股 (E大 2.1)
  - 逢跌买入节奏: 倒金字塔加码 +10% (E大 2.2)
  - 基准锚点价格: 首日真实开盘价 (P0 杜绝未来函数)
  - 覆盖周期: 90天 / 180天 / 1年 / 2年 / 3年 / 5年
  - 次新 ETF: 上市未满周期严格留空 (None / -)

用法示例:
  python scripts/run_universe_matrix_backtest.py --workers 8 --export-csv data/universe_matrix.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# 添加 backend 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.analysis.universe_matrix_backtest_service import (
    PERIOD_SPECS,
    PRIMARY_SECTORS,
    UniverseMatrixBacktestService,
)
from repositories.universe_matrix_repository import UniverseMatrixRepository


def export_to_csv(results: List[Dict[str, Any]], filepath: str):
    """导出多周期矩阵大宽表至 CSV 文件"""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    headers = [
        "etf_code",
        "etf_name",
        "sector",
        "total_bars",
        # 90天
        "ret_90d",
        "mdd_90d",
        "trades_90d",
        "free_shares_90d",
        # 180天
        "ret_180d",
        "mdd_180d",
        "trades_180d",
        "free_shares_180d",
        # 1年
        "ret_1y",
        "mdd_1y",
        "trades_1y",
        "free_shares_1y",
        # 2年
        "ret_2y",
        "mdd_2y",
        "trades_2y",
        "free_shares_2y",
        # 3年
        "ret_3y",
        "mdd_3y",
        "trades_3y",
        "free_shares_3y",
        # 5年
        "ret_5y",
        "mdd_5y",
        "trades_5y",
        "free_shares_5y",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in results:
            p = item.get("periods") or {}

            def get_col(pk, attr):
                obj = p.get(pk) or {}
                val = obj.get(attr)
                return val if val is not None else ""

            row = [
                item.get("etf_code"),
                item.get("etf_name"),
                item.get("sector"),
                item.get("total_bars"),
                # 90d
                get_col("90d", "annual_return"),
                get_col("90d", "max_drawdown"),
                get_col("90d", "trade_count"),
                get_col("90d", "free_shares"),
                # 180d
                get_col("180d", "annual_return"),
                get_col("180d", "max_drawdown"),
                get_col("180d", "trade_count"),
                get_col("180d", "free_shares"),
                # 1y
                get_col("1y", "annual_return"),
                get_col("1y", "max_drawdown"),
                get_col("1y", "trade_count"),
                get_col("1y", "free_shares"),
                # 2y
                get_col("2y", "annual_return"),
                get_col("2y", "max_drawdown"),
                get_col("2y", "trade_count"),
                get_col("2y", "free_shares"),
                # 3y
                get_col("3y", "annual_return"),
                get_col("3y", "max_drawdown"),
                get_col("3y", "trade_count"),
                get_col("3y", "free_shares"),
                # 5y
                get_col("5y", "annual_return"),
                get_col("5y", "max_drawdown"),
                get_col("5y", "trade_count"),
                get_col("5y", "free_shares"),
            ]
            writer.writerow(row)


def print_top_ranking(results: List[Dict[str, Any]], top_n: int = 20):
    """打印全市场 Top 优选榜单"""
    print("\n" + "=" * 115)
    print(f"🏆 全市场做 T 成熟 ETF 多周期回测优选榜单 (Top {top_n})")
    print("配置: 本金 3w | 180d动态ATR | 模式B留股 | 倒金字塔加码+10% | 首日开盘价P0")
    print("=" * 115)
    header = f"{'排名':<4} {'代码':<7} {'标的简称':<12} {'所属赛道':<10} {'5年年化':<10} {'3年年化':<10} {'1年年化':<10} {'半年年化':<10} {'5年最大回撤':<12} {'5年留存股':<10}"
    print(header)
    print("-" * 115)

    rank = 1
    for item in results:
        p = item.get("periods") or {}
        p5 = p.get("5y") or {}
        p3 = p.get("3y") or {}
        p1 = p.get("1y") or {}
        p180 = p.get("180d") or {}

        # 优先展示有 5 年记录且年化为正的优秀标的
        ret5 = f"+{p5['annual_return']}%" if p5.get("annual_return") is not None else "-"
        ret3 = f"+{p3['annual_return']}%" if p3.get("annual_return") is not None else "-"
        ret1 = f"+{p1['annual_return']}%" if p1.get("annual_return") is not None else "-"
        ret180 = f"+{p180['annual_return']}%" if p180.get("annual_return") is not None else "-"
        mdd5 = f"-{p5['max_drawdown']}%" if p5.get("max_drawdown") is not None else "-"
        free5 = f"{p5['free_shares']}股" if p5.get("free_shares") is not None else "-"

        name = (item.get("etf_name") or "")[:8]
        sec = (item.get("sector") or "")[:6]

        print(f"{rank:<4} {item.get('etf_code'):<7} {name:<12} {sec:<10} {ret5:<10} {ret3:<10} {ret1:<10} {ret180:<10} {mdd5:<12} {free5:<10}")
        rank += 1
        if rank > top_n:
            break
    print("=" * 115)


def print_sector_rankings(sector_stats: List[Dict[str, Any]]):
    """打印首页 11 大赛道网格胜率与收益横评矩阵"""
    print("\n" + "=" * 115)
    print("📊 首页 11 大赛道做 T 网格胜率与综合收益横评矩阵 (按 5 年平均年化排序)")
    print("=" * 115)
    header = f"{'赛道名称':<10} {'标的数(5年有效)':<16} {'5年胜率':<10} {'5年均年化':<12} {'5年均回撤':<12} {'3年胜率':<10} {'赛道标杆 Top Pick':<26}"
    print(header)
    print("-" * 115)

    for s in sector_stats:
        sec_name = s.get("sector", "")
        tot = s.get("total_etfs", 0)
        s5 = s.get("stat_5y") or {}
        s3 = s.get("stat_3y") or {}
        tp = s.get("top_pick") or {}

        valid5_str = f"{tot}只 ({s5.get('valid_count', 0)}只)"
        win5 = f"{s5.get('win_rate')}%" if s5.get("win_rate") is not None else "-"
        ret5 = f"{s5.get('avg_annual_return')}%" if s5.get("avg_annual_return") is not None else "-"
        mdd5 = f"-{s5.get('avg_max_drawdown')}%" if s5.get("avg_max_drawdown") is not None else "-"
        win3 = f"{s3.get('win_rate')}%" if s3.get("win_rate") is not None else "-"

        tp_str = f"{tp.get('etf_code')} {tp.get('etf_name', '')[:6]} (+{tp.get('annual_return')}%)" if tp else "暂无"

        print(f"{sec_name:<10} {valid5_str:<16} {win5:<10} {ret5:<12} {mdd5:<12} {win3:<10} {tp_str:<26}")
    print("=" * 115)


def main():
    parser = argparse.ArgumentParser(description="成熟 ETF 多周期回测矩阵调度")
    parser.add_argument("--workers", type=int, default=8, help="并行工作线程数 (默认 8)")
    parser.add_argument("--export-csv", type=str, default="data/universe_matrix_backtest.csv", help="CSV 导出路径")
    parser.add_argument("--export-json", type=str, default="data/universe_matrix_backtest.json", help="JSON 导出路径")
    parser.add_argument("--top", type=int, default=20, help="终端打印前 N 名 (默认 20)")
    parser.add_argument("--code", type=str, default=None, help="仅回测指定单个 ETF 代码进行调试")

    args = parser.parse_args()

    service = UniverseMatrixBacktestService()

    if args.code:
        universe = [inst for inst in service.get_shoppable_universe() if inst["etf_code"] == args.code]
        if not universe:
            universe = [{"etf_code": args.code, "etf_name": "指定测试", "sector": "未入池"}]
    else:
        universe = service.get_shoppable_universe()

    total_count = len(universe)
    print("=" * 60)
    print("🚀 启动全市场 ETF 多周期网格回测矩阵调度")
    print(f"🎯 待回测标的: {total_count} 只")
    print(f"⏱️ 历史回测周期: 90天, 180天, 1年, 2年, 3年, 5年 (共 6 个维度)")
    print(f"⚡ 并发线程数: {args.workers}")
    print(f"💾 输出文件: {args.export_csv}")
    print("=" * 60)

    t0 = time.time()

    def on_progress(done, total, code):
        pct = int(done / total * 100)
        sys.stdout.write(f"\r[进度: {done:3d}/{total:3d} ({pct:3d}%)] 正在回测: {code} ...")
        sys.stdout.flush()

    results = service.run_universe_matrix(
        instruments=universe,
        total_capital=30000.0,
        scaling_ratio=0.10,
        reinvest_mode="pool_shares",
        step_mode="atr",
        workers=args.workers,
        progress_callback=on_progress,
    )

    elapsed = round(time.time() - t0, 2)
    print(f"\n\n🎉 矩阵回测全部完成！总耗时: {elapsed} 秒 (平均单只标的: {round(elapsed/max(1, total_count)*1000, 1)} ms)")

    # 导出文件
    export_to_csv(results, args.export_csv)
    print(f"✓ 已导出全量多周期矩阵 CSV: {args.export_csv}")

    sector_rankings = service.aggregate_sector_rankings(results)
    payload = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_etfs": len(results),
        "sectors": sector_rankings,
        "records": results,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.export_json)), exist_ok=True)
    with open(args.export_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✓ 已导出完整结果 JSON: {args.export_json}")

    # 同步批量沉淀至 MySQL 原生表 universe_matrix_backtest
    try:
        matrix_repo = UniverseMatrixRepository()
        saved_db = matrix_repo.batch_save(results)
        print(f"✓ 已全量原子沉淀至本地库 universe_matrix_backtest 表 ({saved_db} 行记录)")
    except Exception as db_err:
        print(f"⚠️ 沉淀至本地库 universe_matrix_backtest 失败: {db_err}")

    # 打印榜单与赛道横评
    print_top_ranking(results, top_n=args.top)
    print_sector_rankings(sector_rankings)


if __name__ == "__main__":
    main()

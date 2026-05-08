"""
Layer 1-3 基金分析管道：数据采集 → 多因子打分 → 决策输出
"""
import sys
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import akshare as ak

from src.db.storage import FundStorage

# Layer 1-3 委托给各模块
from src.analysis.scorer import FundAnalyzer
from src.output.report import generate_report


# ============================================================
# 主流程（兼容模式）
# ============================================================

def main():
    print("=" * 60)
    print("基金分析 Agent — Layer 1/2/3 管道启动")
    print("=" * 60)

    # 从数据库加载持仓
    store = FundStorage()
    holding_funds = store.list_holding_funds()

    if not holding_funds:
        print("[ERROR] 数据库中无持仓数据，请先运行:")
        print("  python -m src.cli init -o fund-portfolio.yaml  # 生成示例")
        print("  python -m src.cli import -c fund-portfolio.yaml  # 导入数据")
        print("  python -m src.cli analyze -c fund-portfolio.yaml  # 完整分析")
        return

    codes = [f["code"] for f in holding_funds]
    print(f"\n持仓基金 {len(codes)} 只: {codes}\n")

    # Layer 1: 数据采集
    print("[Layer 1] 开始数据采集...")
    analyzer = FundAnalyzer()
    for code in codes:
        try:
            analyzer.load_fund(code)
        except Exception as e:
            print(f"  [ERROR] {code} 数据采集失败: {e}")

    # Layer 2: 分析打分
    print(f"\n[Layer 2] 开始分析打分...")
    scores = []
    for code in codes:
        if code in analyzer.funds and analyzer.funds[code]["completeness"] != "D":
            s = analyzer.score_fund(code)
            scores.append(s)
            print(f"  {code} {s['fund_name']}: {s['composite_score']}/100 ({s['score_level_emoji']}) — {s['recommendation']}")
        else:
            print(f"  {code}: 数据不足，跳过评分")

    # 相关性矩阵
    print("\n  计算相关性矩阵...")
    correlations = analyzer.compute_correlations()
    if not correlations.empty:
        print("  相关性矩阵:")
        print(correlations.to_string())

    # 压力测试
    print("\n  计算压力测试...")
    stress_tests = analyzer.stress_test()

    # Layer 3: 生成报告
    print(f"\n[Layer 3] 生成诊断报告...")
    report = generate_report(analyzer, scores, correlations, stress_tests)

    # 输出到文件
    report_path = os.path.join(os.path.dirname(__file__), "..", "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  报告已保存至: {report_path}")

    # 保存到数据库
    print("\n  保存分析快照到数据库...")
    try:
        # 转换 scores 为存储格式
        score_data = []
        for s in scores:
            sc = {
                "fund_code": s["fund_code"],
                "data_completeness": s["data_completeness"],
                "composite_score": s["composite_score"],
                "score_level": s["score_level"],
                "macro_score": s["macro_score"],
                "macro_basis": s["macro_basis"],
                "macro_detail": s["macro_detail"],
                "meso_score": s["meso_score"],
                "meso_basis": s.get("meso_basis", ""),
                "meso_detail": s["meso_detail"],
                "micro_score": s["micro_score"],
                "micro_basis": s["micro_basis"],
                "micro_detail": s["micro_detail"],
                "recommendation": s["recommendation"],
                "stop_profit_pct": s["stop_profit_pct"],
                "stop_loss_pct": s["stop_loss_pct"],
                "action_logic": s["action_logic"],
                "key_metrics": f"波动率:{s.get('annual_volatility','N/A')}; 夏普:{s.get('sharpe_1y','N/A')}",
            }
            score_data.append(sc)

        # 转换 stress tests
        st_data = []
        for st in stress_tests:
            st_data.append({
                "scenario_id": st["scenario_id"],
                "scenario_desc": st["scenario_desc"],
                "fund_code": st["fund_code"],
                "estimated_drawdown_pct": st["estimated_drawdown_pct"],
            })

        # 转换 correlations
        corr_data = []
        if not correlations.empty:
            codes_list = list(correlations.columns)
            for i, c1 in enumerate(codes_list):
                for c2 in codes_list[i+1:]:
                    r = correlations.loc[c1, c2]
                    corr_data.append({
                        "fund_code_1": c1,
                        "fund_code_2": c2,
                        "pearson_r": round(float(r), 4),
                        "is_warning": abs(r) > 0.85,
                    })

        snapshot_id = store.save_analysis({
            "analysis_date": datetime.now(),
            "market_summary": "2026年5月: 美联储降息通道中但节奏放缓; A股沪深300 PE约12.5x处于历史40-50%分位; 国内经济缓复苏PMI约50.",
            "scores": score_data,
            "stress_tests": st_data,
            "correlations": corr_data,
        })
        print(f"  快照 ID: {snapshot_id}")

    except Exception as e:
        print(f"  [WARN] 数据库保存失败: {e}")
        import traceback
        traceback.print_exc()

    # 打印报告摘要
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()

"""报告后置校验器：止盈止损线自动校准 + 合规声明强制追加。"""
import re
from typing import Dict, List


COMPLIANCE_TEXT = """---

## 风险提示

- 本报告基于历史公共数据和统计模型自动生成，不构成任何形式的投资承诺或保证
- 历史业绩不代表未来表现，市场有风险，投资需谨慎
- 海外市场（QDII）基金额外面临汇率波动、交易时差和流动性风险
- 情景压力测试为理论假设模拟，实际市场可能出现超出假设范围的更极端波动
- 定投是长期策略，短期浮亏属正常现象，请确保有持续现金流支撑
- 投资者应结合自身风险承受能力、流动性需求和投资期限审慎决策"""


def post_process_report(raw_markdown: str, scores: List[Dict]) -> str:
    """后置处理 Markdown 报告：校正止盈止损线，追加合规声明。

    scores: List[Dict] — 每只基金的评分详情，含 fund_code, fund_name, annual_volatility。
    """
    result = raw_markdown

    # 1. 止盈止损线自动校准
    for s in scores:
        fund_name = s.get("fund_name", "")
        fund_code = s.get("fund_code", "")
        vol = s.get("annual_volatility", 20) or 20

        if not fund_name:
            continue

        # 公式：止盈 = vol * 2.0（上限 60%），止损 = vol * 1.5（上限 40%）
        stop_profit = min(60.0, max(15.0, vol * 2.0))
        stop_loss = min(40.0, max(10.0, vol * 1.5))

        escaped_name = re.escape(fund_name)
        escaped_code = re.escape(fund_code)

        # 在 ### 基金名称（代码）段落内匹配并替换止盈线
        pattern_profit = re.compile(
            rf'(###\s+{escaped_name}（{escaped_code}）\s*\n'
            rf'.*?)\|\s*\*\*止盈线\*\*\s*\|\s*\+[\d.]+%',
            re.DOTALL,
        )
        result = pattern_profit.sub(
            rf'\1| **止盈线** | +{stop_profit:.2f}%', result
        )

        # 替换止损线
        pattern_loss = re.compile(
            rf'(###\s+{escaped_name}（{escaped_code}）\s*\n'
            rf'.*?)\|\s*\*\*止损线\*\*\s*\|\s*[+-]?[\d.]+%',
            re.DOTALL,
        )
        result = pattern_loss.sub(
            rf'\1| **止损线** | -{stop_loss:.2f}%', result
        )

    # 2. 移除已有的风险提示（如有），追加标准合规声明
    existing_idx = result.rfind("## 风险提示")
    if existing_idx >= 0:
        # 截断到风险提示前，并清理末尾多余的 --- 分隔线
        prefix = result[:existing_idx].rstrip()
        if prefix.endswith("\n---"):
            prefix = prefix[:-4].rstrip()
        result = prefix

    result = result.rstrip() + "\n\n" + COMPLIANCE_TEXT + "\n"

    return result

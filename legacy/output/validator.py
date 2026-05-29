"""报告后置校验器：止盈止损线自动校准 + 合规声明强制追加。"""
from datetime import date
from html import escape
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
            rf'(###\s+{escaped_name}（{escaped_code}）.*?\n'
            rf'.*?)\|\s*\*\*止盈线\*\*\s*\|\s*\+[\d.]+%',
            re.DOTALL,
        )
        result = pattern_profit.sub(
            rf'\1| **止盈线** | +{stop_profit:.2f}%', result
        )

        # 替换止损线
        pattern_loss = re.compile(
            rf'(###\s+{escaped_name}（{escaped_code}）.*?\n'
            rf'.*?)\|\s*\*\*止损线\*\*\s*\|\s*[+-]?[\d.]+%',
            re.DOTALL,
        )
        result = pattern_loss.sub(
            rf'\1| **止损线** | -{stop_loss:.2f}%', result
        )
        result = _replace_html_stop_bounds(
            result,
            fund_name=fund_name,
            fund_code=fund_code,
            stop_profit=stop_profit,
            stop_loss=stop_loss,
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


def validate_final_report(markdown: str, report_date: str, holding_count: int) -> None:
    """Reject final reports that violate the Agent decision output contract."""
    forbidden_fragments = [
        "<!-- AGENT:",
        "AGENT_FILL",
        "尚未提供 agent",
        "趋势预测与操作矩阵",
        "操作触发条件",
        "本报告为证据稿",
        "待 Agent 最终评定",
    ]
    violations = [fragment for fragment in forbidden_fragments if fragment in markdown]
    if violations:
        raise ValueError(f"最终报告包含禁用的旧输出内容: {', '.join(violations)}")

    required_chapters = [
        "## 一、新闻资讯与 Agent 舆情研判",
        "## 二、持仓总览与当日归因分析",
        "## 三、定投执行与申购结算状态",
        "## 四、单基金深度诊断",
        "## 五、组合研判与执行方案",
        "## 六、组合风险、相关性与压力测试",
        "## 七、推荐候选与观察池",
    ]
    missing = [heading for heading in required_chapters if heading not in markdown]
    if missing:
        raise ValueError(f"最终报告缺少固定章节: {', '.join(missing)}")

    if "<details markdown=" in markdown:
        raise ValueError("最终报告应使用纯 HTML details 折叠块")

    details_count = markdown.count("<details>")
    if details_count != markdown.count("</details>"):
        raise ValueError("最终报告存在未闭合的 details 折叠块")

    cutoff = date.fromisoformat(report_date)
    news_segment = _section_between(markdown, "## 一、新闻资讯与 Agent 舆情研判", "## 二、持仓总览与当日归因分析")
    for value in re.findall(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", news_segment):
        if date.fromisoformat(value) > cutoff:
            raise ValueError(f"当日新闻线索包含了未来或非口径日的新闻: {value} > {report_date}")

    if holding_count > 0:
        settlement = _section_between(markdown, "### 申购与净值结算状态", "## ")
        row_count = 0
        for line in settlement.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if "基金 | 类型" in stripped or re.match(r"^\|[-:\s|]+\|$", stripped):
                continue
            row_count += 1
        if row_count < holding_count:
            raise ValueError(
                f"申购与净值结算状态未覆盖全部持仓: {row_count}/{holding_count}"
            )


def _section_between(markdown: str, heading: str, next_heading_prefix: str) -> str:
    start = markdown.find(heading)
    if start < 0:
        return ""
    search_from = start + len(heading)
    end = markdown.find(f"\n{next_heading_prefix}", search_from)
    return markdown[start:] if end < 0 else markdown[start:end]


def _replace_html_stop_bounds(
    markdown: str,
    fund_name: str,
    fund_code: str,
    stop_profit: float,
    stop_loss: float,
) -> str:
    """Calibrate stop bounds inside pure-HTML details blocks."""
    escaped_name = re.escape(escape(fund_name, quote=True))
    escaped_code = re.escape(escape(fund_code, quote=True))
    block_pattern = re.compile(
        rf'(<details>\s*<summary>{escaped_name}（{escaped_code}）.*?</summary>.*?</details>)',
        re.DOTALL,
    )

    def replace_block(match):
        block = match.group(1)
        block = re.sub(
            r'(<tr><td>止盈线</td><td>)\+?[+-]?[\d.]+%',
            rf'\1+{stop_profit:.2f}%',
            block,
        )
        block = re.sub(
            r'(<tr><td>止损线</td><td>)[+-]?[\d.]+%',
            rf'\1-{stop_loss:.2f}%',
            block,
        )
        return block

    return block_pattern.sub(replace_block, markdown)

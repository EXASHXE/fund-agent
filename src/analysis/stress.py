"""压力风险线索生成。

脚本不再输出固定四情景作为最终压力测试结论，而是根据基金名称、类型、
行业和重仓生成风险候选。最终情景、冲击幅度和组合影响应由接入 skill
的 agent 结合当前市场局势自主判断。
"""
from typing import Dict, List


def stress_test(funds_data: Dict) -> List[Dict]:
    """按当前持仓暴露生成压力测试候选。"""
    results = []
    for code, fund in funds_data.items():
        basic = fund.get("basic", {}) or {}
        name = basic.get("name", "")
        ftype = basic.get("fund_type", "")
        exposure_text = _fund_exposure_text(fund)
        for scenario in _infer_risk_scenarios(name, ftype, exposure_text):
            results.append({
                "scenario_id": scenario["id"],
                "scenario_desc": scenario["desc"],
                "fund_code": code,
                "fund_name": name,
                "estimated_drawdown_pct": scenario["seed_drawdown"],
                "risk_driver": scenario["driver"],
                "agent_review_required": True,
                "agent_instruction": (
                    "这是基于持仓暴露生成的压力测试初稿。请结合最新宏观、行业、"
                    "新闻和组合仓位，自主调整冲击假设与影响金额。"
                ),
            })
    return results


def _fund_exposure_text(fund: Dict) -> str:
    parts = []
    for key in ["basic"]:
        value = fund.get(key, {})
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    for key in ["holdings", "sectors"]:
        df = fund.get(key)
        if df is not None and hasattr(df, "head") and not getattr(df, "empty", True):
            try:
                parts.append(" ".join(str(x) for x in df.head(10).astype(str).values.flatten()))
            except Exception:
                pass
    return " ".join(parts)


def _infer_risk_scenarios(name: str, ftype: str, exposure_text: str) -> List[Dict]:
    text = f"{name} {ftype} {exposure_text}"
    scenarios = []
    rules = [
        ("R_SEMI", ["半导体", "芯片", "寒武纪", "精测电子", "集成电路"], "国内半导体景气/估值回撤", "半导体需求不及预期、出口管制或估值收缩", -10.0),
        ("R_AI", ["AI", "人工智能", "算力", "服务器", "光模块"], "AI算力链交易拥挤", "业绩兑现低于高预期或资金从AI链撤出", -9.0),
        ("R_EV", ["新能源", "电池", "锂电", "光伏", "储能", "电动车"], "新能源供需和价格压力", "产能过剩、价格战或政策补贴边际变化", -8.0),
        ("R_QDII", ["QDII", "纳斯达克", "标普", "美元", "美股"], "海外权益与汇率共振", "美股估值回撤、美元/人民币波动或海外流动性收紧", -7.0),
        ("R_RATE", ["债", "固收", "利率", "信用"], "利率和信用利差冲击", "利率上行、信用利差扩大或赎回压力", -3.0),
        ("R_COMMODITY", ["石油", "原油", "黄金", "商品", "能源"], "商品价格大幅波动", "供需预期逆转或地缘事件降温", -8.0),
        ("R_CONSUMER", ["消费", "白酒", "食品", "医药", "医疗"], "内需和政策预期变化", "消费复苏弱于预期、集采/监管或盈利下修", -6.0),
    ]
    for sid, keywords, desc, driver, seed in rules:
        if any(kw in text for kw in keywords):
            scenarios.append({
                "id": sid,
                "desc": desc,
                "driver": driver,
                "seed_drawdown": seed,
            })
    if not scenarios:
        scenarios.append({
            "id": "R_MARKET",
            "desc": "权益市场系统性波动",
            "driver": "风险偏好下降、资金面收紧或指数回撤",
            "seed_drawdown": -6.0,
        })
    return scenarios

#!/usr/bin/env python3.12
"""
Daily fund report via Feishu interactive message cards (Approach C).

Usage:
    cd /root/workspace/projects/fund-agent && python3.12 scripts/daily_report_card.py

Flow:
    1. Runs `analyze -c fund-portfolio.yaml -o report.md`
    2. Parses report.md: portfolio, funds, scores, sentiment per fund, news headlines, recs
    3. Builds 4-5 Feishu message cards with column_set layouts
    4. Sends via Feishu interactive message API

Card structure:
    C1: Portfolio overview — KPI columns + per-fund rows (score/value/profit/annual_ret/pending/dca)
    C2: Trading day focus (QDII & DCA) or non-trading day review (week profit / rebalance)
    C3: News sentiment — per-fund values + recent headlines (supports [-+○] prefixes)
    C5: Recommendations — ranked picks with reasons (9-column table)

Key design decisions:
    - Use column_set + lark_md (NOT pipe tables) for mobile readability
    - Sentiment parsed from ## 新闻资讯分析 section, split by #### blocks
    - News headlines from **近期新闻精选：** under each fund block
    - Sentiment mood derived from value (no 综合判断 field in new report format)
"""

import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

PROJECT_DIR = Path("/root/workspace/projects/fund-agent")
REPORT_PATH = PROJECT_DIR / "report.md"
ENV_PATH = Path("/root/.hermes/.env")

APP_ID = "cli_aa8a6d243df8dcb2"
APP_SECRET = "MIKz5ZURJThmvCLfmGxxsd1ZBwvCBH8h"
HOME_CHANNEL = "oc_76abb4b61114d408b94248bd4d9e646a"
API_BASE = "https://open.feishu.cn/open-apis"


def get_token():
    data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
    req = urllib.request.Request(f"{API_BASE}/auth/v3/tenant_access_token/internal", data=data,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]


def send_card(card_json, token):
    content = json.dumps(card_json, ensure_ascii=False)
    body = json.dumps({"receive_id": HOME_CHANNEL, "msg_type": "interactive", "content": content},
                       ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    )
    return json.loads(urllib.request.urlopen(req).read())


def P(t): return {"tag": "plain_text", "content": t}
def D(t): return {"tag": "div", "text": {"tag": "lark_md", "content": t}}
def H(): return {"tag": "hr"}
def N(t): return {"tag": "note", "elements": [{"tag": "plain_text", "content": t}]}

def CS(cols, flex="bisect"):
    return {"tag": "column_set", "flex_mode": flex, "background_style": "default", "columns": cols}

def C(ems):
    if isinstance(ems, str): ems = [ems]
    return {"tag": "column", "width": "weighted", "weight": 1,
            "elements": [D(e) if isinstance(e, str) else e for e in ems]}

def HD(title, tmpl="blue"):
    return {"config": {"wide_screen_mode": True}, "header": {"title": P(title), "template": tmpl}}


def run_analyze():
    """Run the fund-agent analyze command."""
    print("[fund-report] Running analyze...", file=sys.stderr)
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    env["PYTHONUNBUFFERED"] = "1"

    result = subprocess.run(
        ["python3.12", "-m", "src.cli", "analyze", "-c", "fund-portfolio.yaml", "-o", str(REPORT_PATH)],
        cwd=str(PROJECT_DIR), env={**dict(os.environ), **env},
        capture_output=True, text=True, timeout=600
    )
    for line in result.stderr.splitlines():
        if line.strip(): print(f"  {line}", file=sys.stderr)
    for line in result.stdout.splitlines():
        if line.strip(): print(f"  {line}", file=sys.stderr)
    if result.returncode != 0:
        print(f"[ERROR] analyze failed (rc={result.returncode})", file=sys.stderr)
        return False
    print("[fund-report] analyze done.", file=sys.stderr)
    return True


def parse_report():
    """Parse report.md into structured dict."""
    txt = REPORT_PATH.read_text("utf-8")
    data = {}

    def g(p):
        m = re.search(p, txt)
        return m.group(1) if m else "?"

    # ── Portfolio summary KPIs ──
    data["tv"] = g(r"总市值[：：]¥?([\d,]+\.?\d*)")
    data["tp"] = g(r"总收益[：：]¥?\+?(-?[\d,]+\.?\d*)")
    data["tr"] = g(r"总收益率[：：]\+?(-?[\d.]+%)")
    data["pend"] = g(r"待确认金额[：：]¥?([\d,]+\.?\d*)")
    data["fc"] = g(r"持有基金数[：：](\d+)")
    data["tp_cost"] = g(r"总投入[：：]¥?([\d,]+\.?\d*)")
    data["sent"] = g(r"整体情绪均值\*\*[：：]([\d.]+)")

    # sent_mood: derived from sentiment value (no 综合判断 field in new report)
    if data["sent"] != "?":
        sv = float(data["sent"])
        data["sent_mood"] = "偏正面" if sv > 0.55 else "偏谨慎" if sv < 0.45 else "中性"
    else:
        data["sent_mood"] = ""

    # Dates
    m = re.search(r"运行日期[：：]([\d-]+)", txt)
    data["run_date"] = m.group(1) if m else "?"
    m = re.search(r"报告口径日[：：]([\d-]+)", txt)
    data["report_date"] = m.group(1) if m else "?"

    # ── Per-fund data from holdings table (new format: 10 columns) ──
    # | 基金代码 | 基金名称 | 持有市值(¥) | 占比 | 成本价 | 累计收益(¥) | 累计收益率 | 年化收益率 | 待确认(¥) | 定投状态 |
    pat = re.compile(
        r"\| (\w{6}) \| ([^|]+?) \| ([\d,.]+?) \| ([\d.]+%) \| [\d.]+ \|"
        r" ([+-][\d,.]+?) \| ([+-][\d.]+%) \| ([+-]?[\d.]+%|-|\?) \| ([\d,.]+) \| ([^|]+?) \|"
    )
    funds = []
    for m in pat.finditer(txt):
        funds.append({
            "code": m.group(1),
            "name": m.group(2).strip(),
            "value": float(m.group(3).replace(",", "")),
            "pct": m.group(4),
            "profit": m.group(5),
            "ret": m.group(6),
            "annual_ret": m.group(7).strip() if m.group(7) else "?",
            "pending": m.group(8).replace(",", "") if m.group(8) else "0",
            "dca_status": m.group(9).strip() if m.group(9) else "未设置",
        })
    data["funds"] = funds

    # ── Scores: "**综合评分**：62/100（🟡）" ──
    scores = re.findall(r"\*\*综合评分\*\*[：：](\d+)/100", txt)
    codes = re.findall(r"###\s*.+?[（(](\w{6})[)）]", txt)
    sc_map = {}
    for i, sv in enumerate(scores):
        if i < len(codes):
            sc_map[codes[i]] = sv
    data["scores"] = sc_map

    # ── Trade day detection ──
    data["trade_day"] = bool(re.search(r"交易相关跟踪|交易日跟踪重点", txt))

    # ── Recommendations (9-column table) ──
    # | # | 代码 | 名称 | 主题 | 综合分 | 近1月 | 持仓相似度 | 分散度 | 推荐理由 |
    recs = []
    pr = re.compile(
        r"\|\s*\d+\s*\|\s*(\w{6})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*[\d.]+\s*\|\s*[^|]+\s*\|\s*[\d.]+\s*\|\s*[\d.]+\s*\|\s*([^|]+?)\s*\|"
    )
    for m in pr.finditer(txt):
        reason = m.group(4).strip()
        if len(reason) > 10:
            recs.append({
                "code": m.group(1),
                "name": m.group(2).strip(),
                "type": m.group(3).strip(),
                "reason": reason[:60]
            })
    data["recs"] = recs[:5]

    # ── Sentiment + news detail from news section ──
    sent_map = {}
    news_detail = {}
    news_start = txt.find("## 新闻资讯分析")
    if news_start >= 0:
        news_sec = txt[news_start:]
        blocks = re.split(r'(?=#### )', news_sec)
        for blk in blocks:
            if not blk.strip():
                continue
            m = re.search(r'[（(](\w{6})[)）]', blk)
            if not m:
                continue
            code = m.group(1)
            # Sentiment value: "| 情绪均值 | X.XX |"
            m2 = re.search(r'\| 情绪均值 \| ([\d.]+) \|', blk)
            if m2:
                sent_map[code] = m2.group(1)
            # News headlines from "**近期新闻精选：**" — support [-+○] prefixes
            headlines = []
            for hl in re.findall(r'[-+○]\s*\[?[^\]]*\]?\s*(.{0,80})', blk):
                hl = hl.strip()
                if hl and hl != "":
                    headlines.append(hl)
            if headlines:
                news_detail[code] = headlines[:3]
    data["sent_map"] = sent_map
    data["news_detail"] = news_detail

    # ── Non-trade day: week profit ──
    week_profit = []
    idx = txt.find("本周收益")
    if idx >= 0:
        sect = txt[idx:idx+800]
        for line in sect.split("\n"):
            m = re.match(r"\| (\w{6}) \| (.+?) \| ([+-][\d,.]+) \| ([+-][\d.]+%) \| ([\d.]+%) \|", line)
            if m:
                week_profit.append({
                    "code": m.group(1),
                    "name": m.group(2).strip(),
                    "profit": m.group(3),
                    "contrib": m.group(4),
                })
    data["week_profit"] = week_profit

    # Non-trade day: rebalance text (now AGENT placeholder, fallback to empty)
    rebalance = []
    idx = txt.find("风险暴露与再平衡")
    if idx >= 0:
        sect = txt[idx:idx+600]
        for m in re.finditer(r"- (.+)", sect):
            item = m.group(1).strip()
            # Skip AGENT placeholder HTML comments
            if item and not item.startswith("<!--"):
                rebalance.append(item)
    data["rebalance"] = rebalance

    return data


def IND(sc):
    si = int(sc) if sc != "?" else 0
    return "🟢" if si >= 70 else "🟡" if si >= 60 else "🟠" if si >= 45 else "🔴"

def PF(p):
    v = float(p.replace("+", "").replace(",", ""))
    return f"+¥{v:,.0f}" if v >= 0 else f"-¥{abs(v):,.0f}"

def SENT_ARROW(v):
    fv = float(v)
    if fv > 0.55: return "🔺"
    if fv < 0.45: return "🔻"
    return "➖"

def DCA_STATUS_ICON(status):
    s = status.strip()
    if s in ("启用中", "进行中"): return "✅"
    if s == "未设置": return "⚪"
    return "⏳"


def build_cards(data):
    """Build approach C cards: C1 overview, C2 trade/non-trade, C3 sentiment, C5 recs."""
    cards = []
    txt = REPORT_PATH.read_text("utf-8")

    # C2 per-fund name truncation for card display
    FUND_NAME_LEN = 14  # shows "华宝致远混合(QDII)A" fully, others get close

    # ══ C1: Portfolio Overview ══
    tp_cost_v = data["tp_cost"] if data["tp_cost"] != "?" else "—"
    els = [
        D(f"**运行**: {data['run_date']}  |  **口径日**: {data['report_date']}"),
        H(),
        CS([
            C([f"**总市值** ¥{data['tv']}"]),
            C([f"**总收益** **¥{data['tp']}**\\n{data['tr']}"]),
            C([f"**总投入** ¥{tp_cost_v}"]),
            C([f"**待确认** ¥{data['pend']}"]),
        ]),
        H(),
        D("**📋 持仓明细**"),
    ]
    for f in data["funds"]:
        sc = data["scores"].get(f["code"], "?")
        pending_v = f["pending"]
        dca_icon = DCA_STATUS_ICON(f["dca_status"])
        name_short = f['name'][:FUND_NAME_LEN]
        # Column 1: score + fund info
        left = f"{IND(sc)} **{name_short}** {f['code']}  {sc}/100"
        # Column 2: value/profit/annual_ret/pending
        right = f"¥{f['value']:,.0f} {PF(f['profit'])}\\n年化 {f['annual_ret']}  待确认¥{pending_v}  {dca_icon}"
        els.append(CS([
            C([left]),
            C([right]),
        ]))
    els.append(H())
    els.append(N("📌 基于历史数据和统计模型，不构成投资建议。"))
    c = HD("📊 基金组合日报 · 持仓总览", "blue"); c["elements"] = els; cards.append(c)

    # ══ C2: Trade day or Non-trade day ══
    els2 = []
    if data["trade_day"]:
        # QDII rows — new format: | 基金代码 | 基金名称 | 净值日期 | 当前净值 | 真实份额 | 流水模拟份额 | 待确认(¥) | 状态 |
        qdii_items = []
        for m in re.finditer(
            r"\| (\w{6}) \| ([^|]+?) \| ([\d-]+) \| ([\d.]+) \| [\d,.]+ \| [\d,.]+ \| ([\d,.]+) \| (\S+)",
            txt
        ):
            amt = m.group(5).replace(",", "")
            icon = "⏳" if amt not in ("0", "0.00") else "✅"
            qdii_name = m.group(2).strip()[:FUND_NAME_LEN]
            qdii_items.append(C([
                f"**{m.group(1)} {qdii_name}**\\n净值 {m.group(4)} ({m.group(3)})\\n待确认 ¥{amt}  {icon}"
            ]))
        if qdii_items:
            els2.append(D("**QDII 结算状态**"))
            for i in range(0, len(qdii_items), 2):
                els2.append(CS(qdii_items[i:i+2]))
            els2.append(H())

        # DCA rows — new format with more columns
        dca_items = []
        for m in re.finditer(
            r"\| (\w{6}) \| ([^|]+?) \| (\w+) \| ([\d,.]+) \| ([\d-]+) \| (\w+)",
            txt
        ):
            status = m.group(6).strip()
            # Show all scheduled DCA items regardless of status
            scheduled_date = m.group(5)
            dca_items.append(f"• **{m.group(1)}** ({m.group(3)}) ¥{m.group(4)} — {scheduled_date} {status}")
        if dca_items:
            els2.append(D("**定投执行预估**\\n" + "\\n".join(dca_items)))
        else:
            els2.append(D("**定投执行预估**\\n今日无定投。"))
    else:
        els2.append(D(f"📆 **非交易日组合复盘**\\n截至 {data['report_date']}（最近交易日）"))
        els2.append(H())
        if data["week_profit"]:
            els2.append(D("**本周收益与基金贡献**"))
            for w in data["week_profit"]:
                els2.append(CS([
                    C([f"**{w['name'][:FUND_NAME_LEN]}** {w['code']}"]),
                    C([f"{w['profit']}  贡献 {w['contrib']}"]),
                ]))
        if data["rebalance"]:
            els2.append(H())
            els2.append(D("**风险暴露与再平衡**\\n" + "\\n".join(f"• {l}" for l in data["rebalance"])))
        els2.append(H())
        els2.append(D("**定投质量**\\n• 非交易日无净值更新，定投按计划执行"))

    c = HD("📋 " + ("QDII & 定投" if data["trade_day"] else "组合复盘"), "indigo")
    c["elements"] = els2; cards.append(c)

    # ══ C3: News Sentiment + detail ══
    sent_lines = []
    for f in data["funds"]:
        code = f["code"]
        sv = data["sent_map"].get(code)
        n_short = f['name'][:FUND_NAME_LEN]
        if sv:
            sent_lines.append(f"• {n_short}（{code}） **{sv}** {SENT_ARROW(sv)}")
        else:
            sent_lines.append(f"• {n_short}（{code}） ?")

    news_lines = []
    for f in data["funds"]:
        code = f["code"]
        hls = data["news_detail"].get(code, [])
        n_short = f['name'][:FUND_NAME_LEN]
        if hls:
            news_lines.append(f"\\n**{n_short}**（{code}）")
            for hl in hls:
                news_lines.append(f"• {hl}")

    els3 = [
        D(f"**市场情绪总览**\\n整体情绪均值 **{data['sent']}** | {data['sent_mood']}"),
        H(),
        D("**逐基金情绪**\\n" + "\\n".join(sent_lines)),
    ]
    if news_lines:
        els3.append(H())
        els3.append(D("**近期新闻精选**\\n" + "\\n".join(news_lines)))
    els3.append(H())
    els3.append(N("📰 新闻基于最近7天相关资讯分析。"))
    c = HD("📰 新闻情绪", "green"); c["elements"] = els3; cards.append(c)

    # ══ C5: Recommendations ══
    if data["recs"]:
        parts = ["**基于动量和相关性筛选**\\n"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(data["recs"]):
            parts.append(f"{medals[i]} **{r['name']}** ({r['code']})")
            parts.append(f"   类型: {r['type']}  |  {r['reason'][:60]}")
            parts.append("")
        els5 = [D("\\n".join(parts)), H(), N("推荐仅供参考，请结合自身风险偏好决策。")]
        c = HD("🏆 推荐基金", "orange"); c["elements"] = els5; cards.append(c)

    return cards


if __name__ == "__main__":
    if not run_analyze():
        ec = HD("❌ 基金报告生成失败", "red")
        ec["elements"] = [D("analyze 命令执行失败，请检查日志。")]
        send_card(ec, get_token())
        sys.exit(1)

    data = parse_report()
    token = get_token()
    for i, card in enumerate(build_cards(data)):
        resp = send_card(card, token)
        code = resp.get("code", "?")
        if code != 0:
            print(f"[ERROR] C-{i+1}: {code} {resp.get('msg','')}", file=sys.stderr)
        time.sleep(1.5)
    print("[fund-report] Done.", file=sys.stderr)

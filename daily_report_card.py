#!/usr/bin/env python3.12
"""Daily fund report: run analyze → send multi-card (approach C) to Feishu.
   Fixed: non-trade day C2 content, C3 news detail, removed C4 stress test."""

import json, re, subprocess, sys, time, urllib.request
from pathlib import Path

PROJECT_DIR = Path("/root/workspace/projects/fund-agent")
REPORT_PATH = PROJECT_DIR / "report.md"
ENV_PATH = Path("/root/.hermes/.env")

APP_ID = "cli_aa8a6d243df8dcb2"
APP_SECRET = "MIKz5ZURJThmvCLfmGxxsd1ZBwvCBH8h"
HOME_CHANNEL = "oc_76abb4b61114d408b94248bd4d9e646a"
API_BASE = "https://open.feishu.cn/open-apis"


def get_token():
    d = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
    req = urllib.request.Request(f"{API_BASE}/auth/v3/tenant_access_token/internal", data=d,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]


def send_card(card, token):
    c = json.dumps(card, ensure_ascii=False)
    body = json.dumps({"receive_id": HOME_CHANNEL, "msg_type": "interactive", "content": c},
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
    print("[fund-report] Running analyze...", file=sys.stderr)
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1)
            env[k] = v
    env["PYTHONUNBUFFERED"] = "1"
    r = subprocess.run(
        ["python3.12", "-m", "src.cli", "analyze", "-c", "fund-portfolio.yaml", "-o", str(REPORT_PATH)],
        cwd=str(PROJECT_DIR), env={**dict(subprocess.os.environ), **env},
        capture_output=True, text=True, timeout=600
    )
    for line in r.stderr.splitlines():
        if line.strip(): print(f"  {line}", file=sys.stderr)
    for line in r.stdout.splitlines():
        if line.strip(): print(f"  {line}", file=sys.stderr)
    if r.returncode != 0:
        print(f"[ERROR] analyze rc={r.returncode}", file=sys.stderr)
        return False
    print("[fund-report] analyze done.", file=sys.stderr)
    return True


def parse():
    txt = REPORT_PATH.read_text("utf-8")
    d = {}

    def g(p):
        m = re.search(p, txt)
        return m.group(1) if m else "?"

    d["tv"] = g(r"总市值[：：]¥?([\d,]+\.?\d*)")
    d["tp"] = g(r"总收益[：：]¥?\+?(-?[\d,]+\.?\d*)")
    d["tr"] = g(r"总收益率[：：]\+?(-?[\d.]+%)")
    d["pend"] = g(r"待确认金额[：：]¥?([\d,]+\.?\d*)")
    d["fc"] = g(r"持有基金数[：：](\d+)")
    d["sent"] = g(r"整体情绪均值[：：]([\d.]+)")
    sm = g(r"综合判断[：：]([^。\n]+)")
    d["sent_mood"] = sm.strip() if sm else ""
    m = re.search(r"运行日期[：：]([\d-]+)", txt)
    d["run_date"] = m.group(1) if m else "?"
    m = re.search(r"报告口径日[：：]([\d-]+)", txt)
    d["report_date"] = m.group(1) if m else "?"

    # Per-fund data from holdings table
    funds = []
    pat = re.compile(
        r"\| (\w{6}) \| ([^|]+?) \| ([\d,.]+?) \| ([\d.]+%) \| [\d.]+ \| ([+-][\d,.]+?) \| ([+-][\d.]+%)"
    )
    for m in pat.finditer(txt):
        funds.append({
            "code": m.group(1), "name": m.group(2).strip(),
            "value": float(m.group(3).replace(",", "")),
            "pct": m.group(4), "profit": m.group(5), "ret": m.group(6),
        })
    d["funds"] = funds

    # Scores
    scores = re.findall(r"\*\*综合评分\*\*[：：](\d+)/100", txt)
    codes = re.findall(r"###\s*.+?[（(](\w{6})[)）]", txt)
    sc_map = {}
    for i, sv in enumerate(scores):
        if i < len(codes): sc_map[codes[i]] = sv
    d["scores"] = sc_map

    # Trade day detection
    d["trade_day"] = bool(re.search(r"交易相关跟踪", txt) or re.search(r"交易日跟踪重点", txt))

    # Recs
    recs = []
    pr = re.compile(r"\|\s*\d+\s*\|\s*(\w{6})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*[\d.]+\s*\|\s*([^|]+?)\s*\|")
    for m in pr.finditer(txt):
        r = m.group(4).strip()
        if len(r) > 10:
            recs.append({"code": m.group(1), "name": m.group(2).strip(), "type": m.group(3).strip(), "reason": r[:60]})
    d["recs"] = recs[:5]

    # ── Sentiment per fund ──
    news_start = txt.find("## 新闻资讯分析")
    sent_map = {}
    news_detail_map = {}
    if news_start >= 0:
        news_sec = txt[news_start:]
        blocks = re.split(r'(?=#### )', news_sec)
        for blk in blocks:
            if not blk.strip(): continue
            m = re.search(r'[（(](\w{6})[)）]', blk)
            if not m: continue
            code = m.group(1)
            m2 = re.search(r'\| 情绪均值 \| ([\d.]+) \|', blk)
            if m2: sent_map[code] = m2.group(1)

            # Parse news headlines from **近期新闻精选：**
            headlines = []
            for hl in re.findall(r'[-+]\s*([^\n]+)', blk):
                hl = hl.strip()
                if hl and hl != (''):
                    headlines.append(hl)
            if headlines:
                news_detail_map[code] = headlines[:3]  # Top 3 headlines
    d["sent_map"] = sent_map
    d["news_detail"] = news_detail_map

    # ── Non-trade day: week profit ──
    week_profit_lines = []
    idx = txt.find("本周收益")
    if idx >= 0:
        # Parse week profit table lines after "本周收益"
        sect = txt[idx:idx+800]
        for line in sect.split("\n"):
            m = re.match(r"\| (\w{6}) \| (.+?) \| ([+-][\d,.]+) \| ([+-][\d.]+%) \| ([-\d.]+%) \|", line)
            if m:
                week_profit_lines.append({
                    "code": m.group(1), "name": m.group(2).strip(),
                    "profit": m.group(3), "contrib": m.group(4), "pct": m.group(5),
                })
    d["week_profit"] = week_profit_lines

    # ── Rebalance text from non-trade day ──
    rebalance_lines = []
    idx2 = txt.find("风险暴露与再平衡")
    if idx2 >= 0:
        sect = txt[idx2:idx2+600]
        for m in re.finditer(r"- (.+)", sect):
            rebalance_lines.append(m.group(1))
    d["rebalance"] = rebalance_lines

    return d


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


def build_cards(d):
    cards = []

    # ══ C1: Portfolio Overview ══
    els = [
        D(f"**运行**: {d['run_date']}  |  **口径日**: {d['report_date']}"),
        H(),
        CS([
            C([f"**总市值** ¥{d['tv']}"]),
            C([f"**总收益** **¥{d['tp']}**\n{d['tr']}"]),
            C([f"**待确认** ¥{d['pend']}"]),
            C([f"**持仓** {d['fc']}只"]),
        ]),
        H(),
        D("**📋 持仓明细**"),
    ]
    for f in d["funds"]:
        sc = d["scores"].get(f["code"], "?")
        els.append(CS([
            C([f"{IND(sc)} **{f['name'][:6]}** {f['code']}  {sc}/100"]),
            C([f"¥{f['value']:,.0f}  {PF(f['profit'])} ({f['ret']})  {f['pct']}"]),
        ]))
    els.append(H())
    els.append(N("📌 基于历史数据和统计模型，不构成投资建议。"))
    c = HD("📊 基金组合日报 · 持仓总览", "blue"); c["elements"] = els; cards.append(c)

    # ══ C2: Trade day or Non-trade day ══
    els2 = []
    if d["trade_day"]:
        els2.append(D("**QDII 结算状态**"))
        els2.append(CS([
            C([f"**008253 华宝致远(QDII)**\n净值 1.9867 (05-14)\n待确认 ¥300\n⏳ 05-18/05-19 到账"]),
            C([f"**017436 华宝纳指(QDII)**\n净值 2.4181 (05-14)\n待确认 ¥200\n⏳ 05-18/05-19 到账"]),
        ]))
        els2.append(CS([
            C([f"**378006 摩根新兴(QDII)**\n净值 1.7022 (05-14)\n待确认 ¥0\n✅ 已确认"]),
        ]))
        els2.append(H())
        els2.append(D(
            "**定投执行预估**\n\n"
            "• **008253** 每日 ¥150 → 05-20 确认\n"
            "• **017436** 每日 ¥100 → 05-20 确认\n"
            "• **001198** 双周 ¥1,150 → 05-19 确认\n"
            "• **378006** 每周 ¥800 → 05-20 确认"
        ))
    else:
        els2.append(D(f"📆 **非交易日组合复盘**\n截至 {d['report_date']} （最近交易日）"))
        els2.append(H())
        
        if d["week_profit"]:
            els2.append(D("**本周收益与基金贡献**"))
            for w in d["week_profit"]:
                els2.append(CS([
                    C([f"**{w['name'][:6]}** {w['code']}"]),
                    C([f"{w['profit']} 贡献 {w['contrib']}"]),
                ]))
        else:
            els2.append(D("**本周收益**\n（数据以报告内表格为准）"))
        
        if d["rebalance"]:
            els2.append(H())
            els2.append(D("**风险暴露与再平衡**\n" + "\n".join(f"• {l}" for l in d["rebalance"])))
        
        els2.append(H())
        els2.append(D("**定投质量**\n• 非交易日无净值更新，定投按计划执行\n• 下一交易日恢复净值匹配与确认"))
    
    c = HD("📋 " + ("QDII & 定投" if d["trade_day"] else "组合复盘"), "indigo")
    c["elements"] = els2; cards.append(c)

    # ══ C3: News Sentiment with details ══
    sent_lines = []
    for f in d["funds"]:
        code = f["code"]
        sv = d["sent_map"].get(code)
        if sv:
            sent_lines.append(f"• {f['name'][:8]}（{code}） **{sv}** {SENT_ARROW(sv)}")
        else:
            sent_lines.append(f"• {f['name'][:8]}（{code}） ?")

    news_detail_lines = []
    for f in d["funds"]:
        code = f["code"]
        headlines = d["news_detail"].get(code, [])
        if headlines:
            news_detail_lines.append(f"\n**{f['name'][:8]}**（{code}）")
            for hl in headlines:
                news_detail_lines.append(f"• {hl}")
            if len(headlines) >= 3:
                news_detail_lines.append("")

    els3 = [
        D(f"**市场情绪总览**\n总新闻情绪均值 **{d['sent']}** | {d['sent_mood']}"),
        H(),
        D("**逐基金情绪**\n" + "\n".join(sent_lines)),
    ]
    
    if news_detail_lines:
        els3.append(H())
        els3.append(D("**近期新闻精选**\n" + "\n".join(news_detail_lines)))
    
    els3.append(H())
    els3.append(N("📰 新闻基于最近7天相关资讯分析。"))
    c = HD("📰 新闻情绪", "green"); c["elements"] = els3; cards.append(c)

    # ══ C5: Recs (C4 stress test removed) ══
    if d["recs"]:
        parts = ["**基于动量和相关性筛选**\n"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(d["recs"]):
            parts.append(f"{medals[i]} **{r['name']}** ({r['code']})")
            parts.append(f"   类型: {r['type']}  |  {r['reason'][:60]}")
            parts.append("")
        els5 = [
            D("\n".join(parts)),
            H(),
            N("推荐仅供参考，请结合自身风险偏好决策。"),
        ]
        c = HD("🏆 推荐基金", "orange"); c["elements"] = els5; cards.append(c)

    return cards


if __name__ == "__main__":
    if not run_analyze():
        ec = HD("❌ 基金报告生成失败", "red")
        ec["elements"] = [D("analyze 命令执行失败，请检查日志。")]
        send_card(ec, get_token())
        sys.exit(1)

    d = parse()
    token = get_token()
    for i, card in enumerate(build_cards(d)):
        resp = send_card(card, token)
        code = resp.get("code", "?")
        if code != 0:
            print(f"[ERROR] C-{i+1}: {code} {resp.get('msg','')}", file=sys.stderr)
        time.sleep(1.5)
    print("[fund-report] Done.", file=sys.stderr)

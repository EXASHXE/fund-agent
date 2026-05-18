# Alipay Fund Transaction Fetcher — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Automatically scrape fund purchase records from Alipay bill page and incrementally merge into fund-portfolio.yaml.

**Architecture:** `src/data/alipay_fetcher.py` contains all logic (cookie mgmt, Playwright scraping, parsing, mapping, YAML merge). CLI integration adds a `fetch-alipay` subcommand and hooks into `analyze` as Layer 0.

**Tech Stack:** Playwright (browser automation), ruamel.yaml (YAML round-trip), Python stdlib re/datetime/json.

---

### Task 1: Save cookies and update .gitignore

**Files:**
- Create: `.alipay-cookies.json`
- Modify: `.gitignore`

- [ ] **Step 1: Parse user-provided cookie string into JSON**

Parse the cookie string (key=value; ... pairs) into Playwright-compatible format. Domain defaults to `.alipay.com`, path `/`.

```python
# Manual creation of .alipay-cookies.json from user-provided cookie string
import json
from datetime import datetime

cookie_string = "JSESSIONID=RZ42KiXYIsCeh6Ma6f7Zlat0cPjVZqauthRZ55; umt=HBc0154ae00b75b49818448a8b3e57ee53; auth_goto_http_type=https; receive-cookie-deprecation=1; 752459860=vsZTfGbCrPL3D7vQWWnnvshljcZyhSoZexJm64U7QXhd; cna=6y2SIifUY3wCAVtner8DNUD0; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; jsh_t_c_e=jsh_t_0.6359482368508849; ctoken=fuG7SPMIYBNH0twx; _CHIPS-ctoken=fuG7SPMIYBNH0twx; LoginForm=alipay_login_auth; alipay=K1iSL19gs+9WYwC8NCVHERxuexqnnwzgRsrBqfpfMg==; CLUB_ALIPAY_COM=2088622514745727; iw.userid=K1iSL19gs+9WYwC8NCVHEQ==; ali_apache_tracktmp=uid=2088622514745727; auth_jwt=e30.eyJleHAiOjE3NzkxMjM2NTI0NDksInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoidlNFWUFnaHIvUVkxaWN6M1FrN1BmYnBGTG9tRHNUOEQ1ZDk4MWZLIiwidWlkIjoiMjA4ODYyMjUxNDc0NTcyNyJ9.R2JkIL0rkUIlzSVUPGr5rpZBSwX6AKAY831lnP-Y6is; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-ALIPAYJSESSIONID=RZ42KiXYIsCeh6Ma6f7Zlat0cPjVZqauthRZ55; NEW_ALIPAY_TIP=1; rtk=HGQx2pIb+RdQO6mJzGtwHjWLvpcAPO9INndmBQJgLXFYhN4RLfk; ALIPAYJSESSIONID=RZ42KiXYIsCeh6Ma6f7Zlat0cPjVZqauthRZ42GZ00; spanner=gOimrav2ukpEXtClWMqo34k9OaB3YCfo; zone=GZ00F"

cookies = []
for pair in cookie_string.split("; "):
    if "=" not in pair:
        continue
    name, _, value = pair.partition("=")
    cookies.append({
        "name": name.strip(),
        "value": value.strip(),
        "domain": ".alipay.com",
        "path": "/",
        "httpOnly": False,
        "secure": True,
        "sameSite": "Lax",
    })

data = {"updated_at": datetime.now().isoformat(), "cookies": cookies}
with open(".alipay-cookies.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Verify file created and set permissions**

```bash
python3 -c "
import json, os
with open('.alipay-cookies.json') as f:
    d = json.load(f)
print(f'Cookies loaded: {len(d[\"cookies\"])} entries')
print(f'Key cookies present: ALIPAYJSESSIONID={\"ALIPAYJSESSIONID\" in [c[\"name\"] for c in d[\"cookies\"]]}, auth_jwt={\"auth_jwt\" in [c[\"name\"] for c in d[\"cookies\"]]}')
"
os.chmod(".alipay-cookies.json", 0o600)
```

- [ ] **Step 3: Update .gitignore**

Append `.alipay-cookies.json` to `.gitignore`.

- [ ] **Step 4: Commit**

```bash
git add .alipay-cookies.json .gitignore
git commit -m "feat: add alipay cookies store and gitignore"
```

### Task 2: Create alipay_fetcher.py — parse, map, merge modules

**Files:**
- Create: `src/data/alipay_fetcher.py`
- Test: `tests/test_alipay_fetcher.py`

- [ ] **Step 1: Create test file**

```python
# tests/test_alipay_fetcher.py
import pytest
from datetime import date
from src.data.alipay_fetcher import parse_transaction_record, map_fund_name_to_code


def test_parse_basic_buy():
    text = "昨天 11:01 蚂蚁财富-华宝致远混合(QDII)A-买入 金额 150.00 付款成功,份额确认中"
    result = parse_transaction_record(text, today=date(2026, 5, 19))
    assert result is not None
    assert result["fund_name"] == "华宝致远混合(QDII)A"
    assert result["action"] == "买入"
    assert result["amount"] == 150.00
    assert result["after_1500"] is False
    assert result["date"] == date(2026, 5, 18)


def test_parse_sell_ignored():
    text = "昨天 14:30 蚂蚁财富-华宝致远混合(QDII)A-卖出 金额 500.00 交易成功"
    result = parse_transaction_record(text, today=date(2026, 5, 19))
    assert result["action"] == "卖出"


def test_parse_after_1500():
    text = "05-18 15:30 蚂蚁财富-天弘石油天然气指数C-买入 金额 200.00 付款成功"
    result = parse_transaction_record(text, today=date(2026, 5, 19))
    assert result["after_1500"] is True


def test_parse_amount_with_comma():
    text = "05-18 10:00 蚂蚁财富-东方惠灵活配置混合A-买入 金额 1,150.00 付款成功"
    result = parse_transaction_record(text, today=date(2026, 5, 19))
    assert result["amount"] == 1150.00


def test_map_fund_exact():
    yaml_holdings = [
        {"code": "008253", "name": "华宝致远混合(QDII)A"},
        {"code": "001198", "name": "东方惠灵活配置混合A"},
    ]
    code = map_fund_name_to_code("华宝致远混合(QDII)A", yaml_holdings)
    assert code == "008253"


def test_map_fund_core_name():
    yaml_holdings = [
        {"code": "008253", "name": "华宝致远混合(QDII)A"},
    ]
    code = map_fund_name_to_code("华宝致远混合(QDII)A", yaml_holdings)
    assert code == "008253"


def test_map_fund_no_match():
    yaml_holdings = [{"code": "008253", "name": "华宝致远混合(QDII)A"}]
    code = map_fund_name_to_code("未知基金ABC", yaml_holdings)
    assert code is None
```

- [ ] **Step 2: Create src/data/alipay_fetcher.py with parse and map functions**

```python
"""支付宝账单流水抓取、解析、映射与 YAML 合并。"""
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COOKIE_FILE = ".alipay-cookies.json"
BILL_URL = "https://consumeprod.alipay.com/record/standard.htm"
SEARCH_KEYWORD = "蚂蚁财富"
DAYS_LOOKBACK = 30


def parse_transaction_record(text: str, today: date) -> Optional[Dict[str, Any]]:
    """从支付宝账单行文本中提取结构化交易记录。"""
    text = text.strip()
    if SEARCH_KEYWORD not in text:
        return None

    # --- date ---
    parsed_date = None
    if text.startswith("今天"):
        parsed_date = today
    elif text.startswith("昨天"):
        parsed_date = today - timedelta(days=1)
    elif text.startswith("前天"):
        parsed_date = today - timedelta(days=2)
    else:
        m = re.match(r"(\d{2})-(\d{2})", text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            try:
                parsed_date = date(today.year, month, day)
            except ValueError:
                parsed_date = None
        else:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
            if m:
                parsed_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    if parsed_date is None:
        return None

    # --- time ---
    time_match = re.search(r"(\d{2}):(\d{2})", text)
    hour = int(time_match.group(1)) if time_match else 12
    minute = int(time_match.group(2)) if time_match else 0

    # --- fund name (between 1st and 2nd '-') ---
    parts = text.split("-")
    if len(parts) < 3:
        return None
    fund_name = parts[1].strip()

    # --- action (after last '-', before amount/status) ---
    last_segment = parts[-1].strip()
    action_match = re.match(r"(买入|卖出|赎回|分红|退款|转换)", last_segment)
    action = action_match.group(1) if action_match else "未知"

    # --- amount ---
    amount_match = re.search(r"(\d[\d,]*\.\d{2})", text)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else 0.0

    # --- status ---
    status = ""
    if "付款成功" in text:
        status = "付款成功"
    elif "交易成功" in text:
        status = "交易成功"
    if "份额确认中" in text:
        status += ",份额确认中" if status else "份额确认中"

    return {
        "date": parsed_date,
        "time": f"{hour:02d}:{minute:02d}",
        "fund_name": fund_name,
        "action": action,
        "amount": amount,
        "status": status,
        "after_1500": hour >= 15,
    }


def _extract_core_name(full_name: str) -> str:
    """去掉基金名中的括号后缀，提取核心名称。"""
    core = full_name.split("(")[0].split("（")[0].strip()
    return core


def map_fund_name_to_code(
    alipay_fund_name: str, yaml_holdings: List[Dict[str, str]]
) -> Optional[str]:
    """将支付宝流水中的基金名映射为 YAML 中的 fund code。"""
    alipay_core = _extract_core_name(alipay_fund_name)

    for h in yaml_holdings:
        yaml_core = _extract_core_name(h["name"])
        if alipay_core == yaml_core:
            return h["code"]

    for h in yaml_holdings:
        if alipay_core in h["name"] or h["name"] in alipay_core:
            return h["code"]

    for h in yaml_holdings:
        yaml_core = _extract_core_name(h["name"])
        if alipay_core in yaml_core or yaml_core in alipay_core:
            return h["code"]

    return None


def _is_duplicate(record: Dict[str, Any], purchases: List[Dict[str, Any]]) -> bool:
    """检查交易记录是否已存在于 purchases 列表中。"""
    rec_date = record["date"]
    rec_amount = record["amount"]
    for p in purchases:
        p_date = p.get("date")
        if isinstance(p_date, str):
            p_date = date.fromisoformat(p_date)
        p_amount = p.get("amount", 0.0)
        if isinstance(p_amount, (int, float)):
            if p_date == rec_date and abs(p_amount - rec_amount) < 0.02:
                return True
    return False


def merge_purchases_to_yaml(
    records: List[Dict[str, Any]],
    config_path: str,
) -> Dict[str, int]:
    """将抓取到的交易记录增量合并到 YAML，返回 {code: new_count}。"""
    from ruamel.yaml import YAML

    yaml_engine = YAML()
    yaml_engine.preserve_quotes = True
    yaml_engine.indent(mapping=2, sequence=4, offset=2)

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml_engine.load(f)

    stats: Dict[str, int] = {}
    holdings = data.get("holdings", [])
    yaml_holding_map = {h["code"]: h for h in holdings}

    for rec in records:
        if rec["action"] != "买入":
            continue
        code = rec.get("code")
        if not code or code not in yaml_holding_map:
            continue

        h = yaml_holding_map[code]
        existing_purchases = h.get("purchases", [])
        if _is_duplicate(rec, existing_purchases):
            continue

        new_purchase = {
            "date": rec["date"],
            "amount": rec["amount"],
            "nav": None,
            "after_1500": rec.get("after_1500", False),
        }
        existing_purchases.append(new_purchase)
        h["purchases"] = existing_purchases
        stats[code] = stats.get(code, 0) + 1

    with open(config_path, "w", encoding="utf-8") as f:
        yaml_engine.dump(data, f)

    return stats
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_alipay_fetcher.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/data/alipay_fetcher.py tests/test_alipay_fetcher.py
git commit -m "feat: add alipay transaction parser and YAML merge"
```

### Task 3: Add Playwright scraping module

**Files:**
- Modify: `src/data/alipay_fetcher.py`

- [ ] **Step 1: Add cookie management functions**

```python
def _load_cookies() -> Optional[List[Dict[str, Any]]]:
    """从本地文件加载支付宝 cookies。"""
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, "r") as f:
            data = json.load(f)
        return data.get("cookies", [])
    except Exception:
        return None


def _save_cookies(cookies: List[Dict[str, Any]]):
    """保存 cookies 到本地文件。"""
    data = {"updated_at": datetime.now().isoformat(), "cookies": cookies}
    with open(COOKIE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(COOKIE_FILE, 0o600)


def _cookies_expired() -> bool:
    """检查本地 cookie 文件是否存在且未过期（最后一次更新在24h内）。"""
    if not os.path.exists(COOKIE_FILE):
        return True
    try:
        with open(COOKIE_FILE, "r") as f:
            data = json.load(f)
        updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
        return (datetime.now() - updated) > timedelta(hours=24)
    except Exception:
        return True
```

- [ ] **Step 2: Add Playwright scraping function**

```python
def _scrape_alipay_bills(config_holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """使用 Playwright 抓取支付宝账单中近 30 天的蚂蚁财富交易记录。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[支付宝] Playwright 未安装。安装: pip install playwright && python3 -m playwright install chromium")
        return [], {}

    cookies = _load_cookies()
    if cookies is None:
        print("[支付宝] Cookie 文件不存在，启动扫码登录...")
        cookies = _qr_login()
        if cookies is None:
            print("[支付宝] 扫码登录失败或被取消，跳过抓取。")
            return [], {}
        _save_cookies(cookies)

    records = []
    unmapped = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            page.goto(BILL_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            if "auth" in page.url or "login" in page.url:
                print("[支付宝] Cookie 已过期，重新扫码登录...")
                context.close()
                browser.close()
                os.remove(COOKIE_FILE)
                return _scrape_alipay_bills(config_holdings)

            page.wait_for_timeout(2000)

            # Search for keyword
            try:
                search_input = page.locator("input[placeholder*=搜索], input.search-input, #searchInput").first
                if search_input.is_visible():
                    search_input.fill(SEARCH_KEYWORD)
                    page.wait_for_timeout(1500)
                    search_input.press("Enter")
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            today = date.today()
            cutoff = today - timedelta(days=DAYS_LOOKBACK)

            while True:
                page.wait_for_timeout(1500)
                rows = page.locator("tr, .record-item, .bill-item, .list-item, li[class*=record]").all()
                for row in rows:
                    try:
                        text = row.inner_text().strip()
                    except Exception:
                        continue
                    if SEARCH_KEYWORD not in text:
                        continue
                    rec = parse_transaction_record(text, today)
                    if rec is None:
                        continue
                    if rec["date"] < cutoff:
                        continue
                    if rec["action"] != "买入":
                        continue

                    code = map_fund_name_to_code(rec["fund_name"], config_holdings)
                    if code is None:
                        unmapped.add(rec["fund_name"])
                        continue
                    rec["code"] = code
                    records.append(rec)

                next_btn = page.locator("a:has-text('下一页'), button:has-text('下一页'), .next, [class*=next]").first
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(1500)
                else:
                    break

        finally:
            context.close()
            browser.close()

    stats = {"new": len(records), "unmapped": list(unmapped) if unmapped else []}
    return records, stats


def _qr_login() -> Optional[List[Dict[str, Any]]]:
    """启动有头浏览器，让用户扫码登录支付宝。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    print("[支付宝] 正在启动浏览器，请用支付宝 App 扫描页面二维码登录...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://auth.alipay.com/login", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        print("[支付宝] 等待登录完成（最多 120 秒）...")
        try:
            page.wait_for_url("**/record/**", timeout=120000)
        except Exception:
            page.wait_for_url("**consumeprod**", timeout=120000)

        page.wait_for_timeout(2000)
        cookies = context.cookies()
        browser.close()
        print("[支付宝] 登录成功，已保存 cookies。")
        return cookies
```

- [ ] **Step 3: Commit**

```bash
git add src/data/alipay_fetcher.py
git commit -m "feat: add Playwright scraping and QR login for alipay"
```

### Task 4: Add main orchestration function

**Files:**
- Modify: `src/data/alipay_fetcher.py`

- [ ] **Step 1: Add fetch_and_merge main function**

```python
def fetch_and_merge(config_path: str) -> Dict[str, Any]:
    """主入口：抓取支付宝流水并合并到 YAML。
    
    Returns:
        {"status": "ok"|"skipped", "new_total": int, "by_fund": {code: {"name": str, "new": int, "existing": int}, ...}, "unmapped": [str]}
    """
    result = {"status": "skipped", "new_total": 0, "by_fund": {}, "unmapped": []}

    yaml_path = Path(config_path)
    if not yaml_path.exists():
        return result

    from ruamel.yaml import YAML
    yaml_engine = YAML()
    yaml_engine.preserve_quotes = True
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml_engine.load(f)

    holdings = data.get("holdings", [])
    if not holdings:
        return result

    config_holdings = [{"code": h["code"], "name": h["name"]} for h in holdings]

    print("\n[Layer 0] 支付宝流水抓取...")
    records, scrape_stats = _scrape_alipay_bills(config_holdings)

    if not records:
        print("[支付宝] 未发现新交易记录。")
        return result

    # Map codes onto records
    unmapped = set()
    for rec in records:
        if "code" not in rec:
            code = map_fund_name_to_code(rec["fund_name"], config_holdings)
            if code is None:
                unmapped.add(rec["fund_name"])
                continue
            rec["code"] = code

    records = [r for r in records if "code" in r]

    # Build stats
    by_fund: Dict[str, Dict] = {}
    for h in config_holdings:
        existing = len([p for p in holdings if hasattr(p, "get") and False])  # placeholder
        by_fund[h["code"]] = {"name": h["name"], "new": 0, "existing": 0}

    # Count existing purchases
    for h in holdings:
        code = h.get("code", "")
        if code in by_fund:
            by_fund[code]["existing"] = len(h.get("purchases", []))

    # Merge
    stats = merge_purchases_to_yaml(records, config_path)

    for code, count in stats.items():
        if code in by_fund:
            by_fund[code]["new"] = count

    new_total = sum(stats.values())
    result["status"] = "ok"
    result["new_total"] = new_total
    result["by_fund"] = by_fund
    result["unmapped"] = list(unmapped)

    # Summary output
    print(f"\n[支付宝流水] 发现 {len(records)} 条新买入记录")
    for code, info in by_fund.items():
        if info["new"] > 0:
            print(f"  {code} {info['name']}: +{info['new']} 条新增, {info['existing']} 条已存在")
    if unmapped:
        print(f"  无法映射: {len(unmapped)} 条 ({', '.join(unmapped)})")

    return result
```

- [ ] **Step 2: Commit**

```bash
git add src/data/alipay_fetcher.py
git commit -m "feat: add fetch_and_merge orchestration function"
```

### Task 5: CLI integration

**Files:**
- Modify: `src/cli.py`

- [ ] **Step 1: Add --skip-alipay flag and fetch-alipay subcommand**

```python
# Add to p_analyze (after existing add_argument lines):
p_analyze.add_argument("--skip-alipay", action="store_true", help="跳过支付宝流水抓取步骤")

# Add new subcommand (after p_snap):
p_fetch_alipay = sub.add_parser("fetch-alipay", help="从支付宝抓取基金交易流水并合并到 YAML")
p_fetch_alipay.add_argument("-c", "--config", required=True, help="YAML 配置文件路径")
```

- [ ] **Step 2: Insert Layer 0 in cmd_analyze**

In `cmd_analyze`, after loading config (line 54) and before `import_to_database` (line 55):

```python
config = load_portfolio_config(args.config)

# Layer 0: Alipay fetch
if not getattr(args, "skip_alipay", False):
    from src.data.alipay_fetcher import fetch_and_merge
    fetch_and_merge(args.config)
    config = load_portfolio_config(args.config)  # reload after merge

import_to_database(config)
```

- [ ] **Step 3: Add fetch-alipay handler**

```python
def cmd_fetch_alipay(args):
    """从支付宝抓取基金交易流水并合并到 YAML。"""
    from src.data.alipay_fetcher import fetch_and_merge
    result = fetch_and_merge(args.config)
    if result["status"] == "ok":
        print(f"\n[fetch-alipay] 成功新增 {result['new_total']} 条交易记录。")
    else:
        print("[fetch-alipay] 无新记录或抓取被跳过。")
```

- [ ] **Step 4: Wire command in main()**

```python
elif args.command == "fetch-alipay":
    cmd_fetch_alipay(args)
```

- [ ] **Step 5: Commit**

```bash
git add src/cli.py
git commit -m "feat: add --skip-alipay flag and fetch-alipay subcommand"
```

### Task 6: End-to-end validation

**Files:**
- Run: CLI commands

- [ ] **Step 1: Verify fetch-alipay standalone works**

```bash
python3 -m src.cli fetch-alipay -c fund-portfolio.yaml
```

Expected: Playwright launches, loads cookies, scrapes bills, prints summary. If cookies work, should see records. If cookie expired, QR login window opens.

- [ ] **Step 2: Verify analyze --skip-alipay works**

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-alipay --skip-recommend
```

Expected: Normal analyze flow without alipay step.

- [ ] **Step 3: Verify analyze with alipay works**

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-recommend
```

Expected: Layer 0 runs first, then normal flow.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git diff --staged --stat
git commit -m "fix: integration tweaks from e2e testing"
```

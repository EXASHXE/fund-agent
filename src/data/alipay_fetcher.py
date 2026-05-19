"""支付宝账单流水抓取、解析、映射与 YAML 合并。"""
import io
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COOKIE_FILE = ".alipay-cookies.json"
AUTH_STATE_FILE = ".alipay-auth-state.json"
BILL_URL = "https://consumeprod.alipay.com/record/standard.htm"
SEARCH_KEYWORD = "蚂蚁财富"
DAYS_LOOKBACK = 30


def _extract_core_name(full_name: str) -> str:
    """去掉基金名中的括号后缀，提取核心名称。"""
    m = re.match(r"^(.+?)[\(\（]", full_name)
    if m:
        return m.group(1).strip()
    return full_name.strip()


def parse_transaction_record(text: str, today: date) -> Optional[Dict[str, Any]]:
    """从支付宝账单行文本中提取结构化交易记录。"""
    text = text.strip()
    if SEARCH_KEYWORD not in text:
        return None

    parsed_date = None
    if text.startswith("今天"):
        parsed_date = today
    elif text.startswith("昨天"):
        parsed_date = today - timedelta(days=1)
    elif text.startswith("前天"):
        parsed_date = today - timedelta(days=2)
    else:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
        if m:
            try:
                parsed_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                parsed_date = None
        else:
            m = re.match(r"(\d{2})-(\d{2})", text)
            if m:
                try:
                    parsed_date = date(today.year, int(m.group(1)), int(m.group(2)))
                except ValueError:
                    parsed_date = None

    if parsed_date is None:
        return None

    time_match = re.search(r"(\d{2}):(\d{2})", text)
    hour = int(time_match.group(1)) if time_match else 12
    minute = int(time_match.group(2)) if time_match else 0

    parts = text.split("-")
    if len(parts) < 3:
        return None
    fund_name = parts[1].strip()

    last_segment = parts[-1].strip()
    action_match = re.match(r"(买入|卖出|赎回|分红|退款|转换)", last_segment)
    action = action_match.group(1) if action_match else "未知"

    amount_match = re.search(r"(\d[\d,]*\.\d{2})", text)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else 0.0

    status = ""
    if "付款成功" in text:
        status = "付款成功"
    elif "交易成功" in text:
        status = "交易成功"
    if "份额确认中" in text:
        status = f"{status},份额确认中" if status else "份额确认中"

    return {
        "date": parsed_date,
        "time": f"{hour:02d}:{minute:02d}",
        "fund_name": fund_name,
        "action": action,
        "amount": amount,
        "status": status,
        "after_1500": hour >= 15,
    }


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
        if alipay_core in h["name"] or _extract_core_name(h["name"]) in alipay_core:
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


# ── YAML merge ──


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
    yaml_holding_map = {str(h.get("code", "")): h for h in holdings}

    for rec in records:
        if rec.get("action") != "买入":
            continue
        code = str(rec.get("code", ""))
        if not code or code not in yaml_holding_map:
            continue

        h = yaml_holding_map[code]
        existing_purchases: list = h.get("purchases", []) or []
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

    if stats:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml_engine.dump(data, f)

    return stats


# ── Auth state management (Playwright storage_state) ──


def _has_auth_state() -> bool:
    """检查是否有有效的登录状态文件。"""
    f = Path(AUTH_STATE_FILE)
    if not f.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        return (datetime.now() - mtime) < timedelta(hours=24)
    except Exception:
        return False


def _qr_login() -> Optional[str]:
    """无头浏览器获取支付宝登录二维码，终端显示，用户扫码后保存登录状态。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    print("[支付宝] 正在获取登录二维码...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 1000}, device_scale_factor=3)
        page.goto(BILL_URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Extract QR code URL from canvas element
        qr_url = _extract_qr_url_from_page(page)
        if qr_url is None:
            browser.close()
            print("[支付宝] 无法获取二维码。请在有桌面的环境运行 fetch-alipay 触发浏览器扫码。")
            return None

        _display_qr_terminal(qr_url)
        print("[支付宝] 请用支付宝 App 扫描上方二维码（最多 180 秒）...")

        logged_in = False
        for seconds in range(180):
            page.wait_for_timeout(1000)
            current_url = page.url
            if "consumeprod" in current_url:
                logged_in = True
                break
            if "record" in current_url and "alipay" in current_url:
                logged_in = True
                break
            if "auth" not in current_url and "login" not in current_url and "alipay.com" in current_url:
                logged_in = True
                break
            if seconds % 15 == 14:
                print(f"  等待中... ({seconds + 1}s)")

        if not logged_in:
            browser.close()
            print("[支付宝] 登录超时，未检测到扫码。")
            return None

        page.wait_for_timeout(2000)
        print(f"[支付宝] 登录后 URL: {page.url[:120]}")
        context = page.context
        context.storage_state(path=AUTH_STATE_FILE)
        browser.close()
        print("[支付宝] 登录成功，已保存登录状态。")
        return AUTH_STATE_FILE


def _extract_qr_url_from_page(page) -> Optional[str]:
    """从支付宝登录页面提取二维码 URL。"""
    from PIL import Image

    canvas = page.locator("canvas").first
    box = canvas.bounding_box()
    if box is None:
        return None

    clip = {
        "x": box["x"] - 5,
        "y": box["y"] - 5,
        "width": box["width"] + 10,
        "height": box["height"] + 10,
    }
    ss = page.screenshot(clip=clip)
    img = Image.open(io.BytesIO(ss))

    from pyzbar.pyzbar import decode

    for scale in (2, 3, 4):
        scaled = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        decoded = decode(scaled)
        if decoded:
            return decoded[0].data.decode("utf-8")

    gray = img.convert("L")
    for threshold in (100, 128, 150):
        binary = gray.point(lambda p: 255 if p > threshold else 0)
        decoded = decode(binary.resize((480, 480), Image.NEAREST))
        if decoded:
            return decoded[0].data.decode("utf-8")

    return None


def _display_qr_terminal(qr_url: str):
    """在终端用 qrencode 显示二维码。"""
    # Try qrencode CLI first
    try:
        proc = subprocess.run(
            ["qrencode", "-t", "ANSIUTF8", qr_url],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            print("\n" + proc.stdout + "\n")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: Python qrcode library terminal output
    try:
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr.print_ascii()
        return
    except ImportError:
        pass

    # Last resort: just print the URL
    print(f"[支付宝] 请手动复制以下链接到浏览器打开: {qr_url}")


def _ensure_auth() -> Optional[str]:
    """确保有有效的登录状态，过期或不存在则触发扫码登录。返回 auth state 文件路径或 None。"""
    if _has_auth_state():
        return AUTH_STATE_FILE

    if os.path.exists(AUTH_STATE_FILE):
        os.remove(AUTH_STATE_FILE)

    print("[支付宝] 登录状态不存在或已过期，启动扫码登录...")
    auth_path = _qr_login()
    if auth_path is None:
        print("[支付宝] 扫码登录失败或被取消，跳过抓取。")
    return auth_path


def _scrape_alipay_bills(
    config_holdings: List[Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """使用 Playwright 抓取支付宝账单中近 30 天的蚂蚁财富交易记录。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[支付宝] Playwright 未安装。安装: pip install playwright && python3 -m playwright install chromium")
        return [], {}

    auth_state_path = _ensure_auth()
    if auth_state_path is None:
        return [], {}

    records: List[Dict[str, Any]] = []
    unmapped: set = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=auth_state_path)
        except Exception:
            context = browser.new_context()

        page = context.new_page()

        try:
            page.goto(BILL_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            if "auth" in current_url or "login" in current_url or "consumeprod" not in current_url:
                print("[支付宝] 登录状态已过期，将在下次运行时重新扫码登录。")
                if os.path.exists(AUTH_STATE_FILE):
                    os.remove(AUTH_STATE_FILE)
                return [], {"unmapped": [], "auth_expired": True}

            page.wait_for_timeout(2000)

            try:
                search_input = page.locator("input[placeholder*=搜索], input[type=search], input.search-input").first
                if search_input.is_visible():
                    search_input.fill(SEARCH_KEYWORD)
                    page.wait_for_timeout(1500)
                    search_input.press("Enter")
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            today = date.today()
            cutoff = today - timedelta(days=DAYS_LOOKBACK)
            page_num = 0
            max_pages = 200

            while page_num < max_pages:
                page_num += 1
                page.wait_for_timeout(1500)

                rows = page.locator("tr, .record-item, .bill-item, .list-item, li[class*=record]").all()
                for row in rows:
                    try:
                        text_content = row.inner_text().strip()
                    except Exception:
                        continue
                    if SEARCH_KEYWORD not in text_content:
                        continue
                    rec = parse_transaction_record(text_content, today)
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

                next_btn = page.locator(
                    "a:has-text('下一页'), button:has-text('下一页'), .next, [class*=next]"
                ).first
                if next_btn.is_visible() and next_btn.is_enabled():
                    next_btn.click()
                    page.wait_for_timeout(1500)
                else:
                    break

        finally:
            context.close()
            browser.close()

    stats: Dict[str, Any] = {"unmapped": list(unmapped) if unmapped else []}
    return records, stats


# ── Main entry ──


def _save_auth_from_cookie_string(cookie_string: str):
    """将 cookie 字符串 (key=value; ...) 转换为 Playwright storage_state 格式并保存。"""
    import time
    cookies = []
    future_expiry = int(time.time()) + 86400
    for pair in cookie_string.split("; "):
        if "=" not in pair:
            continue
        name, _, value = pair.partition("=")
        value = value.strip().strip('"')
        cookies.append({
            "name": name.strip(),
            "value": value,
            "domain": ".alipay.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
            "expires": future_expiry,
        })
    state = {"cookies": cookies, "origins": []}
    with open(AUTH_STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.chmod(AUTH_STATE_FILE, 0o600)
    print(f"[支付宝] 已从 cookie 字符串保存 {len(cookies)} 个 cookies。")


def fetch_and_merge(config_path: str, cookie_string: Optional[str] = None) -> Dict[str, Any]:
    """主入口：抓取支付宝流水并合并到 YAML。
    
    Args:
        config_path: fund-portfolio.yaml 路径
        cookie_string: 可选，直接提供 cookie 字符串（key=value; ...）跳过 QR 登录
    """
    result: Dict[str, Any] = {
        "status": "skipped",
        "new_total": 0,
        "by_fund": {},
        "unmapped": [],
    }

    if cookie_string:
        _save_auth_from_cookie_string(cookie_string)

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

    config_holdings = [{"code": str(h.get("code", "")), "name": str(h.get("name", ""))} for h in holdings]

    print("\n[Layer 0] 支付宝流水抓取...")
    records, scrape_stats = _scrape_alipay_bills(config_holdings)

    if not records:
        print("[支付宝] 未发现新买入交易记录。")
        result["unmapped"] = scrape_stats.get("unmapped", [])
        return result

    by_fund: Dict[str, Dict[str, Any]] = {}
    for h in config_holdings:
        code = h["code"]
        by_fund[code] = {"name": h["name"], "new": 0, "existing": 0}

    for holding in holdings:
        code = str(holding.get("code", ""))
        if code in by_fund:
            by_fund[code]["existing"] = len(holding.get("purchases", []) or [])

    stats = merge_purchases_to_yaml(records, config_path)

    for code, count in stats.items():
        if code in by_fund:
            by_fund[code]["new"] = count

    new_total = sum(stats.values())
    result["status"] = "ok"
    result["new_total"] = new_total
    result["by_fund"] = by_fund
    result["unmapped"] = scrape_stats.get("unmapped", [])

    print(f"\n[支付宝流水] 发现 {len(records)} 条新买入记录")
    for code, info in by_fund.items():
        if info["new"] > 0:
            print(f"  {code} {info['name']}: +{info['new']} 条新增, {info['existing']} 条已存在")
    if result["unmapped"]:
        print(f"  无法映射: {len(result['unmapped'])} 条 ({', '.join(result['unmapped'])})")

    return result

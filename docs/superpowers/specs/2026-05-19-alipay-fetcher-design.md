# Alipay Fund Transaction Fetcher — Design Spec

> Created: 2026-05-19 | Status: Draft

## 1. Purpose

Automatically fetch fund purchase transaction records from Alipay bill page and merge them into `fund-portfolio.yaml` as part of the `analyze` workflow.

## 2. Files

### New

| File | Purpose |
|------|---------|
| `src/data/alipay_fetcher.py` | Core: cookie management, Playwright scraping, parsing, mapping, YAML merge |
| `.alipay-cookies.json` | Local cookie store (git-ignored, `chmod 600`) |

### Modified

| File | Change |
|------|--------|
| `src/cli.py` | Insert Layer 0 `_run_alipay_fetch()` before Layer 1; add `fetch-alipay` subcommand; add `--skip-alipay` flag |
| `.gitignore` | Append `.alipay-cookies.json` |

## 3. Data Flow

```
analyze() pipeline:
  ┌─────────────────────────────────────────────┐
  │ Layer 0 (NEW): _run_alipay_fetch()           │
  │   1. Check .alipay-cookies.json              │
  │      └─ missing → launch browser, QR login   │
  │   2. Load cookies, navigate to bill page     │
  │   3. Search "蚂蚁财富", paginate 1 month      │
  │   4. Parse records: date, fund, amount       │
  │   5. Map fund name → YAML fund code           │
  │   6. Incremental merge into YAML purchases    │
  │   7. Print summary                           │
  │   (ANY error → log warning, continue)        │
  ├─────────────────────────────────────────────┤
  │ import_to_database()                         │
  │ Layer 1: data collection                     │
  │ Layer 2: scoring                             │
  │ Layer 3: news                                │
  │ Layer 4: report                              │
  └─────────────────────────────────────────────┘
```

## 4. Cookie Format

`.alipay-cookies.json`:
```json
{
  "updated_at": "2026-05-19T10:00:00",
  "cookies": [
    {
      "name": "ALIPAYJSESSIONID",
      "value": "RZ42KiXYIsCeh...",
      "domain": ".alipay.com",
      "path": "/",
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ]
}
```

## 5. Scraping Logic

### 5.1 Target Page

`https://consumeprod.alipay.com/record/standard.htm`

### 5.2 Flow

1. Navigate to bill page with saved cookies
2. Wait for transaction list to render (selector detection)
3. Locate search input, type "蚂蚁财富", trigger search
4. Loop:
   - Wait for rows to load
   - Extract row text content
   - Parse each row (see 5.3)
   - Click "next page" or scroll to load more
   - Stop when: record date exceeds 30-day window (system date - 30 days), or no more data
5. Return list of parsed records

### 5.3 Record Parsing

Input format:
```
昨天 11:01 蚂蚁财富-华宝致远混合(QDII)A-买入 金额 150.00 付款成功,份额确认中
```

Extraction rules:

| Field | Method | Example |
|-------|--------|---------|
| date | "昨天"→yesterday; "前天"→day-before; "NN-NN"→current year; "YYYY-NN-NN"→literal | `2026-05-18` |
| time | regex `\d{2}:\d{2}` | `11:01` |
| fund_name | text between 1st `-` and 2nd `-` | `华宝致远混合(QDII)A` |
| action | text after last `-`, before amount/status | `买入` |
| amount | regex `\d+\.\d{2}` | `150.00` |
| status | trailing text after amount | `付款成功,份额确认中` |
| after_1500 | time >= `15:00` → true | `false` |

Only records with action = `买入` are imported.

## 6. Fund Mapping

```
Alipay fund name:  "华宝致远混合(QDII)A"
                   ↓ strip parenthetical suffix
core name:         "华宝致远混合"
                   ↓ case-insensitive substring match against
YAML fund names:   ["华宝致远混合(QDII)A", "天弘石油天然气指数C", ...]
                   ↓
match:             "华宝致远混合(QDII)A" → code "008253" ✓
```

Algorithm:
1. Extract core name (text before first `(` or `（`)
2. For each YAML holding, extract its core name
3. Exact match on core names → success
4. If no exact match, check if alipay core is substring of YAML full name
5. If still unmatched → skip record, print warning with fund name

## 7. YAML Merge

### 7.1 Dedup Rule

For each parsed record, check against existing purchases:
```
MATCH:  same fund_code AND same date AND |amount_diff| < 0.02
SKIP:   match found (already exists)
ADD:    no match found → append to purchases list
```

### 7.2 Write Strategy

Use `ruamel.yaml` to preserve comments, ordering, and formatting. Only modify `purchases` lists of matched funds. The `nav` field is set to `null` (filled by AKShare later).

### 7.3 Summary Output

```
[支付宝流水] 发现 45 条蚂蚁财富交易记录（近1个月）
  008253 华宝致远混合(QDII)A: +3 条新增, 15 条已存在
  017436 华宝纳斯达克精选股票(QDII)A: +2 条新增, 14 条已存在
  001198 东方惠灵活配置混合A: +1 条新增, 3 条已存在
  无法映射: 1 条 (基金名: "XX未知")
```

## 8. Cookie Lifecycle

### 8.1 Initial Setup

On first run (`.alipay-cookies.json` missing):
- Launch Chromium in **headed** mode (visible browser window)
- Navigate to `https://auth.alipay.com/login`
- Print prompt: "请用支付宝 App 扫描浏览器中的二维码完成登录"
- Poll URL until it leaves auth domain → login complete
- Call `context.cookies()` to extract all cookies
- Save to `.alipay-cookies.json` with `chmod 600`
- Close browser

### 8.2 Expiry Detection

On load cookie + navigate: if URL redirects to `*/auth/*` → cookie expired.
- Delete `.alipay-cookies.json`
- Trigger 8.1 initial setup flow

## 9. CLI Integration

### 9.1 New Subcommand

```bash
python3 -m src.cli fetch-alipay -c fund-portfolio.yaml
```

Standalone: fetch + merge only, no scoring/report.

### 9.2 Analyze Integration

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md           # default: includes alipay fetch
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-alipay  # skip
```

## 10. Error Handling

**Principle**: Alipay fetch is additive. Any failure MUST NOT block the main analyze pipeline.

| Scenario | Behavior |
|----------|----------|
| Playwright/Chromium not installed | Print install guide, skip, continue |
| Cookie file missing + user closes QR window | Skip, continue |
| Page structure changed (parse fails) | Log error + sample HTML snippet, skip |
| Network timeout | Retry ×2, then skip |
| Zero records map to YAML funds | Print warning, do not modify YAML |
| Amount parses as 0.00 | Skip that record |

## 11. Dependencies

New Python packages:
- `playwright` — browser automation (not yet installed)
- `ruamel.yaml` — preserve YAML formatting on write (already installed v0.18.16, add to requirements.txt)

Playwright browser install:
```bash
python3 -m playwright install chromium
```

## 12. Security

- `.alipay-cookies.json` is git-ignored and `chmod 600`
- Cookies never transmitted outside the local machine
- Browser launched in headed mode for QR login (user sees what's happening)
- No cookies logged or printed to console

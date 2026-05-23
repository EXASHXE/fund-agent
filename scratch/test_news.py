import akshare as ak
for code in ["021620", "018380"]:
    try:
        df = ak.fund_portfolio_hold_em(symbol=code, date="2025")
        if df is not None and not df.empty:
            print(f"Fund {code} hold EM 2025: shape =", df.shape)
        else:
            df2 = ak.fund_portfolio_hold_em(symbol=code, date="2024")
            if df2 is not None and not df2.empty:
                print(f"Fund {code} hold EM 2024: shape =", df2.shape)
            else:
                print(f"Fund {code} hold EM empty")
    except Exception as e:
        print(f"Fund {code} error:", e)

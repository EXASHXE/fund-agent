import akshare as ak

for code in ["008253", "017436", "378006"]:
    print(f"\n--- Fund {code} ---")
    for year in ["2025", "2024"]:
        try:
            df = ak.fund_portfolio_hold_em(symbol=code, date=year)
            if df is not None and not df.empty:
                print(f"Year {year}: shape =", df.shape)
                print(df.head(5)[["股票代码", "股票名称", "占净值比例"]])
                break
            else:
                print(f"Year {year} empty")
        except Exception as e:
            print(f"Year {year} error:", e)

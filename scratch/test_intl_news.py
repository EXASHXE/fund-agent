import pandas as pd
pd.options.mode.string_storage = "python"

import akshare as ak
for code in ["NVDA", "00700"]:
    print(f"\n--- Stock {code} news ---")
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            print(f"Success! shape = {df.shape}")
            print(df.head(2)[["新闻标题", "发布时间"]])
        else:
            print("Empty dataframe returned")
    except Exception as e:
        print(f"Error: {e}")

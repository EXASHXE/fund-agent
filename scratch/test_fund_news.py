import pandas as pd
pd.options.mode.string_storage = "python"
import akshare as ak

for code in ["008253", "001198"]:
    print(f"\n--- Fund Code {code} EM news ---")
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            print(f"Success! shape = {df.shape}")
            print(df.head(2))
        else:
            print("Empty dataframe returned")
    except Exception as e:
        print(f"Error: {e}")

import pandas as pd
print("Before setting:", pd.options.mode.string_storage)

pd.options.mode.string_storage = "python"
print("After setting:", pd.options.mode.string_storage)

import akshare as ak
try:
    df = ak.stock_news_em(symbol="000001")
    print("Success! shape =", df.shape)
except Exception as e:
    import traceback
    traceback.print_exc()

import pandas as pd
pd.options.mode.string_storage = "python"
import akshare as ak
import traceback

try:
    ak.stock_news_em(symbol="008253")
except Exception as e:
    traceback.print_exc()

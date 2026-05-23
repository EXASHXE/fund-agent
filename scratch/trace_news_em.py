import traceback
import akshare as ak

try:
    ak.stock_news_em(symbol="000001")
except Exception as e:
    traceback.print_exc()

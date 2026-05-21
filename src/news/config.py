"""新闻模块 LLM 蒸馏 API 配置"""
import os

LLM_CONFIG = {
    "api_url": os.environ.get(
        "FUND_NEWS_LLM_URL",
        "https://opencode.ai/zen/v1/chat/completions",
    ),
    "model": os.environ.get(
        "FUND_NEWS_LLM_MODEL",
        "deepseek-v4-flash-free",
    ),
    "api_key": os.environ.get(
        "FUND_NEWS_LLM_KEY",
        "sk-fSTFZjQbGmXIN8tQbCGOr6u5Zh45Z6ctRpNbhWQ1HHW7QReUTeN3H3y98ihuU3yk",
    ),
    "max_tokens": 512,
    "temperature": 0.1,
    "timeout": 15,
}

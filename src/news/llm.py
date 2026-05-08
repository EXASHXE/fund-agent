"""LLM 接口 — 新闻综合推理与趋势判断"""
from typing import Dict, List
import json
import os


class OpenAICompatibleClient:
    """OpenAI-compatible API 客户端"""

    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'


class NewsLLMAnalyzer:
    """LLM 驱动的新闻综合推理"""

    SYSTEM_PROMPT = """你是一个量化基金分析师助手。请基于提供的新闻情绪数据、基金净值走势和当前持仓信息，
进行综合分析并返回结构化JSON。要求：
1. 客观冷静，不做过度乐观或悲观的判断
2. 标注置信度（high/medium/low）
3. 风险因素要具体而非泛泛而谈
4. 只返回JSON，不要有其他内容

JSON格式:
{
  "summary": "一句话新闻事件总结",
  "sentiment_trend": "情绪趋势描述",
  "key_events": ["事件1", "事件2"],
  "short_term_view": "短期(1-2周)趋势判断",
  "mid_term_view": "中期(1-3月)趋势判断",
  "risk_factors": ["风险1", "风险2"],
  "confidence": "high/medium/low"
}"""

    def __init__(self, client=None):
        self.client = client or OpenAICompatibleClient()

    def analyze(
        self,
        fund_name: str,
        fund_code: str,
        sentiment_data: List[Dict],
        nav_summary: str,
        holding_context: str = "",
    ) -> Dict:
        """对基金新闻进行 LLM 综合推理。"""
        recent_sent = sentiment_data[-5:] if len(sentiment_data) > 5 else sentiment_data
        sent_lines = []
        for s in recent_sent:
            sent_lines.append(
                f"- {s.get('date', '')}: 情绪均值{s.get('sentiment_mean', 0):.3f}, "
                f"新闻{s.get('news_count', 0)}条, "
                f"关键词: {', '.join(s.get('top_keywords', [])[:5])}"
            )
        sent_text = "\n".join(sent_lines)

        user_prompt = f"""基金: {fund_name} ({fund_code})

近期新闻情绪:
{sent_text}

净值走势:
{nav_summary}

{"持仓上下文: " + holding_context if holding_context else ""}

请基于以上信息进行分析。"""

        try:
            response = self.client.chat(self.SYSTEM_PROMPT, user_prompt)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("\n", 1)[0]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except Exception as e:
            return {"error": str(e), "summary": "LLM分析暂时不可用"}

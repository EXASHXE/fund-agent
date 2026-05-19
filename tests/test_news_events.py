import unittest

from src.news.events import extract_news_events


class NewsEventsTest(unittest.TestCase):
    def test_extract_news_events_clusters_related_semiconductor_news(self):
        news = [
            {
                "title": "寒武纪业绩预增，AI芯片需求改善",
                "content": "国内半导体产业链景气度提升",
                "date": "2026-05-18",
                "sentiment_score": 0.82,
            },
            {
                "title": "精测电子受益半导体检测设备订单增长",
                "content": "国产替代逻辑延续",
                "date": "2026-05-18",
                "sentiment_score": 0.75,
            },
        ]

        events = extract_news_events(news)

        self.assertTrue(events)
        self.assertEqual(events[0]["direction"], "positive")
        self.assertGreater(events[0]["impact_score"], 0)
        self.assertTrue(any("半导体" in asset or "芯片" in asset for asset in events[0]["affected_assets"]))


if __name__ == "__main__":
    unittest.main()

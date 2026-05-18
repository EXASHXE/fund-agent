import pytest
from datetime import date
from src.data.alipay_fetcher import (
    parse_transaction_record,
    map_fund_name_to_code,
    _extract_core_name,
    _is_duplicate,
)


class TestParseTransactionRecord:
    def test_basic_buy(self):
        text = "昨天 11:01 蚂蚁财富-华宝致远混合(QDII)A-买入 金额 150.00 付款成功,份额确认中"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["fund_name"] == "华宝致远混合(QDII)A"
        assert result["action"] == "买入"
        assert result["amount"] == 150.00
        assert result["after_1500"] is False
        assert result["date"] == date(2026, 5, 18)

    def test_sell_action(self):
        text = "昨天 14:30 蚂蚁财富-华宝致远混合(QDII)A-卖出 金额 500.00 交易成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["action"] == "卖出"

    def test_after_1500(self):
        text = "05-18 15:30 蚂蚁财富-天弘石油天然气指数C-买入 金额 200.00 付款成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["after_1500"] is True
        assert result["date"] == date(2026, 5, 18)

    def test_amount_with_comma(self):
        text = "05-18 10:00 蚂蚁财富-东方惠灵活配置混合A-买入 金额 1,150.00 付款成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["amount"] == 1150.00

    def test_today(self):
        text = "今天 09:00 蚂蚁财富-华宝纳斯达克精选股票(QDII)A-买入 金额 100.00 付款成功,份额确认中"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["date"] == date(2026, 5, 19)

    def test_day_before_yesterday(self):
        text = "前天 10:00 蚂蚁财富-摩根全球新兴市场混合(QDII)-买入 金额 800.00 付款成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["date"] == date(2026, 5, 17)

    def test_full_date_format(self):
        text = "2026-05-15 10:30 蚂蚁财富-天弘石油天然气指数C-买入 金额 200.00 付款成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["date"] == date(2026, 5, 15)

    def test_no_ant_keyword(self):
        text = "昨天 10:00 淘宝-购买商品 金额 99.00 付款成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is None

    def test_status_extraction(self):
        text = "05-18 10:00 蚂蚁财富-东方惠灵活配置混合A-买入 金额 1,150.00 付款成功,份额确认中"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert "付款成功" in result["status"]
        assert "份额确认中" in result["status"]

    def test_action_redemption(self):
        text = "昨天 11:00 蚂蚁财富-华宝致远混合(QDII)A-赎回 金额 500.00 交易成功"
        result = parse_transaction_record(text, today=date(2026, 5, 19))
        assert result is not None
        assert result["action"] == "赎回"


class TestExtractCoreName:
    def test_with_parentheses(self):
        assert _extract_core_name("华宝致远混合(QDII)A") == "华宝致远混合"

    def test_with_chinese_parens(self):
        assert _extract_core_name("华宝纳斯达克精选股票发起式（QDII）A") == "华宝纳斯达克精选股票发起式"

    def test_no_parens(self):
        assert _extract_core_name("天弘石油天然气指数C") == "天弘石油天然气指数C"


class TestMapFundNameToCode:
    @pytest.fixture
    def holdings(self):
        return [
            {"code": "008253", "name": "华宝致远混合(QDII)A"},
            {"code": "017436", "name": "华宝纳斯达克精选股票(QDII)A"},
            {"code": "001198", "name": "东方惠灵活配置混合A"},
            {"code": "378006", "name": "摩根全球新兴市场混合(QDII)"},
        ]

    def test_exact_match(self, holdings):
        code = map_fund_name_to_code("华宝致远混合(QDII)A", holdings)
        assert code == "008253"

    def test_core_name_match(self, holdings):
        code = map_fund_name_to_code("华宝致远混合(QDII)A", holdings)
        assert code == "008253"

    def test_substring_match(self, holdings):
        code = map_fund_name_to_code("东方惠灵活配置混合A", holdings)
        assert code == "001198"

    def test_no_match(self, holdings):
        code = map_fund_name_to_code("未知基金ABC", holdings)
        assert code is None


class TestIsDuplicate:
    def test_exact_match(self):
        rec = {"date": date(2026, 5, 18), "amount": 150.00}
        purchases = [{"date": date(2026, 5, 18), "amount": 150.00}]
        assert _is_duplicate(rec, purchases) is True

    def test_float_tolerance(self):
        rec = {"date": date(2026, 5, 18), "amount": 150.01}
        purchases = [{"date": date(2026, 5, 18), "amount": 150.00}]
        assert _is_duplicate(rec, purchases) is True

    def test_different_date(self):
        rec = {"date": date(2026, 5, 19), "amount": 150.00}
        purchases = [{"date": date(2026, 5, 18), "amount": 150.00}]
        assert _is_duplicate(rec, purchases) is False

    def test_different_amount(self):
        rec = {"date": date(2026, 5, 18), "amount": 200.00}
        purchases = [{"date": date(2026, 5, 18), "amount": 150.00}]
        assert _is_duplicate(rec, purchases) is False

    def test_string_date_in_purchases(self):
        rec = {"date": date(2026, 5, 18), "amount": 150.00}
        purchases = [{"date": "2026-05-18", "amount": 150.00}]
        assert _is_duplicate(rec, purchases) is True

"""验证量化重构框架——Sortino 比率 & 舆情时间衰减

在修改 scorer.py 和 sentiment.py 之前，确保新算法的数值正确性。
"""

import numpy as np


def test_sortino_calculation():
    """验证 Sortino 比率计算正确性
    
    Sortino = (Mean(R_i - MAR_daily) * 252) / DownsideDeviation_annual
    DownsideDeviation_annual = sqrt(mean(min(0, R_i - MAR_daily)^2)) * sqrt(252)
    """
    np.random.seed(42)
    # 模拟 252 个交易日收益率（年化约 12% 收益，15% 波动）
    daily_returns = np.random.normal(0.0005, 0.015, 252).tolist()
    
    MAR_annual = 0.025  # 2.5% 无风险利率
    MAR_daily = (1 + MAR_annual) ** (1/252) - 1
    
    returns = np.array(daily_returns, dtype=float)
    
    # 下行偏差（仅计入低于 MAR 的波动）
    downside = np.minimum(returns - MAR_daily, 0)
    downside_deviation_daily = np.sqrt(np.mean(downside ** 2))
    downside_deviation_annual = downside_deviation_daily * np.sqrt(252)
    
    # Sortino 比率
    mean_excess_daily = np.mean(returns - MAR_daily)
    sortino = mean_excess_daily * 252 / downside_deviation_annual if downside_deviation_annual > 0 else 0.0
    
    print(f"日均超额收益: {mean_excess_daily:.8f}")
    print(f"年化下行偏差: {downside_deviation_annual:.6f}")
    print(f"Sortino Ratio: {sortino:.4f}")
    
    assert isinstance(sortino, float), "Sortino must be float"
    assert -10 < sortino < 10, f"Sortino {sortino} out of reasonable range [-10, 10]"
    
    # 正收益应产生正 Sortino
    assert sortino > 0, f"Expected positive Sortino for positive excess returns, got {sortino}"
    
    print("✓ Sortino ratio test PASSED")
    return sortino


def test_sortino_with_negative_returns():
    """验证 Sortino 在亏损场景下正确返回负值或零"""
    # 模拟大幅亏损的日收益率
    np.random.seed(99)
    daily_returns = np.random.normal(-0.003, 0.02, 252).tolist()
    
    MAR_annual = 0.025
    MAR_daily = (1 + MAR_annual) ** (1/252) - 1
    
    returns = np.array(daily_returns, dtype=float)
    downside = np.minimum(returns - MAR_daily, 0)
    downside_dev = np.sqrt(np.mean(downside ** 2)) * np.sqrt(252)
    mean_excess = np.mean(returns - MAR_daily)
    sortino = mean_excess * 252 / downside_dev if downside_dev > 0 else 0.0
    
    print(f"Negative scenario Sortino: {sortino:.4f}")
    assert sortino < 0, f"Expected negative Sortino for negative returns, got {sortino}"
    print("✓ Negative Sortino test PASSED")
    return sortino


def test_sentiment_decay():
    """验证舆情时间衰减加权算法
    
    Weight_i = exp(-λ * Δt)
    Decayed_Sentiment = Σ(Sentiment_i * Weight_i) / Σ(Weight_i)
    """
    daily_sentiments = [
        {"date": "2026-05-14", "sentiment_mean": 0.10},
        {"date": "2026-05-15", "sentiment_mean": 0.18},
        {"date": "2026-05-16", "sentiment_mean": 0.25},
        {"date": "2026-05-17", "sentiment_mean": 0.33},
        {"date": "2026-05-18", "sentiment_mean": 0.42},
        {"date": "2026-05-19", "sentiment_mean": 0.50},
        {"date": "2026-05-20", "sentiment_mean": 0.60},
    ]
    
    LAMBDA = 0.200  # 3.5 天半衰期
    
    total_weight = 0.0
    weighted_sum = 0.0
    current_idx = len(daily_sentiments) - 1
    
    for idx, agg in enumerate(daily_sentiments):
        delta_t = current_idx - idx
        decay_weight = np.exp(-LAMBDA * delta_t)
        raw = agg["sentiment_mean"]
        weighted_sum += raw * decay_weight
        total_weight += decay_weight
    
    decayed = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.5
    
    raw_values = [d["sentiment_mean"] for d in daily_sentiments]
    simple_mean = np.mean(raw_values)
    
    print(f"原始情绪值: {raw_values}")
    print(f"简单均值: {simple_mean:.4f}")
    print(f"指数衰减聚合 (λ={LAMBDA}): {decayed}")
    
    # 验证：衰减值应在 range 内
    assert min(raw_values) <= decayed <= max(raw_values), \
        f"Decayed {decayed} out of range [{min(raw_values)}, {max(raw_values)}]"
    
    # 单调上升数据：衰减值应高于中位数（给近期更高权重）
    median_val = np.median(raw_values)
    assert decayed > median_val, \
        f"Decayed {decayed} should be > median {median_val:.4f} (recent-weighted for upward trend)"
    
    print("✓ Sentiment decay test PASSED")
    return decayed


def test_sentiment_decay_high_lambda():
    """验证高 λ 值时更快遗忘旧数据"""
    daily = [
        {"sentiment_mean": 0.1},  # 6 天前
        {"sentiment_mean": 0.1},  # 5 天前
        {"sentiment_mean": 0.1},  # 4 天前
        {"sentiment_mean": 0.1},  # 3 天前
        {"sentiment_mean": 0.1},  # 2 天前
        {"sentiment_mean": 0.1},  # 1 天前
        {"sentiment_mean": 0.9},  # 今天
    ]
    
    LAMBDA_HIGH = 0.5  # 高波动市：快速遗忘
    
    total_w = 0.0
    weighted_s = 0.0
    current_idx = len(daily) - 1
    
    for idx, agg in enumerate(daily):
        delta_t = current_idx - idx
        w = np.exp(-LAMBDA_HIGH * delta_t)
        weighted_s += agg["sentiment_mean"] * w
        total_w += w
    
    decayed_high = round(weighted_s / total_w, 4)
    
    LAMBDA_LOW = 0.1  # 长线牛市：缓慢遗忘
    total_w = 0.0
    weighted_s = 0.0
    for idx, agg in enumerate(daily):
        delta_t = current_idx - idx
        w = np.exp(-LAMBDA_LOW * delta_t)
        weighted_s += agg["sentiment_mean"] * w
        total_w += w
    decayed_low = round(weighted_s / total_w, 4)
    
    print(f"高 λ ({LAMBDA_HIGH}) 衰减值: {decayed_high} (更接近今日 0.9)")
    print(f"低 λ ({LAMBDA_LOW}) 衰减值: {decayed_low} (历史数据影响更大)")
    
    # 高 λ 时衰减值应更接近今天的 0.9
    assert decayed_high > decayed_low, \
        f"High λ should give more weight to recent data: {decayed_high} vs {decayed_low}"
    
    print("✓ λ 参数敏感性测试 PASSED")
    return decayed_high, decayed_low


if __name__ == "__main__":
    print("=" * 60)
    print("量化重构框架沙盒验证")
    print("=" * 60)
    
    s1 = test_sortino_calculation()
    s2 = test_sortino_with_negative_returns()
    d1 = test_sentiment_decay()
    d2_h, d2_l = test_sentiment_decay_high_lambda()
    
    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS PASSED ✓")
    print(f"  Sortino (normal):    {s1:.4f}")
    print(f"  Sortino (negative):  {s2:.4f}")
    print(f"  Decay Sentiment:     {d1:.4f}")
    print(f"  Decay (high λ):     {d2_h:.4f}")
    print(f"  Decay (low λ):      {d2_l:.4f}")
    print("=" * 60)

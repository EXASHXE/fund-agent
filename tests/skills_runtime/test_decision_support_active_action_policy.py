"""Tests for decision_support active action policy — active actions require evidence anchors."""


from src.skills_runtime.decision_support.action_policy import ACTIVE_ACTIONS, PASSIVE_ACTIONS, _normalized_action


class TestActiveActionPolicy:
    """Active actions (BUY, SELL, INCREASE, REDUCE) must have evidence anchors."""

    def test_active_actions_set(self):
        assert "BUY" in ACTIVE_ACTIONS
        assert "SELL" in ACTIVE_ACTIONS
        assert "INCREASE" in ACTIVE_ACTIONS
        assert "REDUCE" in ACTIVE_ACTIONS

    def test_passive_actions_set(self):
        assert "WAIT" in PASSIVE_ACTIONS
        assert "HOLD" in PASSIVE_ACTIONS
        assert "PAUSE_DCA" in PASSIVE_ACTIONS

    def test_active_and_passive_disjoint(self):
        assert not (ACTIVE_ACTIONS & PASSIVE_ACTIONS)

    def test_normalized_action_buy(self):
        assert _normalized_action("buy") == "BUY"

    def test_normalized_action_sell(self):
        assert _normalized_action("sell") == "SELL"

    def test_normalized_action_none(self):
        assert _normalized_action(None) is None

    def test_normalized_action_unknown(self):
        assert _normalized_action("UNKNOWN") is None

    def test_normalized_action_aliases(self):
        assert _normalized_action("ADD") == "INCREASE"
        assert _normalized_action("TRIM") == "REDUCE"
        assert _normalized_action("WATCH") == "HOLD"

    def test_active_actions_are_frozenset(self):
        assert isinstance(ACTIVE_ACTIONS, frozenset)

    def test_passive_actions_are_frozenset(self):
        assert isinstance(PASSIVE_ACTIONS, frozenset)

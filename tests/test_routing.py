import pytest
from app.graph.routing import route_after_verify, route_after_resolution


class TestRouteAfterVerify:
    def test_verified_goes_to_fetch_context(self):
        state = {"identity_verified": True}
        assert route_after_verify(state) == "fetch_context"

    def test_not_verified_goes_to_escalate(self):
        state = {"identity_verified": False}
        assert route_after_verify(state) == "escalate"

    def test_missing_verified_defaults_to_escalate(self):
        assert route_after_verify({}) == "escalate"


class TestRouteAfterResolution:
    def test_high_confidence_no_reason_ends(self):
        state = {"confidence": 0.9, "escalation_reason": None}
        assert route_after_resolution(state) == "__end__"

    def test_low_confidence_escalates(self):
        state = {"confidence": 0.5, "escalation_reason": None}
        assert route_after_resolution(state) == "escalate"

    def test_confidence_at_threshold_escalates(self):
        # threshold is 0.75; exactly at threshold should NOT escalate
        state = {"confidence": 0.75, "escalation_reason": None}
        assert route_after_resolution(state) == "__end__"

    def test_escalation_reason_forces_escalate(self):
        state = {"confidence": 0.9, "escalation_reason": "User unverified"}
        assert route_after_resolution(state) == "escalate"

    def test_both_conditions_escalate(self):
        state = {"confidence": 0.3, "escalation_reason": "Cannot resolve"}
        assert route_after_resolution(state) == "escalate"

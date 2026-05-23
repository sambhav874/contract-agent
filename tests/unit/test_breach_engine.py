"""Unit tests for BreachEngine — all operators, penalty types, edge cases."""

import pytest
from app.agents.breach_engine import BreachEngine


def _kpi(operator=">=", value_min=90.0, value_max=None,
         consequence_value=500.0, consequence_unit="flat"):
    return {
        "contract_id": "c1",
        "kpi_id": "k1",
        "operator": operator,
        "value_min": value_min,
        "value_max": value_max,
        "consequence_value": consequence_value,
        "consequence_unit": consequence_unit,
        "trigger_condition": "Below threshold",
        "remediation": "Submit RCA",
        "remediation_sla": "48h",
    }


def _actual(value=85.0):
    return {"value": value}


# ── check_breach ──────────────────────────────────────────────────────

class TestCheckBreach:
    def test_breach_ge_operator(self):
        """Actual below >= threshold → breach."""
        result = BreachEngine.check_breach(_kpi(">=", 90.0), _actual(85.0))
        assert result.is_breach is True
        assert result.actual_value == 85.0
        assert result.threshold_value == 90.0

    def test_no_breach_ge_operator(self):
        """Actual at threshold → no breach."""
        result = BreachEngine.check_breach(_kpi(">=", 90.0), _actual(90.0))
        assert result.is_breach is False

    def test_breach_le_operator(self):
        """Actual above <= threshold → breach."""
        result = BreachEngine.check_breach(_kpi("<=", 5.0), _actual(7.0))
        assert result.is_breach is True

    def test_no_breach_le_operator(self):
        result = BreachEngine.check_breach(_kpi("<=", 5.0), _actual(5.0))
        assert result.is_breach is False

    def test_breach_gt_operator(self):
        result = BreachEngine.check_breach(_kpi(">", 10.0), _actual(10.0))
        assert result.is_breach is True   # 10 is NOT > 10

    def test_no_breach_gt_operator(self):
        result = BreachEngine.check_breach(_kpi(">", 10.0), _actual(11.0))
        assert result.is_breach is False

    def test_breach_lt_operator(self):
        result = BreachEngine.check_breach(_kpi("<", 5.0), _actual(5.0))
        assert result.is_breach is True   # 5 is NOT < 5

    def test_breach_eq_operator(self):
        result = BreachEngine.check_breach(_kpi("==", 100.0), _actual(99.0))
        assert result.is_breach is True

    def test_no_breach_eq_operator(self):
        result = BreachEngine.check_breach(_kpi("==", 100.0), _actual(100.0))
        assert result.is_breach is False

    def test_breach_ne_operator(self):
        result = BreachEngine.check_breach(_kpi("!=", 0.0), _actual(0.0))
        assert result.is_breach is True

    def test_between_operator_in_range(self):
        kpi = _kpi("between", value_min=80.0, value_max=100.0)
        result = BreachEngine.check_breach(kpi, _actual(90.0))
        assert result.is_breach is False

    def test_between_operator_below_range(self):
        kpi = _kpi("between", value_min=80.0, value_max=100.0)
        result = BreachEngine.check_breach(kpi, _actual(75.0))
        assert result.is_breach is True

    def test_between_operator_above_range(self):
        kpi = _kpi("between", value_min=80.0, value_max=100.0)
        result = BreachEngine.check_breach(kpi, _actual(105.0))
        assert result.is_breach is True

    def test_no_threshold_no_breach(self):
        """Missing threshold → always on track."""
        kpi = _kpi(">=", value_min=None)
        kpi["value_min"] = None
        result = BreachEngine.check_breach(kpi, _actual(0.0))
        assert result.is_breach is False

    def test_unknown_operator_no_breach(self):
        """Unknown operator → safe default: no breach."""
        kpi = _kpi("???", 90.0)
        result = BreachEngine.check_breach(kpi, _actual(50.0))
        assert result.is_breach is False

    def test_breach_sets_penalty_amount(self):
        kpi = _kpi(">=", 90.0, consequence_value=1000.0, consequence_unit="flat")
        result = BreachEngine.check_breach(kpi, _actual(80.0))
        assert result.penalty_amount == 1000.0

    def test_sample_count_propagated(self):
        result = BreachEngine.check_breach(_kpi(), _actual(85.0), sample_count=5)
        assert result.sample_count == 5


# ── calculate_penalty ─────────────────────────────────────────────────

class TestCalculatePenalty:
    def test_flat_penalty(self):
        """No scaling keyword → return consequence_value directly."""
        kpi = _kpi(">=", 90.0, consequence_value=500.0, consequence_unit="USD")
        penalty = BreachEngine.calculate_penalty(kpi, 80.0)
        assert penalty == 500.0

    def test_per_percentage_point_penalty(self):
        """Deviation of 10pp × 500 = 5000."""
        kpi = _kpi(">=", 90.0, consequence_value=500.0,
                   consequence_unit="USD per percentage point")
        penalty = BreachEngine.calculate_penalty(kpi, 80.0)
        assert penalty == 5000.0

    def test_per_unit_penalty(self):
        """Volume breach: deviation of 20 units × 50 = 1000."""
        kpi = _kpi(">=", 100.0, consequence_value=50.0,
                   consequence_unit="INR per unit")
        penalty = BreachEngine.calculate_penalty(kpi, 80.0)
        assert penalty == 1000.0

    def test_per_hour_penalty(self):
        """Hours of overage × rate."""
        kpi = _kpi("<=", 5.0, consequence_value=200.0,
                   consequence_unit="USD per hour")
        # actual=8 → deviation=3 hours above limit of 5
        penalty = BreachEngine.calculate_penalty(kpi, 8.0)
        assert penalty == 600.0

    def test_per_item_penalty(self):
        kpi = _kpi(">=", 50.0, consequence_value=10.0,
                   consequence_unit="INR per item")
        penalty = BreachEngine.calculate_penalty(kpi, 40.0)
        assert penalty == 100.0

    def test_no_breach_ge_deviation_is_zero(self):
        """Actual >= threshold → deviation 0 → 0 penalty for scaling types."""
        kpi = _kpi(">=", 90.0, consequence_value=500.0,
                   consequence_unit="USD per percentage point")
        penalty = BreachEngine.calculate_penalty(kpi, 95.0)
        assert penalty == 0.0

    def test_le_breach_deviation(self):
        """For <= KPI: deviation = actual - threshold."""
        kpi = _kpi("<=", 3.0, consequence_value=100.0,
                   consequence_unit="USD per percentage point")
        penalty = BreachEngine.calculate_penalty(kpi, 8.0)
        assert penalty == 500.0  # deviation=5 × 100

    def test_consequence_unit_none_defaults_flat(self):
        """Missing consequence_unit → flat penalty."""
        kpi = _kpi(">=", 90.0, consequence_value=300.0, consequence_unit=None)
        penalty = BreachEngine.calculate_penalty(kpi, 50.0)
        assert penalty == 300.0

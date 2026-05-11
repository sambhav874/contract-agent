"""Engine for detecting KPI breaches by comparing actuals vs targets."""

import operator
from typing import Any, Dict
from app.db.models import KPIItem, OperationalActual, BreachResult

class BreachEngine:
    """Handles comparison logic between KPIs and Operational Actuals."""

    OPERATORS = {
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        ">": operator.gt,
        "<": operator.lt,
        "!=": operator.ne,
    }

    @classmethod
    def calculate_penalty(cls, kpi: Dict[str, Any], actual_val: float) -> float:
        """Calculate penalty based on the deviation from threshold."""
        threshold = kpi.get("value_min", 0)
        consequence_val = float(kpi.get("consequence_value") or 0.0)
        # Check both fields for penalty description
        penalty_desc = (str(kpi.get("consequence", "")) + " " + str(kpi.get("consequence_unit", ""))).lower()
        
        # Linear scaling: e.g. "$1,000 per percentage point below target"
        if "per percentage point" in penalty_desc:
            deviation = max(0, threshold - actual_val)
            return round(deviation * consequence_val, 2)
        
        # Hourly scaling: e.g. "$500 per hour over threshold"
        if "per hour" in penalty_desc:
            deviation = max(0, actual_val - threshold)
            return round(deviation * consequence_val, 2)
            
        return consequence_val

    @classmethod
    def check_breach(cls, kpi: Dict[str, Any], actual: Dict[str, Any], sample_count: int = 1) -> BreachResult:
        """Compare actual performance against KPI threshold."""
        op_str = kpi.get("operator")
        threshold = kpi.get("value_min")
        actual_val = actual.get("value")
        
        if threshold is None and op_str != "between":
            # If no threshold is defined, we can't breach it (or it's on track by default)
            is_on_track = True
        elif op_str == "between":
            val_max = kpi.get("value_max")
            if threshold is None or val_max is None:
                is_on_track = True
            else:
                is_on_track = threshold <= actual_val <= val_max
        elif op_str in cls.OPERATORS:
            is_on_track = cls.OPERATORS[op_str](actual_val, threshold)
        else:
            is_on_track = True 

        penalty_triggered = None
        penalty_amount = 0.0
        if not is_on_track:
            penalty_triggered = kpi.get("trigger_condition")
            penalty_amount = cls.calculate_penalty(kpi, actual_val)

        return BreachResult(
            contract_id=kpi["contract_id"],
            kpi_id=kpi["kpi_id"],
            actual_value=actual_val,
            threshold_value=threshold,
            operator=op_str or "N/A",
            is_breach=not is_on_track,
            penalty_triggered=penalty_triggered,
            penalty_amount=penalty_amount,
            remediation=kpi.get("remediation"),
            remediation_sla=kpi.get("remediation_sla"),
            sample_count=sample_count
        )


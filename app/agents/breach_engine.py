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
    def check_breach(cls, kpi: Dict[str, Any], actual: Dict[str, Any]) -> BreachResult:
        """
        Compare actual performance against KPI threshold.
        
        A breach occurs if the target condition is FALSE.
        Target: "Delivery Delay <= 4 hours"
        If Actual is 6 hours: 6 <= 4 is FALSE -> Breach.
        """
        op_str = kpi.get("operator")
        threshold = kpi.get("value_min")
        actual_val = actual.get("value")
        
        if op_str == "between":
            val_max = kpi.get("value_max")
            is_on_track = threshold <= actual_val <= val_max
        elif op_str in cls.OPERATORS:
            is_on_track = cls.OPERATORS[op_str](actual_val, threshold)
        else:
            # Fallback for unknown operators or text-based KPIs
            is_on_track = True 

        # Penalty logic
        penalty_triggered = None
        penalty_amount = 0.0
        if not is_on_track:
            penalty_triggered = kpi.get("trigger_condition")
            # Simple linear penalty if consequence is provided
            consequence = kpi.get("consequence_value")
            if consequence:
                penalty_amount = consequence

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
            remediation_sla=kpi.get("remediation_sla")
        )


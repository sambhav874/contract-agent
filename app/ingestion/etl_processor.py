"""Deterministic ETL processor for mapping raw data to KPIs."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.db.mongodb import MongoDB
from app.db.models import OperationalActual

def get_by_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve a value from a dict using dot notation (e.g., 'reading.value')."""
    if not path:
        return None
    
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

class ETLProcessor:
    """Processes raw records into operational actuals using mapping rules."""

    @staticmethod
    async def process_contract_actuals(contract_id: str) -> Dict[str, int]:
        """Process all pending raw actuals for a specific contract."""
        pending = await MongoDB.get_pending_raw_actuals(contract_id)
        rules = await MongoDB.get_mapping_rules(contract_id)
        
        if not pending:
            return {"processed": 0, "skipped": 0, "errors": 0}
        
        stats = {"processed": 0, "skipped": 0, "errors": 0}
        
        for raw in pending:
            source = raw.get("source", "")
            # Find ALL matching rules (exact or prefix)
            matching_rules = [r for r in rules if source.startswith(r["source_match"])]
            
            if not matching_rules:
                stats["skipped"] += 1
                continue
                
            success_count = 0
            for rule in matching_rules:
                try:
                    # Apply mappings
                    mappings = rule.get("field_mappings", {})
                    raw_data = raw.get("data", {})
                    
                    # Extract value (required)
                    val_path = mappings.get("value")
                    value = get_by_path(raw_data, val_path) if val_path else raw_data.get("value")
                    
                    if value is None:
                        stats["errors"] += 1
                        continue
                    
                    # Extract timestamp (optional)
                    ts_path = mappings.get("timestamp")
                    timestamp = get_by_path(raw_data, ts_path) if ts_path else raw_data.get("timestamp")
                    if not timestamp:
                        timestamp = datetime.now().isoformat()
                    
                    # Extract unit (optional)
                    unit_path = mappings.get("unit")
                    unit = get_by_path(raw_data, unit_path) if unit_path else raw_data.get("unit")
                    if not unit:
                        unit = "unit" # Default
                    
                    # Create OperationalActual
                    actual = OperationalActual(
                        actual_id=str(uuid4()),
                        contract_id=contract_id,
                        kpi_id=rule["kpi_id"],
                        value=float(value),
                        unit=str(unit),
                        timestamp=str(timestamp),
                        source=f"etl:{source}",
                        metadata={"raw_id": raw["raw_id"]}
                    )
                    
                    # Persist
                    await MongoDB.insert_actual(actual.model_dump())
                    stats["processed"] += 1
                    success_count += 1
                    
                except Exception as e:
                    import logging
                    logging.error(f"ETL Error for raw_id {raw.get('raw_id')} with rule {rule.get('rule_id')}: {str(e)}")
                    stats["errors"] += 1
            
            # Mark raw record as processed or error based on success
            new_status = "processed" if success_count > 0 else "error"
            await MongoDB.update_raw_actual_status(raw["raw_id"], new_status)
                
        return stats

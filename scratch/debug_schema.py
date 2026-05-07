from app.db.models import KPIExtractionOutput
import json

print(json.dumps(KPIExtractionOutput.model_json_schema(), indent=2))

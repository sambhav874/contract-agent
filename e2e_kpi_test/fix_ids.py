import os
import json
import csv

granularity_dir = "e2e_kpi_test/granularity"

for filename in os.listdir(granularity_dir):
    filepath = os.path.join(granularity_dir, filename)
    if filename.endswith(".csv"):
        with open(filepath, "r") as f:
            lines = f.readlines()
        if not lines: continue
        # Fix header if sed messed it up
        lines[0] = lines[0].replace("KPI-id", "kpi_id").replace("KPI-ID", "kpi_id")
        # Fix content: kpi_ -> KPI-, then uppercase the whole thing (carefully)
        new_lines = [lines[0]]
        for line in lines[1:]:
            parts = line.split(",")
            if parts:
                parts[0] = parts[0].replace("kpi_", "KPI-").replace("KPI-", "KPI-").upper()
                new_lines.append(",".join(parts))
        with open(filepath, "w") as f:
            f.writelines(new_lines)
            
    elif filename.endswith(".json"):
        with open(filepath, "r") as f:
            data = json.load(f)
        if "kpi_id" in data:
            data["kpi_id"] = data["kpi_id"].replace("kpi_", "KPI-").upper()
        elif "KPI-id" in data:
            val = data.pop("KPI-id")
            data["kpi_id"] = val.replace("kpi_", "KPI-").upper()
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
print("Fix complete.")

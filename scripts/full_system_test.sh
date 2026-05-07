#!/bin/bash

# Configuration
CONTRACT_PATH="tests/fixtures/airport_food.md"
CONTRACT_ID="FINAL-TEST-GUARDIAN"
OUTPUT_FILE="test_results_complete.txt"
PYTHON="./venv/bin/python3"

# Initialize output file
echo "=== CONTRACT GUARDIAN FINAL VALIDATION ===" > $OUTPUT_FILE
echo "Timestamp: $(date)" >> $OUTPUT_FILE
echo "Contract: $CONTRACT_PATH" >> $OUTPUT_FILE
echo "------------------------------------------" >> $OUTPUT_FILE

echo "[1/5] Ingesting Contract..."
$PYTHON cli.py ingest $CONTRACT_PATH --id $CONTRACT_ID --overwrite >> $OUTPUT_FILE 2>&1

echo "[2/5] Analysing KPIs (LLM Extraction)..."
# Using --sync for direct output
$PYTHON cli.py analyse $CONTRACT_ID --intent kpi --sync >> $OUTPUT_FILE 2>&1

echo "[3/5] Saving KPIs to Vault..."
$PYTHON cli.py save-kpis $CONTRACT_ID >> $OUTPUT_FILE 2>&1

echo "[4/5] Ingesting Structured Performance Data..."
# Create a robust discovery python snippet
TEMP_JSON=$(mktemp)
$PYTHON -c "
import asyncio, json, os, sys
sys.path.append(os.getcwd())
from app.db.mongodb import MongoDB
async def run():
    await MongoDB.connect()
    kpis = await MongoDB.get_kpis('$CONTRACT_ID')
    mapping = {k['name']: k['kpi_id'] for k in kpis}
    # Look for partial matches
    temp_id = next((v for k,v in mapping.items() if 'Temperature' in k), None)
    uptime_id = next((v for k,v in mapping.items() if 'Uptime' in k), None)
    print(json.dumps({'temp': temp_id, 'uptime': uptime_id}))
    await MongoDB.disconnect()
asyncio.run(run())
" > $TEMP_JSON

TEMP_ID=$(cat $TEMP_JSON | jq -r '.temp')
UPTIME_ID=$(cat $TEMP_JSON | jq -r '.uptime')

echo "Discovered IDs: Temp=$TEMP_ID, Uptime=$UPTIME_ID" >> $OUTPUT_FILE

# Ingest breach data for temperature (115F < 140F)
$PYTHON cli.py ingest-actuals $CONTRACT_ID --kpi-id "$TEMP_ID" --value 115 --unit "F" >> $OUTPUT_FILE 2>&1
# Ingest compliance data for uptime (99.5% > 98%)
$PYTHON cli.py ingest-actuals $CONTRACT_ID --kpi-id "$UPTIME_ID" --value 99.5 --unit "%" >> $OUTPUT_FILE 2>&1

echo "[5/5] Checking Breaches and Final Result..."
$PYTHON cli.py check-breaches $CONTRACT_ID >> $OUTPUT_FILE 2>&1

echo "------------------------------------------" >> $OUTPUT_FILE
echo "VALIDATION COMPLETE." >> $OUTPUT_FILE

# Clean up
rm $TEMP_JSON

# Final Output
cat $OUTPUT_FILE

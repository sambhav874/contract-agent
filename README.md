# Contract Guardian

CLI-based AI agent for legal contract analysis using Gemini AI, Voyage AI embeddings, and MongoDB. Now featuring a premium **Agentic Monitoring Dashboard**.

## 🚀 Dashboard (Premium UI)

The project now includes a high-fidelity monitoring dashboard for real-time KPI tracking and breach remediation.

### 1. Start the Backend API
```bash
python cli.py serve --port 8080
```

### 2. Start the Frontend
```bash
cd frontend
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

## Prerequisites

- Python 3.11+
- Docker Compose (for MongoDB and RabbitMQ)
- Google AI Studio API key (Gemini)
- Voyage AI API key

## Setup

```bash
# Clone and setup
cd contract-agent
cp .env.example .env
# Edit .env and add your API keys

# Install dependencies
pip install -r requirements.txt

# Start infrastructure (MongoDB + RabbitMQ)
docker compose up -d

# Create MongoDB Atlas Vector Search index
# Run the command printed by: python cli.py list --init-index
```

## Usage

```bash
# Ingest a contract
python cli.py ingest ./contracts/vendor_agreement.md --name "Vendor Agreement 2025"

# List contracts
python cli.py list

# Analyze with different intents
python cli.py analyse <contract_id> --intent risk --sync
python cli.py analyse <contract_id> --intent kpi --sync
python cli.py analyse <contract_id> --intent clause --sync
python cli.py analyse <contract_id> --intent obligations --sync
python cli.py analyse <contract_id> --intent summary --mode plain --sync
python cli.py analyse <contract_id> --intent redflags --sync
python cli.py analyse <contract_id> --intent auto --q "your question"

# Free-form query
python cli.py query <contract_id> --q "What is the notice period?"

# Export results
python cli.py export <job_id> --format json --output result.json
```

## Architecture

- **Gemini 1.5 Pro**: Deep analysis and reasoning
- **Gemini 2.0 Flash**: Intent routing, fast classification
- **Voyage AI voyage-3**: Contract and chunk embeddings
- **MongoDB Atlas**: Vector search + document store
- **RabbitMQ + Celery**: Async job processing
- **Rich**: Terminal UI formatting

## Directory Structure

```
contract-agent/
├── cli.py                 # CLI entry point
├── app/
│   ├── config.py          # Settings
│   ├── db/                # MongoDB connection, models
│   ├── ingestion/         # Parser, chunker, embedder
│   ├── retrieval/         # Hybrid search
│   ├── routing/           # Intent classification
│   ├── agents/            # Analysis agents
│   ├── synthesis/         # Output synthesis
│   ├── llm/               # Gemini client
│   └── tasks/             # Celery tasks
├── prompts/               # Agent prompts
└── tests/                 # Fixtures and tests
```

## Testing

```bash
pytest tests/ -v
```

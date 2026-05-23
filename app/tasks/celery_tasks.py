"""Celery task definitions."""

from celery import Celery
from celery.signals import worker_init
from asgiref.sync import async_to_sync

from app.config import settings
from app.db.mongodb import MongoDB


# Celery setup
celery_app = Celery(
    "contract_agent",
    broker=settings.rabbitmq_url,
    backend=settings.mongodb_uri,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@worker_init.connect
def init_worker(*args, **kwargs):
    """Initialize MongoDB connection on worker startup."""
    import asyncio
    asyncio.run(MongoDB.connect())


@celery_app.task(bind=True, max_retries=3)
def ingest_contract(self, file_path: str, name: str) -> dict:
    """
    Ingest a contract file.

    Args:
        file_path: Path to the Markdown file
        name: Contract name

    Returns:
        Contract metadata dict
    """
    try:
        from app.ingestion.parser import parse_contract
        from app.ingestion.chunker import hierarchical_chunk
        from app.ingestion.embedder import get_embedding_service
        from app.db.mongodb import MongoDB
        from app.db.models import StructuralMap

        # Parse contract
        metadata, structural_map, text = async_to_sync(parse_contract)(file_path, name)

        # Chunk document
        chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)

        # Embed chunks
        embedder = get_embedding_service()
        embedded_chunks = async_to_sync(embedder.embed_chunks)(chunks)

        # Store in MongoDB
        async_to_sync(MongoDB.insert_contract)(metadata)
        async_to_sync(MongoDB.insert_chunks)(embedded_chunks)

        return metadata.model_dump()

    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def analyze_contract(
    self,
    contract_id: str,
    intent: str,
    user_query: str | None = None,
) -> dict:
    """
    Analyze a contract.

    Args:
        contract_id: Contract ID
        intent: Analysis intent
        user_query: Optional user query

    Returns:
        Analysis result dict
    """
    try:
        from app.routing.intent_router import route_intent
        from app.agents.risk_agent import RiskAgent
        from app.agents.kpi_agent import KPIAgent
        from app.agents.clause_agent import ClauseAgent
        from app.agents.obligation_agent import ObligationAgent
        from app.agents.summary_agent import SummaryAgent
        from app.agents.redflag_agent import RedFlagAgent
        from app.synthesis.synthesiser import synthesise_output
        from app.db.mongodb import MongoDB

        # Get contract
        contract = async_to_sync(MongoDB.get_contract)(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # Route intent
        query_plan = async_to_sync(route_intent)(intent, user_query)

        # Select agent
        agent_map = {
            "risk": RiskAgent,
            "kpi": KPIAgent,
            "clause": ClauseAgent,
            "obligations": ObligationAgent,
            "summary": SummaryAgent,
            "redflags": RedFlagAgent,
        }

        agent_class = agent_map.get(intent, RiskAgent)
        agent = agent_class()

        # Run analysis
        output = async_to_sync(agent.analyze)(query_plan, contract_id, user_query or "")

        # Synthesize
        result = async_to_sync(synthesise_output)(output)

        return result

    except Exception as e:
        raise self.retry(exc=e, countdown=60)

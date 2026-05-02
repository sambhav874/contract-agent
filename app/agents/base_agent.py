"""Base agent with ReAct loop and self-correction."""

import json
from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.db.models import BaseAnalysisOutput
from app.llm.gemini_client import call_gemini
from app.retrieval.retriever import format_chunks_for_context, get_retriever


class BaseAgent(ABC):
    """Base class for all analysis agents."""

    output_schema: Type[BaseModel]
    prompt_file: str

    def __init__(self):
        self.retriever = get_retriever()
        self.max_self_correct_attempts = 2

    @abstractmethod
    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> BaseAnalysisOutput:
        """Run analysis with ReAct loop."""
        pass

    def load_prompt(self) -> str:
        """Load prompt from file."""
        try:
            with open(self.prompt_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            return self._default_prompt()

    def _default_prompt(self) -> str:
        """Default prompt if file not found."""
        return """Analyze the contract and provide structured output.
Only use information from the provided contract chunks.
Every finding must cite the chunk_id and structural_path.
If a clause is not found, state it was not found - do not infer.
Express uncertainty with confidence scores below 0.7.
Flag items below 0.5 confidence for human review."""

    async def self_correct(
        self,
        response: dict[str, Any],
        error: ValidationError,
        context_chunks: list[dict[str, Any]],
    ) -> BaseAnalysisOutput:
        """Attempt self-correction on validation failure."""
        for attempt in range(self.max_self_correct_attempts):
            try:
                correction_prompt = f"""The previous response failed validation:
{error.error_count()}

Response: {json.dumps(response, default=str)}

Please correct the response to match the expected schema."""

                corrected = await call_gemini(
                    model=settings.gemini_fast_model,
                    system_prompt=self.load_prompt(),
                    user_message=correction_prompt,
                    response_schema=self.output_schema.model_json_schema(),
                    temperature=0.0,
                )
                return self.output_schema.model_validate(corrected)

            except ValidationError:
                if attempt == self.max_self_correct_attempts - 1:
                    raise
                continue

        raise error

    async def _retrieve_and_analyze(
        self,
        contract_id: str,
        user_query: str,
        query_plan: Any,
        max_rounds: int = 3,
        top_k: int = 10,
    ) -> BaseAnalysisOutput:
        """Internal retrieval and analysis loop."""
        context_chunks: list[dict[str, Any]] = []

        for round_num in range(max_rounds):
            # Retrieve relevant chunks
            new_chunks = await self.retriever.fetch(
                contract_id=contract_id,
                query=user_query,
                tags=query_plan.priority_section_tags,
                levels=query_plan.chunk_levels,
                top_k=top_k,
            )
            context_chunks.extend(new_chunks)

            # Format context
            context_text = format_chunks_for_context(context_chunks)

            # Call LLM
            response = await call_gemini(
                model=settings.gemini_analysis_model,
                system_prompt=self.load_prompt(),
                user_message=f"Context:\n{context_text}\n\nQuery: {user_query}",
                response_schema=self.output_schema.model_json_schema(),
                temperature=0.0,
            )

            # Validate output
            try:
                output = self.output_schema.model_validate(response)
                
                # If the agent says it needs more context, and we have rounds left, continue
                if output.needs_more_context and round_num < max_rounds - 1:
                    # Update the query for the next round if provided
                    if output.additional_tags_needed:
                        query_plan.priority_section_tags.extend(output.additional_tags_needed)
                    continue
                
                return output
            except ValidationError as e:
                if round_num == max_rounds - 1:
                    # Last round - try self-correction
                    return await self.self_correct(response, e, context_chunks)
                continue

            # Check if more context needed
            if not response.get("needs_more_context", False):
                break

            # Update tags based on agent's needs
            if response.get("additional_tags_needed"):
                query_plan.priority_section_tags = response["additional_tags_needed"]

        # Fallback - return best effort
        return self.output_schema.model_validate(response)


def format_chunks(chunks: list[dict[str, Any]]) -> str:
    """Format chunks for LLM context."""
    return format_chunks_for_context(chunks)

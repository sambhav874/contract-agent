"""Base agent with ReAct loop, self-correction, and map-pass support."""

import json
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.db.models import BaseAnalysisOutput
from app.llm.gemini_client import call_gemini
from app.retrieval.retriever import format_chunks_for_context, get_retriever


class BaseAgent(ABC):
    """
    Base class for all analysis agents.

    Implements:
    - Multi-round ReAct retrieval loop with deduplication
    - Map pass (broad survey before targeted analysis)
    - Schema-guided LLM calls
    - Automatic self-correction on validation failure
    - Context budget management to avoid token overflow
    """

    output_schema: Type[BaseModel]
    prompt_file: str

    # Subclasses can override these defaults
    DEFAULT_TOP_K: int = 15
    MAX_CONTEXT_TOKENS: int = 90_000   # ~90k chars is safe for Gemini 1.5 Pro
    SELF_CORRECT_ATTEMPTS: int = 2
    REQUIRE_CITATIONS: bool = True

    def __init__(self):
        self.retriever = get_retriever()

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    @abstractmethod
    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> BaseAnalysisOutput:
        """Run analysis. Implemented by each agent subclass."""
        pass

    def load_prompt(self) -> str:
        """Load system prompt from file, fall back to generic."""
        try:
            with open(self.prompt_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            return self._default_prompt()

    # ------------------------------------------------------------------ #
    # Core retrieval + analysis loop                                        #
    # ------------------------------------------------------------------ #

    async def _retrieve_and_analyze(
        self,
        contract_id: str,
        user_query: str,
        query_plan: Any,
        max_rounds: int = 3,
        top_k: int | None = None,
    ) -> BaseAnalysisOutput:
        """
        Multi-round retrieval and analysis loop.

        Round 0 (optional map pass): Fetch macro chunks across all sections to
        build a broad picture of the contract structure before targeted retrieval.

        Rounds 1-N (targeted): Retrieve meso/micro chunks based on priority tags,
        accumulate context, call LLM, check if more context is needed.
        """
        if top_k is None:
            top_k = self.DEFAULT_TOP_K

        seen_chunk_ids: set[str] = set()
        context_chunks: list[dict[str, Any]] = []
        last_response: dict[str, Any] = {}

        # ── Optional map pass (broad macro survey) ──────────────────────
        if getattr(query_plan, "map_pass_required", False):
            map_chunks = await self.retriever.fetch(
                contract_id=contract_id,
                query=user_query,
                tags=None,           # no tag filter → broad sweep
                levels=["macro"],
                top_k=20,
            )
            for chunk in map_chunks:
                cid = chunk.get("chunk_id", "")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    context_chunks.append(chunk)

        # ── Targeted retrieval rounds ────────────────────────────────────
        current_tags = list(getattr(query_plan, "priority_section_tags", []) or [])
        current_levels = list(getattr(query_plan, "chunk_levels", ["meso"]) or ["meso"])

        for round_num in range(max_rounds):
            new_chunks = await self.retriever.fetch(
                contract_id=contract_id,
                query=user_query,
                tags=current_tags if current_tags else None,
                levels=current_levels,
                top_k=top_k,
            )

            added = 0
            for chunk in new_chunks:
                cid = chunk.get("chunk_id", "")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    context_chunks.append(chunk)
                    added += 1

            # Respect context budget
            context_text = self._build_context(context_chunks)
            if len(context_text) > self.MAX_CONTEXT_TOKENS:
                # Trim oldest non-structural chunks
                context_chunks = self._trim_context(context_chunks)
                context_text = self._build_context(context_chunks)

            # Build prompt with round awareness
            round_instruction = ""
            if round_num > 0:
                round_instruction = (
                    f"\n\nCRITICAL: This is round {round_num+1} of retrieval. "
                    "You previously requested more context. I have now provided it. "
                    "You MUST return the COMPLETE JSON object including ALL previously identified items "
                    "plus any new findings. Do NOT return a conversational summary."
                )

            # Build citation instruction if enabled
            citation_instruction = ""
            if self.REQUIRE_CITATIONS:
                chunk_ids = [c.get("chunk_id") for c in context_chunks if c.get("chunk_id")]
                if chunk_ids:
                    citation_instruction = (
                        "\n\nCITATION RULE: Every claim MUST cite source chunk(s) using "
                        f"[CHUNK: <id>] format. Available IDs: {', '.join(chunk_ids)}. "
                        "Claims without a valid citation will be rejected."
                    )

            # Call LLM
            last_response = await call_gemini(
                model=settings.gemini_analysis_model,
                system_prompt=self.load_prompt(),
                user_message=(
                    f"RETRIEVED CONTRACT CONTEXT:\n{context_text}\n"
                    f"{round_instruction}{citation_instruction}\n\n---\n"
                    f"USER QUERY: {user_query}"
                ),
                response_schema=self.output_schema.model_json_schema(),
                temperature=0.0,
                enable_thinking=True,
            )

            # Try to validate
            try:
                output = self.output_schema.model_validate(last_response)

                # Post-validate citations if enabled
                if self.REQUIRE_CITATIONS:
                    validation_error = self._validate_citations(last_response, context_chunks)
                    if validation_error:
                        raise ValidationError.from_exception_data(
                            title="CitationError",
                            line_errors=[{
                                "loc": ("citations",),
                                "input": last_response,
                                "type": "value_error",
                                "ctx": {"error": ValueError(validation_error)},
                            }],
                        )

                # Agent signals it needs more data
                if output.needs_more_context and round_num < max_rounds - 1:
                    extra_tags = getattr(output, "additional_tags_needed", []) or []
                    if extra_tags:
                        current_tags = list(set(current_tags + extra_tags))
                    # Widen chunk levels on subsequent rounds
                    if "macro" not in current_levels:
                        current_levels.append("macro")
                    continue

                return output

            except ValidationError as e:
                if round_num == max_rounds - 1:
                    return await self._self_correct(last_response, e, context_chunks)
                continue  # try again with more context

        # Last-chance validate
        try:
            return self.output_schema.model_validate(last_response)
        except ValidationError as e:
            return await self._self_correct(last_response, e, context_chunks)

    # ------------------------------------------------------------------ #
    # Self-correction                                                        #
    # ------------------------------------------------------------------ #

    async def _self_correct(
        self,
        bad_response: dict[str, Any],
        error: ValidationError,
        context_chunks: list[dict[str, Any]],
    ) -> BaseAnalysisOutput:
        """Ask the LLM to fix its own malformed output."""
        schema_str = json.dumps(self.output_schema.model_json_schema(), indent=2)
        correction_prompt = (
            f"Your previous response failed schema validation.\n\n"
            f"VALIDATION ERRORS:\n{error}\n\n"
            f"BAD RESPONSE:\n{json.dumps(bad_response, default=str)[:4000]}\n\n"
            f"REQUIRED JSON SCHEMA:\n{schema_str}\n\n"
            f"Return ONLY a corrected JSON object that matches the schema exactly. "
            f"Do not add any explanation outside the JSON."
        )

        for attempt in range(self.SELF_CORRECT_ATTEMPTS):
            try:
                corrected = await call_gemini(
                    model=settings.gemini_fast_model,
                    system_prompt=self.load_prompt(),
                    user_message=correction_prompt,
                    response_schema=self.output_schema.model_json_schema(),
                    temperature=0.0,
                    enable_thinking=True,
                )
                return self.output_schema.model_validate(corrected)
            except ValidationError:
                if attempt == self.SELF_CORRECT_ATTEMPTS - 1:
                    # Return a safe default rather than crashing the pipeline
                    return self.output_schema.model_construct(
                        needs_more_context=True,
                        additional_tags_needed=["self_correction_failed"],
                    )

        return self.output_schema.model_construct(needs_more_context=True)

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #

    def _build_context(self, chunks: list[dict[str, Any]]) -> str:
        return format_chunks_for_context(chunks)

    def _validate_citations(
        self, response: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> str | None:
        """
        Validate that any [CHUNK: <id>] citations in the response exist in context.
        Returns an error string if any citation is invalid, None otherwise.
        """
        import re as _re
        text = json.dumps(response, default=str, ensure_ascii=False)
        cited_ids = set(_re.findall(r"\[CHUNK:\s*([^\]]+)\]", text))
        valid_ids = {c.get("chunk_id") for c in chunks if c.get("chunk_id")}
        invalid = cited_ids - valid_ids
        if invalid:
            return f"Invalid chunk citations: {', '.join(invalid)}"
        return None

    def _trim_context(
        self,
        chunks: list[dict[str, Any]],
        keep_ratio: float = 0.75,
    ) -> list[dict[str, Any]]:
        """Drop lower-priority chunks to stay within context budget."""
        # Prefer structural (macro) chunks; drop micro first, then meso
        level_priority = {"macro": 0, "meso": 1, "micro": 2}
        sorted_chunks = sorted(
            chunks,
            key=lambda c: level_priority.get(c.get("chunk_level", "micro"), 3),
        )
        keep = max(1, int(len(sorted_chunks) * keep_ratio))
        return sorted_chunks[:keep]

    def _default_prompt(self) -> str:
        return (
            "Analyze the contract chunks carefully. "
            "Only use information from the provided context. "
            "Cite chunk_id and structural_path for every finding. "
            "Use confidence scores below 0.7 for uncertain items. "
            "Set needs_more_context=true only if critical sections are absent."
        )

    # ── Legacy shim for tests that call .analyse() ────────────────────
    async def analyse(self, *args, **kwargs):
        return await self.analyze(*args, **kwargs)

    @classmethod
    def self_correct(cls, *args, **kwargs):
        """Legacy class-level shim used in test assertions."""
        pass
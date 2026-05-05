"""
Ragas Evaluation using Gemini and VoyageAI.
Implements Faithfulness, Answer Relevance, Context Precision, and Context Recall.

Architecture Note
-----------------
ragas.evaluate() is a *synchronous* function that internally creates its own
asyncio event loop via nest_asyncio.  If you call it from inside an already-
running asyncio.run() you get a deadlock.

The clean fix is to split the work:
  Phase 1 (async)  – retrieve contexts + generate answers  → returns a plain Dataset
  Phase 2 (sync)   – call ragas.evaluate() with that Dataset

The CLI passes the Dataset back out of the async context and calls Phase 2
synchronously.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Dict

from datasets import Dataset

from ragas import evaluate, RunConfig
from ragas.metrics import context_precision, context_recall, faithfulness, answer_relevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from pymongo import MongoClient

from app.config import settings
from app.retrieval.langchain_retriever import get_voyage_embeddings


class RagasEvaluator:
    """Evaluates RAG performance using the Ragas framework."""

    def __init__(self, model_name: str | None = None):
        # answer_relevancy uses n>1 candidates — requires gemini-2.0-flash or later,
        # NOT lite/preview models. Hard-pin to gemini-2.0-flash for the judge.
        judge_model = model_name or "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=judge_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
        self.embeddings = get_voyage_embeddings()

        # Wrap for Ragas API
        self.ragas_llm = LangchainLLMWrapper(self.llm)
        self.ragas_emb = LangchainEmbeddingsWrapper(self.embeddings)

        self.client = MongoClient(settings.mongodb_uri)
        self.db_name = settings.mongodb_db_name
        self.collection_name = "chunks"

    def _get_vector_store(self) -> MongoDBAtlasVectorSearch:
        collection = self.client[self.db_name][self.collection_name]
        return MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=self.embeddings,
            index_name="chunk_embedding_index",
            text_key="text",
            embedding_key="embedding",
        )

    async def _generate_answer(self, prompt: str) -> str:
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return str(response.content)

    # ------------------------------------------------------------------ #
    # Phase 1 – ASYNC: retrieve + generate                                #
    # ------------------------------------------------------------------ #
    async def build_eval_dataset(
        self, contract_id: str, test_set: List[Dict[str, str]]
    ) -> Dataset:
        """
        Async phase: Run retrieval and generation for each test sample.
        Returns a Hugging Face Dataset ready for ragas.evaluate().
        """
        vector_store = self._get_vector_store()

        questions: List[str] = []
        ground_truths: List[str] = []
        contexts: List[List[str]] = []
        answers: List[str] = []

        for example in test_set:
            query = example["query"]
            ground_truth = example["answer"]

            # Retrieve from MongoDB Atlas Vector Search
            docs = vector_store.similarity_search(
                query,
                k=5,
                pre_filter={"contract_id": {"$eq": contract_id}},
            )
            retrieved_texts = [d.page_content for d in docs]
            context_str = "\n".join(retrieved_texts)

            # Generate answer
            prompt = (
                f"Context:\n{context_str}\n\n"
                f"Question: {query}\n\n"
                f"Answer accurately based ONLY on context:"
            )
            prediction_text = await self._generate_answer(prompt)

            questions.append(query)
            ground_truths.append(ground_truth)
            contexts.append(retrieved_texts)
            answers.append(prediction_text)

        return Dataset.from_dict(
            {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
            }
        )

    # ------------------------------------------------------------------ #
    # Phase 2 – SYNC: score with Ragas                                    #
    # ------------------------------------------------------------------ #
    def score(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Synchronous phase: call ragas.evaluate() with a pre-built Dataset.
        Must be called OUTSIDE any asyncio.run() / event loop.
        """
        run_config = RunConfig(
            max_workers=1,
            max_wait=300,
            max_retries=10,
            timeout=300,
        )

        result = evaluate(
            dataset=dataset,
            metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
            llm=self.ragas_llm,
            embeddings=self.ragas_emb,
            run_config=run_config,
            raise_exceptions=False,
        )

        scores: Dict[str, Any] = {}
        details: List[Dict] = []

        if result is not None:
            try:
                # to_pandas() always works even if some metrics timed out (NaN for those cells)
                df = result.to_pandas()
                details = df.to_dict(orient="records")
                # Aggregate: mean of each numeric column, skipping NaN
                numeric_cols = [c for c in df.columns if df[c].dtype in ("float64", "float32")]
                scores = {col: float(df[col].mean()) for col in numeric_cols if not df[col].isna().all()}
            except Exception as exc:
                print(f"Could not parse Ragas results: {exc}")

        return {"aggregate_scores": scores, "details": details}

"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Keys
    gemini_api_key: str
    voyage_api_key: str

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "contract_agent"

    # RabbitMQ
    rabbitmq_url: str = "amqp://agent:agentpass@localhost:5672//"

    # Model Configuration
    gemini_analysis_model: str = "gemini-3.1-flash-lite-preview"
    gemini_fast_model: str = "gemini-3.1-flash-lite-preview"
    voyage_model: str = "voyage-3"

    # Processing Configuration
    max_retrieval_rounds: int = 3
    chunk_batch_size: int = 128

    # Safety Guard Configuration
    max_cost_usd: float = 5.0
    max_iterations: int = 15
    max_tokens_per_request: int = 32768

    # Logging
    log_level: str = "INFO"

    @property
    def is_local(self) -> bool:
        """Check if running in local development mode."""
        return "localhost" in self.mongodb_uri


settings = Settings()

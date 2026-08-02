"""Central configuration for IntelliDesk.

All tunables live here so the RAG pipeline, the agent, the MCP server and
the API layer stay consistent with each other.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    google_api_key: str = ""
    agent_model: str = "gpt-4.1-mini"
    max_tokens: int = 2048
    temperature: float = 0.1          # low temp: business answers should be stable

    # --- RAG ---
    chroma_dir: str = str(PROJECT_ROOT / "storage" / "chroma")
    collection_name: str = "intellidesk_kb"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 800             # characters per chunk
    chunk_overlap: int = 120          # keeps context across chunk boundaries
    top_k: int = 5                    # documents returned per retrieval
    score_threshold: float = 0.25     # drop weakly-related chunks

    # --- Business data / MCP ---
    business_db: str = str(PROJECT_ROOT / "storage" / "business.db")
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8901

    # --- Agent behaviour ---
    max_agent_iterations: int = 8     # hard stop for runaway tool loops


settings = Settings()

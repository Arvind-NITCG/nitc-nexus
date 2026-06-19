from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    database_hostname: str = Field("localhost", env="DATABASE_HOSTNAME")
    database_port: int = Field(5432, env="DATABASE_PORT")
    database_password: str = Field("", env="DATABASE_PASSWORD")
    database_name: str = Field("nitc_nexus", env="DATABASE_NAME")
    database_username: str = Field("user", env="DATABASE_USERNAME")


    semantic_model: str = Field("sentence-transformers/all-MiniLM-L6-v2", env="SEMANTIC_MODEL")
    model_dim: int = Field(384, env="MODEL_DIM")


    max_depth: int = Field(3, env="CHUNK_MAX_DEPTH")
    chunk_size: int = Field(200, env="CHUNK_SIZE")
    min_chunk_size: int = Field(50, env="MIN_CHUNK_SIZE")
    chunking_strategy: str = Field("recursive", env="CHUNKING_STRATEGY")
    overlap_size: int = Field(20, env="OVERLAP_SIZE")
    max_num_sentences: int = Field(3, env="MAX_NUM_SENTENCES")
    similarity_threshold: float = Field(0.7, env="SIMILARITY_THRESHOLD")
    max_tokens: int = Field(500, env="MAX_TOKENS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
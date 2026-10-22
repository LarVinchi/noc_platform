from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL
from pydantic import Field, SecretStr, model_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "NOC Platform API"
    ENVIRONMENT: str = "production"
    AUTH_MODE: str = "entra"
    ENTRA_TENANT_ID: str = ""
    ENTRA_API_CLIENT_ID: str = ""
    ENTRA_SPA_CLIENT_ID: str = ""
    ENTRA_SCOPE: str = "access_as_user"
    CORS_ORIGINS: list[str] = []
    MONITORING_INGEST_TOKEN: str = ""
    PLATFORM_AGENT_INGEST_TOKEN: SecretStr = SecretStr("")
    PLATFORM_AGENT_HOST_ID: str = "noc-review-host"
    PLATFORM_WARNING_PERCENT: float = Field(default=80, ge=1, le=99)
    PLATFORM_CRITICAL_PERCENT: float = Field(default=90, ge=1, le=100)
    DOCUMENT_STORAGE_ROOT: str = "private_documents"
    KNOWLEDGE_ENABLED: bool = False
    KNOWLEDGE_SERVICE_URL: str = ""
    KNOWLEDGE_SERVICE_TOKEN: SecretStr = SecretStr("")
    LINKED_DOCUMENTS_ENABLED: bool = False
    LINKED_COLLECTOR_COLLECTION_ID: str = ""
    LINKED_COLLECTOR_TOKEN: SecretStr = SecretStr("")
    LINKED_ONEDRIVE_ALLOWED_HOSTS: list[str] = []
    ENERGY_FILE_PUSH_ENABLED: bool = False
    ENERGY_FILE_PUSH_SOURCE_ID: str = "site-energy"
    ENERGY_FILE_PUSH_INTERVAL_SECONDS: int = Field(default=3600, ge=60, le=86400)
    ENERGY_ONEDRIVE_ENABLED: bool = False
    ENERGY_GRAPH_TENANT_ID: str = ""
    ENERGY_GRAPH_CLIENT_ID: str = ""
    ENERGY_GRAPH_DRIVE_ID: str = ""
    ENERGY_GRAPH_ITEM_ID: str = ""
    ENERGY_GRAPH_CLIENT_SECRET: SecretStr = SecretStr("")
    ENERGY_GRAPH_CLIENT_SECRET_FILE: str = ""
    ENERGY_SYNC_INTERVAL_SECONDS: int = Field(default=60, ge=15, le=3600)
    
    # Database configuration (Defaults to your local Docker setup)
    POSTGRES_USER: str = "noc_admin"
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5433" # We used 5433 to avoid your local pgAdmin conflict
    POSTGRES_DB: str = "noc_platform_db"

    @model_validator(mode='after')
    def valid_platform_thresholds(self):
        if self.PLATFORM_WARNING_PERCENT >= self.PLATFORM_CRITICAL_PERCENT:
            raise ValueError('Platform warning threshold must be below the critical threshold')
        return self
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Constructs the postgresql:// connection string
        return URL.create("postgresql+psycopg2", username=self.POSTGRES_USER,
                          password=self.POSTGRES_PASSWORD, host=self.POSTGRES_SERVER,
                          port=int(self.POSTGRES_PORT), database=self.POSTGRES_DB).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

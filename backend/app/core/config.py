from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

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
    DOCUMENT_STORAGE_ROOT: str = "private_documents"
    
    # Database configuration (Defaults to your local Docker setup)
    POSTGRES_USER: str = "noc_admin"
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5433" # We used 5433 to avoid your local pgAdmin conflict
    POSTGRES_DB: str = "noc_platform_db"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Constructs the postgresql:// connection string
        return URL.create("postgresql+psycopg2", username=self.POSTGRES_USER,
                          password=self.POSTGRES_PASSWORD, host=self.POSTGRES_SERVER,
                          port=int(self.POSTGRES_PORT), database=self.POSTGRES_DB).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

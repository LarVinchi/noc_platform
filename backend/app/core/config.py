from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NOC Platform API"
    
    # Database configuration (Defaults to your local Docker setup)
    POSTGRES_USER: str = "noc_admin"
    POSTGRES_PASSWORD: str = "noc_secure_password_123"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5433" # We used 5433 to avoid your local pgAdmin conflict
    POSTGRES_DB: str = "noc_platform_db"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Constructs the postgresql:// connection string
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"

settings = Settings()
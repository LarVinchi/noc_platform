from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 1. Create the SQLAlchemy Engine
# This is the core interface to the database.
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    pool_pre_ping=True, # Tests the connection before executing queries
    pool_size=10,       # Number of connections to keep open
    max_overflow=20     # Max extra connections if it gets busy
)

# 2. Create a SessionLocal class
# Each instance of this will be an actual database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create a Base class
# All of our future database models will inherit from this Base.
Base = declarative_base()

# 4. Dependency Injection for FastAPI
# We will use this function in our API routes to grab a database connection, 
# execute a query, and then safely close the connection.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
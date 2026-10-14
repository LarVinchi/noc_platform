from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from app.core.security import actor_context
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


@event.listens_for(Session, "before_flush")
def set_audit_actor(session, flush_context, instances):
    actor = actor_context.get()
    session.execute(text("SELECT set_config('noc.actor', :actor, true), "
                         "set_config('noc.verified', :verified, true), "
                         "set_config('noc.request_id', :request_id, true)"),
                    {"actor": actor["id"], "verified": str(actor["verified"]).lower(),
                     "request_id": actor["request_id"]})

# 4. Dependency Injection for FastAPI
# We will use this function in our API routes to grab a database connection, 
# execute a query, and then safely close the connection.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

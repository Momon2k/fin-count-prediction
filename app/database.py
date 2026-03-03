"""
Database connection and session management
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = None
SessionLocal = None
Base = declarative_base()


def init_db():
    """Initialize database connection"""
    global engine, SessionLocal
    
    if not settings.database_url:
        logger.warning("DATABASE_URL not configured. Database features will be disabled.")
        return False
    
    try:
        # Convert Railway's mysql:// to mysql+pymysql:// for SQLAlchemy
        database_url = settings.database_url
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
            logger.info("Converted DATABASE_URL to use PyMySQL driver")
        
        # Create engine with MySQL-specific settings
        engine = create_engine(
            database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour 23 minutes
        )
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("✓ Database connection established successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        return False


def get_db() -> Generator[Session | None, None, None]:
    """
    Dependency function to get database session
    
    Usage in FastAPI endpoints:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
    
    Returns None if database is not initialized.
    """
    if SessionLocal is None:
        # Return None instead of raising error - allows endpoints to work without DB
        yield None
        return
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database"""
    if engine is None:
        logger.warning("Cannot create tables: database not initialized")
        return False
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {e}")
        return False


def is_db_available() -> bool:
    """Check if database is available and configured"""
    return engine is not None and SessionLocal is not None

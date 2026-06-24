from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Update with your postgres username, password, host, port, and database name
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/pai"

# Create the SQLAlchemy engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a sessionmaker instance for handling database transactions
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Base class for data models to inherit from
Base = declarative_base()

# Dependency utility to manage database session lifecycles per API request
async def get_db():
    async with SessionLocal() as session:
        yield session
"""
Database configuration and connection setup.
PostgreSQL only (configured via DATABASE_URL).
"""
from sqlalchemy import create_engine
from api.db import get_database_url

DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL, future=True)

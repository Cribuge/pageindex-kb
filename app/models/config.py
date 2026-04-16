"""
System configuration key-value store.
"""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON

from core.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

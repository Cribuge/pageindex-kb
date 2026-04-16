"""
Initialize database tables and create default data.
"""
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from core.database import engine, Base
from models.document import Document, TreeNode
from models.chat import ChatSession, ChatMessage


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Database initialized.")


if __name__ == "__main__":
    init_db()

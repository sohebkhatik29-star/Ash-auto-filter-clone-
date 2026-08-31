"""Database module wrapper for clone plugins.
Provides mongo_db and mongo_client instances.
"""
from plugins.clone import mongo_db, mongo_client

__all__ = ["mongo_db", "mongo_client"]

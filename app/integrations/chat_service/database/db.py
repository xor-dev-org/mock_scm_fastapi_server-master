import os
from app.utils.postgres_db import find_one as pg_find_one
from app.utils.postgres_db import insert_one as pg_insert_one

CHAT_COLLECTION_NAME = os.getenv("CHAT_COLLECTION_NAME", "acs_chat_collection")


class PostgresChatCollection:
    def find_one(self, filter_value):
        return pg_find_one(CHAT_COLLECTION_NAME, filter_value)

    def insert_one(self, document):
        return pg_insert_one(CHAT_COLLECTION_NAME, document)


chat_collection = PostgresChatCollection()

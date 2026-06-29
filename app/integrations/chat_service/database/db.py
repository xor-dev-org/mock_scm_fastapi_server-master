import os
from app.utils.postgres_db import find_many as pg_find_many
from app.utils.postgres_db import find_one as pg_find_one
from app.utils.postgres_db import insert_one as pg_insert_one
from app.utils.postgres_db import update_one as pg_update_one

CHAT_COLLECTION_NAME = os.getenv("CHAT_COLLECTION_NAME", "acs_chat_collection")


class PostgresChatCollection:
    def find_one(self, filter_value):
        return pg_find_one(CHAT_COLLECTION_NAME, filter_value)

    def find_many(self, filter_value=None):
        return pg_find_many(CHAT_COLLECTION_NAME, filter_value)

    def insert_one(self, document):
        return pg_insert_one(CHAT_COLLECTION_NAME, document)

    def update_one(self, filter_value, update_value):
        return pg_update_one(CHAT_COLLECTION_NAME, filter_value, update_value)


chat_collection = PostgresChatCollection()

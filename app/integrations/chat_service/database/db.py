import os
from pymongo import MongoClient

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "scm_procurement")

client = MongoClient(MONGODB_URL)
database = client[DATABASE_NAME]

chat_collection = database["chat"]
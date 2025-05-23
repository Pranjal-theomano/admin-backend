from os import getenv
import os
import sys
from pymongo import MongoClient
import logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://sunny-user-test:s9AA31F9Czycw1Er@dev-test-sunnybackend.epqt7.mongodb.net/?retryWrites=true&w=majority&appName=dev-test-sunnybackend")
db_client = MongoClient(MONGO_URI)
db_name = os.getenv("DB_NAME", "sunny-dev")
db = db_client[db_name]

collection = db["users"]
voice_collection = db["voice_responses"]
chat_collection = db["proposal_interactions"]
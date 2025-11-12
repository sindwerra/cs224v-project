import certifi

from pymongo import MongoClient
from pymongo.server_api import ServerApi

from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv()
    mongodb_uri = os.getenv('MONGODB_URI')

    # Create a new client and connect to the server
    client = MongoClient(mongodb_uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=30000, server_api=ServerApi('1'))
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

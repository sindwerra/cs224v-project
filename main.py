import os

from dotenv import load_dotenv
from database import HFAgentDatabase

if __name__ == "__main__":
    load_dotenv()
    mongodb_uri = os.getenv('MONGODB_URI')
    
    if not mongodb_uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    
    # Initialize database connection
    db = HFAgentDatabase(mongodb_uri)
    
    # Test connection
    db.ping()
    
    # Insert sample data
    # db.insert_sample_data()
    
    # Display all data
    db.display_data()
    
    print("\n" + "="*60)
    print("Database operations completed successfully!")
    print("="*60)

import certifi
import uuid
from datetime import datetime, timezone
from bson import ObjectId

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError

# Database and Collection Names
DB_NAME = "HFAgent"
USERS_COLLECTION = "Users"
MESSAGES_COLLECTION = "Messages"

# ========== Utility Functions ==========

def generate_user_id():
    """Generate a unique user ID in the format usr_xxxxx"""
    unique_id = str(uuid.uuid4())[:8].replace('-', '')
    return f"usr_{unique_id}"

def validate_email(email):
    """Basic email validation"""
    if '@' in email and '.' in email.split('@')[1]:
        return True
    return False

def validate_date(date_str):
    """Validate date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

class HFAgentDatabase:
    """Database operations for HFAgent database"""
    
    def __init__(self, mongodb_uri):
        """Initialize MongoDB client and connect to HFAgent database"""
        self.client = MongoClient(
            mongodb_uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            server_api=ServerApi('1')
        )
        self.db = self.client[DB_NAME]
        self.users = self.db[USERS_COLLECTION]
        self.messages = self.db[MESSAGES_COLLECTION]
    
    def ping(self):
        """Test database connection"""
        try:
            self.client.admin.command('ping')
            print("✓ Successfully connected to MongoDB!")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            raise e
    
    # ========== User Operations ==========
    
    def create_user(self, user_id, role, profile, contact):
        """Create a new user document"""
        user_doc = {
            "_id": user_id,
            "role": role,
            "profile": profile,
            "contact": contact,
            "created_at": datetime.now(timezone.utc)
        }
        
        try:
            result = self.users.insert_one(user_doc)
            print(f"✓ Created user: {user_id}")
            return result.inserted_id
        except PyMongoError as e:
            print(f"✗ Error creating user: {e}")
            raise e
    
    def get_user(self, user_id):
        """Get a user by ID"""
        try:
            user = self.users.find_one({"_id": user_id})
            return user
        except PyMongoError as e:
            print(f"✗ Error fetching user: {e}")
            raise e
    
    def get_user_by_email(self, email):
        """Get a user by email address"""
        try:
            user = self.users.find_one({"contact.email": email})
            return user
        except PyMongoError as e:
            print(f"✗ Error fetching user by email: {e}")
            raise e
    
    def get_user_by_phone(self, phone):
        """Get a user by phone number"""
        try:
            user = self.users.find_one({"contact.phone": phone})
            return user
        except PyMongoError as e:
            print(f"✗ Error fetching user by phone: {e}")
            raise e
    
    def get_all_users(self):
        """Get all users"""
        try:
            users = list(self.users.find())
            return users
        except PyMongoError as e:
            print(f"✗ Error fetching users: {e}")
            raise e
    
    def update_user(self, user_id, update_fields):
        """Update user fields"""
        try:
            result = self.users.update_one(
                {"_id": user_id},
                {"$set": update_fields}
            )
            if result.modified_count > 0:
                print(f"✓ Updated user: {user_id}")
            return result
        except PyMongoError as e:
            print(f"✗ Error updating user: {e}")
            raise e
    
    def delete_user(self, user_id):
        """Delete a user by ID"""
        try:
            result = self.users.delete_one({"_id": user_id})
            if result.deleted_count > 0:
                print(f"✓ Deleted user: {user_id}")
            return result
        except PyMongoError as e:
            print(f"✗ Error deleting user: {e}")
            raise e
    
    # ========== Message Operations ==========
    
    def create_message(self, user_id, user_text, assistant_text, model="gpt-4o-mini", 
                      message_type="conversation", metadata=None):
        """
        Create a new message document
        
        Args:
            user_id: User ID
            user_text: User's message text
            assistant_text: Assistant's response text
            model: Model name used
            message_type: Type of message - "conversation", "recommendation", "risk_assessment", etc.
            metadata: Additional metadata (e.g., recommendation details, risk flags)
        """
        now = datetime.now(timezone.utc)
        
        message_doc = {
            "user_id": user_id,
            "message_type": message_type,
            "user": {
                "text": user_text,
                "ts": now
            },
            "assistant": {
                "text": assistant_text,
                "ts": now,
                "meta": {"model": model}
            },
            "created_at": now,
            "updated_at": now
        }
        
        # Add metadata if provided
        if metadata:
            message_doc["metadata"] = metadata
        
        try:
            result = self.messages.insert_one(message_doc)
            print(f"✓ Created message: {result.inserted_id} for user: {user_id}")
            return result.inserted_id
        except PyMongoError as e:
            print(f"✗ Error creating message: {e}")
            raise e
    
    def get_message(self, message_id):
        """Get a message by ID"""
        try:
            message = self.messages.find_one({"_id": ObjectId(message_id)})
            return message
        except PyMongoError as e:
            print(f"✗ Error fetching message: {e}")
            raise e
    
    def get_messages_by_user(self, user_id, message_type=None):
        """
        Get all messages for a specific user
        
        Args:
            user_id: User ID
            message_type: Optional filter by message type (e.g., "conversation", "recommendation")
        """
        try:
            query = {"user_id": user_id}
            if message_type:
                query["message_type"] = message_type
            messages = list(self.messages.find(query).sort("created_at", 1))
            return messages
        except PyMongoError as e:
            print(f"✗ Error fetching messages: {e}")
            raise e
    
    def get_all_messages(self):
        """Get all messages"""
        try:
            messages = list(self.messages.find().sort("created_at", 1))
            return messages
        except PyMongoError as e:
            print(f"✗ Error fetching messages: {e}")
            raise e
    
    def update_message(self, message_id, update_fields):
        """Update message fields"""
        update_fields["updated_at"] = datetime.now(timezone.utc)
        try:
            result = self.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": update_fields}
            )
            if result.modified_count > 0:
                print(f"✓ Updated message: {message_id}")
            return result
        except PyMongoError as e:
            print(f"✗ Error updating message: {e}")
            raise e
    
    def delete_message(self, message_id):
        """Delete a message by ID"""
        try:
            result = self.messages.delete_one({"_id": ObjectId(message_id)})
            if result.deleted_count > 0:
                print(f"✓ Deleted message: {message_id}")
            return result
        except PyMongoError as e:
            print(f"✗ Error deleting message: {e}")
            raise e
    
    # ========== Recommendation Operations ==========
    
    def create_recommendation(self, user_id, recommendation_text, recommendation_data, 
                            status="generated", model="gpt-4o-mini"):
        """
        Create a recommendation message for a patient
        
        Args:
            user_id: Patient's user ID
            recommendation_text: Human-readable recommendation text
            recommendation_data: Structured recommendation data (dict with medications, dosages, etc.)
            status: Recommendation status - "generated", "pending_approval", "approved", "rejected"
            model: Model used to generate recommendation
        
        Returns:
            Inserted message ID
        """
        metadata = {
            "recommendation": recommendation_data,
            "status": status,
            "generated_at": datetime.now(timezone.utc)
        }
        
        return self.create_message(
            user_id=user_id,
            user_text="[System: Recommendation generated based on clinical assessment]",
            assistant_text=recommendation_text,
            model=model,
            message_type="recommendation",
            metadata=metadata
        )
    
    def get_recommendations_by_user(self, user_id, status=None):
        """
        Get all recommendations for a specific user
        
        Args:
            user_id: Patient's user ID
            status: Optional filter by status ("generated", "approved", etc.)
        
        Returns:
            List of recommendation messages
        """
        try:
            query = {"user_id": user_id, "message_type": "recommendation"}
            if status:
                query["metadata.status"] = status
            recommendations = list(self.messages.find(query).sort("created_at", -1))
            return recommendations
        except PyMongoError as e:
            print(f"✗ Error fetching recommendations: {e}")
            raise e
    
    def get_latest_recommendation(self, user_id):
        """Get the most recent recommendation for a user"""
        try:
            recommendation = self.messages.find_one(
                {"user_id": user_id, "message_type": "recommendation"},
                sort=[("created_at", -1)]
            )
            return recommendation
        except PyMongoError as e:
            print(f"✗ Error fetching latest recommendation: {e}")
            raise e
    
    def update_recommendation_status(self, message_id, new_status, approved_by=None):
        """
        Update the status of a recommendation
        
        Args:
            message_id: Recommendation message ID
            new_status: New status ("approved", "rejected", etc.)
            approved_by: Optional user ID of approver (e.g., physician ID)
        """
        try:
            update_data = {
                "metadata.status": new_status,
                "updated_at": datetime.now(timezone.utc)
            }
            if approved_by:
                update_data["metadata.approved_by"] = approved_by
                update_data["metadata.approved_at"] = datetime.now(timezone.utc)
            
            result = self.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": update_data}
            )
            if result.modified_count > 0:
                print(f"✓ Updated recommendation status: {message_id} -> {new_status}")
            return result
        except PyMongoError as e:
            print(f"✗ Error updating recommendation: {e}")
            raise e
    
    # ========== Utility Functions ==========
    
    def insert_sample_data(self):
        """Insert sample documents for Users and Messages collections"""
        print("\n" + "="*60)
        print("Inserting Sample Data")
        print("="*60)
        
        # Sample Users
        print("\n--- Creating Sample Users ---")
        
        user1_id = self.create_user(
            user_id="usr_123",
            role="patient",
            profile={
                "name": "Jane Doe",
                "dob": "1972-03-09",
                "sex": "F"
            },
            contact={
                "phone": "+1-555-0123",
                "email": "jane.doe@example.com"
            }
        )
        
        user2_id = self.create_user(
            user_id="usr_456",
            role="clinician",
            profile={
                "name": "Dr. John Smith",
                "dob": "1980-07-15",
                "sex": "M"
            },
            contact={
                "phone": "+1-555-0456",
                "email": "john.smith@hospital.com"
            }
        )
        
        user3_id = self.create_user(
            user_id="usr_789",
            role="patient",
            profile={
                "name": "Alice Johnson",
                "dob": "1965-11-22",
                "sex": "F"
            },
            contact={
                "phone": "+1-555-0789",
                "email": "alice.johnson@example.com"
            }
        )
        
        # Sample Messages
        print("\n--- Creating Sample Messages ---")
        
        # Messages for user1 (usr_123)
        msg1_id = self.create_message(
            user_id="usr_123",
            user_text="BP 110/70, breathing better.",
            assistant_text="Great! Proposing lisinopril ↑ to 20 mg qd pending MD approval.",
            model="gpt-4o-mini"
        )
        
        msg2_id = self.create_message(
            user_id="usr_123",
            user_text="Feeling tired today, slight shortness of breath.",
            assistant_text="Please monitor your symptoms. If it persists, contact your physician. Consider reducing activity today.",
            model="gpt-4o-mini"
        )
        
        # Message for user2 (usr_456)
        msg3_id = self.create_message(
            user_id="usr_456",
            user_text="Patient reported improved blood pressure readings.",
            assistant_text="Noted. Continue current medication regimen. Schedule follow-up in 2 weeks.",
            model="gpt-4o-mini"
        )
        
        # Message for user3 (usr_789)
        msg4_id = self.create_message(
            user_id="usr_789",
            user_text="Experiencing chest discomfort after exercise.",
            assistant_text="This is concerning. Please rest immediately and contact emergency services if pain worsens. Avoid physical activity until cleared by your doctor.",
            model="gpt-4o-mini"
        )
        
        print("\n✓ Sample data insertion completed!")
    
    def display_data(self):
        """Display all users and messages"""
        print("\n" + "="*60)
        print("Displaying Database Contents")
        print("="*60)
        
        # Display Users
        print("\n--- Users Collection ---")
        users = self.get_all_users()
        for user in users:
            print(f"\nUser ID: {user['_id']}")
            print(f"  Role: {user['role']}")
            print(f"  Name: {user['profile']['name']}")
            print(f"  DOB: {user['profile']['dob']}")
            print(f"  Sex: {user['profile']['sex']}")
            print(f"  Email: {user['contact']['email']}")
            print(f"  Created: {user['created_at']}")
        
        # Display Messages
        print("\n--- Messages Collection ---")
        messages = self.get_all_messages()
        for msg in messages:
            print(f"\nMessage ID: {msg['_id']}")
            print(f"  User ID: {msg['user_id']}")
            print(f"  User Text: {msg['user']['text']}")
            print(f"  User Timestamp: {msg['user']['ts']}")
            print(f"  Assistant Text: {msg['assistant']['text']}")
            print(f"  Assistant Timestamp: {msg['assistant']['ts']}")
            print(f"  Model: {msg['assistant']['meta']['model']}")
            print(f"  Created: {msg['created_at']}")
            print(f"  Updated: {msg['updated_at']}")

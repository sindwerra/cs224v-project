"""
MongoDB Database Module for HF-Agent
Provides database connection, collections, and getter/setter methods
following best practices for data persistence.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError, OperationFailure
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB connection and provides access to collections."""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: str = "hf_agent_db"):
        """
        Initialize database connection.
        
        Args:
            connection_string: MongoDB connection string. If None, uses MONGODB_URI env var or default.
            database_name: Name of the database to use.
        """
        self.connection_string = connection_string or os.getenv(
            "MONGODB_URI", 
            "mongodb://localhost:27017/"
        )
        self.database_name = database_name
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self._connect()
        self._create_indexes()
    
    def _connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                maxPoolSize=50,  # Connection pool size
                minPoolSize=10,
                retryWrites=True,
                retryReads=True
            )
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB database: {self.database_name}")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def _create_indexes(self):
        """Create indexes for optimal query performance."""
        try:
            # Patients collection indexes
            self.db.patients.create_index("patient_id", unique=True)
            self.db.patients.create_index("created_at")
            
            # Episodes collection indexes
            self.db.episodes.create_index("episode_id", unique=True)
            self.db.episodes.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)])
            self.db.episodes.create_index("status")
            self.db.episodes.create_index("state_version")
            
            # Recommendations collection indexes
            self.db.recommendations.create_index("rec_id", unique=True)
            self.db.recommendations.create_index([("episode_id", ASCENDING), ("created_at", DESCENDING)])
            self.db.recommendations.create_index("status")
            
            # Messages collection indexes
            self.db.messages.create_index([("episode_id", ASCENDING), ("ts", DESCENDING)])
            self.db.messages.create_index("ts")
            
            logger.info("Database indexes created successfully")
        except OperationFailure as e:
            logger.warning(f"Index creation warning: {e}")
    
    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class PatientRepository:
    """Repository for patient data with getter/setter methods."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.collection: Collection = db_manager.db.patients
    
    def create_patient(self, patient_id: str, demographics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new patient record.
        
        Args:
            patient_id: Unique patient identifier
            demographics: Patient demographic information
            
        Returns:
            Created patient document
            
        Raises:
            DuplicateKeyError: If patient_id already exists
        """
        patient_doc = {
            "_id": patient_id,
            "patient_id": patient_id,
            "demographics": demographics,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        try:
            result = self.collection.insert_one(patient_doc)
            logger.info(f"Created patient: {patient_id}")
            return self.get_patient(patient_id)
        except DuplicateKeyError:
            logger.warning(f"Patient {patient_id} already exists")
            raise
    
    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get patient by ID.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Patient document or None if not found
        """
        patient = self.collection.find_one({"patient_id": patient_id})
        return patient
    
    def update_patient(self, patient_id: str, demographics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update patient demographics.
        
        Args:
            patient_id: Patient identifier
            demographics: Updated demographics (partial update supported)
            
        Returns:
            True if update was successful, False otherwise
        """
        update_doc = {"updated_at": datetime.utcnow()}
        if demographics:
            update_doc["demographics"] = demographics
        
        result = self.collection.update_one(
            {"patient_id": patient_id},
            {"$set": update_doc}
        )
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated patient: {patient_id}")
        return success
    
    def delete_patient(self, patient_id: str) -> bool:
        """
        Delete a patient record.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            True if deletion was successful, False otherwise
        """
        result = self.collection.delete_one({"patient_id": patient_id})
        success = result.deleted_count > 0
        if success:
            logger.info(f"Deleted patient: {patient_id}")
        return success
    
    def list_patients(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """
        List all patients with pagination.
        
        Args:
            limit: Maximum number of patients to return
            skip: Number of patients to skip
            
        Returns:
            List of patient documents
        """
        patients = list(self.collection.find().sort("created_at", DESCENDING).skip(skip).limit(limit))
        return patients


class EpisodeRepository:
    """Repository for episode data with getter/setter methods."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.collection: Collection = db_manager.db.episodes
    
    def create_episode(
        self,
        episode_id: str,
        patient_id: str,
        patient_state: Dict[str, Any],
        risk_level: str = "none",
        risk_flags: Optional[List[str]] = None,
        status: str = "pending_doctor"
    ) -> Dict[str, Any]:
        """
        Create a new episode.
        
        Args:
            episode_id: Unique episode identifier
            patient_id: Patient identifier
            patient_state: Current patient state (vitals, labs, symptoms, etc.)
            risk_level: Risk level (none, moderate, high)
            risk_flags: List of risk flags
            status: Episode status (pending_doctor, approved, denied, communicated, closed, escalated)
            
        Returns:
            Created episode document
        """
        episode_doc = {
            "_id": episode_id,
            "episode_id": episode_id,
            "patient_id": patient_id,
            "state_version": 1,
            "patient_state": patient_state,
            "risk_level": risk_level,
            "risk_flags": risk_flags or [],
            "status": status,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        try:
            self.collection.insert_one(episode_doc)
            logger.info(f"Created episode: {episode_id} for patient: {patient_id}")
            return self.get_episode(episode_id)
        except DuplicateKeyError:
            logger.warning(f"Episode {episode_id} already exists")
            raise
    
    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get episode by ID.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Episode document or None if not found
        """
        episode = self.collection.find_one({"episode_id": episode_id})
        return episode
    
    def get_episodes_by_patient(
        self,
        patient_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all episodes for a patient.
        
        Args:
            patient_id: Patient identifier
            limit: Maximum number of episodes to return
            skip: Number of episodes to skip
            
        Returns:
            List of episode documents
        """
        episodes = list(
            self.collection.find({"patient_id": patient_id})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return episodes
    
    def get_episodes_by_status(
        self,
        status: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get episodes by status.
        
        Args:
            status: Episode status
            limit: Maximum number of episodes to return
            skip: Number of episodes to skip
            
        Returns:
            List of episode documents
        """
        episodes = list(
            self.collection.find({"status": status})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return episodes
    
    def update_episode_state(
        self,
        episode_id: str,
        patient_state: Dict[str, Any],
        risk_level: Optional[str] = None,
        risk_flags: Optional[List[str]] = None,
        status: Optional[str] = None
    ) -> bool:
        """
        Update episode state and increment state_version.
        
        Args:
            episode_id: Episode identifier
            patient_state: Updated patient state
            risk_level: Updated risk level (optional)
            risk_flags: Updated risk flags (optional)
            status: Updated status (optional)
            
        Returns:
            True if update was successful, False otherwise
        """
        update_doc = {
            "updated_at": datetime.utcnow(),
            "patient_state": patient_state
        }
        
        if risk_level is not None:
            update_doc["risk_level"] = risk_level
        if risk_flags is not None:
            update_doc["risk_flags"] = risk_flags
        if status is not None:
            update_doc["status"] = status
        
        # Increment state_version atomically
        result = self.collection.update_one(
            {"episode_id": episode_id},
            {
                "$set": update_doc,
                "$inc": {"state_version": 1}
            }
        )
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated episode: {episode_id}, state_version incremented")
        return success
    
    def update_episode_status(self, episode_id: str, status: str) -> bool:
        """
        Update episode status only.
        
        Args:
            episode_id: Episode identifier
            status: New status
            
        Returns:
            True if update was successful, False otherwise
        """
        result = self.collection.update_one(
            {"episode_id": episode_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated episode {episode_id} status to: {status}")
        return success
    
    def get_latest_episode(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent episode for a patient.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Latest episode document or None if not found
        """
        episode = self.collection.find_one(
            {"patient_id": patient_id},
            sort=[("created_at", DESCENDING)]
        )
        return episode


class RecommendationRepository:
    """Repository for recommendation data with getter/setter methods."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.collection: Collection = db_manager.db.recommendations
    
    def create_recommendation(
        self,
        rec_id: str,
        episode_id: str,
        plan: Dict[str, Any],
        based_on_state_version: int,
        status: str = "draft"
    ) -> Dict[str, Any]:
        """
        Create a new recommendation.
        
        Args:
            rec_id: Unique recommendation identifier
            episode_id: Associated episode identifier
            plan: Recommendation plan (actions, monitoring, follow-up, etc.)
            based_on_state_version: State version this recommendation is based on
            status: Recommendation status (draft, final, communicated, superseded)
            
        Returns:
            Created recommendation document
        """
        rec_doc = {
            "_id": rec_id,
            "rec_id": rec_id,
            "episode_id": episode_id,
            "plan": plan,
            "based_on_state_version": based_on_state_version,
            "status": status,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        try:
            self.collection.insert_one(rec_doc)
            logger.info(f"Created recommendation: {rec_id} for episode: {episode_id}")
            return self.get_recommendation(rec_id)
        except DuplicateKeyError:
            logger.warning(f"Recommendation {rec_id} already exists")
            raise
    
    def get_recommendation(self, rec_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recommendation by ID.
        
        Args:
            rec_id: Recommendation identifier
            
        Returns:
            Recommendation document or None if not found
        """
        rec = self.collection.find_one({"rec_id": rec_id})
        return rec
    
    def get_recommendations_by_episode(
        self,
        episode_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all recommendations for an episode.
        
        Args:
            episode_id: Episode identifier
            limit: Maximum number of recommendations to return
            skip: Number of recommendations to skip
            
        Returns:
            List of recommendation documents
        """
        recommendations = list(
            self.collection.find({"episode_id": episode_id})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return recommendations
    
    def get_latest_recommendation(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent recommendation for an episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Latest recommendation document or None if not found
        """
        rec = self.collection.find_one(
            {"episode_id": episode_id},
            sort=[("created_at", DESCENDING)]
        )
        return rec
    
    def update_recommendation_status(self, rec_id: str, status: str) -> bool:
        """
        Update recommendation status.
        
        Args:
            rec_id: Recommendation identifier
            status: New status
            
        Returns:
            True if update was successful, False otherwise
        """
        result = self.collection.update_one(
            {"rec_id": rec_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated recommendation {rec_id} status to: {status}")
        return success
    
    def update_recommendation_plan(self, rec_id: str, plan: Dict[str, Any]) -> bool:
        """
        Update recommendation plan.
        
        Args:
            rec_id: Recommendation identifier
            plan: Updated plan
            
        Returns:
            True if update was successful, False otherwise
        """
        result = self.collection.update_one(
            {"rec_id": rec_id},
            {
                "$set": {
                    "plan": plan,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated recommendation {rec_id} plan")
        return success
    
    def mark_superseded(self, episode_id: str, current_state_version: int) -> int:
        """
        Mark recommendations as superseded if they're based on an older state version.
        
        Args:
            episode_id: Episode identifier
            current_state_version: Current state version of the episode
            
        Returns:
            Number of recommendations marked as superseded
        """
        result = self.collection.update_many(
            {
                "episode_id": episode_id,
                "based_on_state_version": {"$lt": current_state_version},
                "status": {"$ne": "superseded"}
            },
            {
                "$set": {
                    "status": "superseded",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        count = result.modified_count
        if count > 0:
            logger.info(f"Marked {count} recommendations as superseded for episode: {episode_id}")
        return count


class MessageRepository:
    """Repository for conversation messages with getter/setter methods."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.collection: Collection = db_manager.db.messages
    
    def create_message(
        self,
        episode_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new message.
        
        Args:
            episode_id: Associated episode identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (e.g., decision_trace, channel)
            
        Returns:
            Created message document
        """
        message_doc = {
            "episode_id": episode_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "ts": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        result = self.collection.insert_one(message_doc)
        message_doc["_id"] = result.inserted_id
        logger.debug(f"Created message for episode: {episode_id}")
        return message_doc
    
    def get_messages_by_episode(
        self,
        episode_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for an episode.
        
        Args:
            episode_id: Episode identifier
            limit: Maximum number of messages to return
            skip: Number of messages to skip
            
        Returns:
            List of message documents
        """
        messages = list(
            self.collection.find({"episode_id": episode_id})
            .sort("ts", ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return messages
    
    def get_recent_messages(
        self,
        episode_id: str,
        n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the most recent N messages for an episode.
        
        Args:
            episode_id: Episode identifier
            n: Number of recent messages to return
            
        Returns:
            List of message documents (most recent first)
        """
        messages = list(
            self.collection.find({"episode_id": episode_id})
            .sort("ts", DESCENDING)
            .limit(n)
        )
        return list(reversed(messages))  # Return in chronological order


class HFAgentDatabase:
    """Main database interface providing access to all repositories."""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: str = "hf_agent_db"):
        """
        Initialize database and repositories.
        
        Args:
            connection_string: MongoDB connection string
            database_name: Database name
        """
        self.db_manager = DatabaseManager(connection_string, database_name)
        self.patients = PatientRepository(self.db_manager)
        self.episodes = EpisodeRepository(self.db_manager)
        self.recommendations = RecommendationRepository(self.db_manager)
        self.messages = MessageRepository(self.db_manager)
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    # Initialize database
    with HFAgentDatabase() as db:
        # Example: Create a patient
        try:
            patient = db.patients.create_patient(
                patient_id="P001",
                demographics={"name": "John Doe", "age": 65, "gender": "M"}
            )
            print(f"Created patient: {patient['patient_id']}")
        except DuplicateKeyError:
            print("Patient already exists")
        
        # Example: Create an episode
        try:
            episode = db.episodes.create_episode(
                episode_id="E001",
                patient_id="P001",
                patient_state={
                    "vitals": {"sbp": 110, "dbp": 70, "hr": 65},
                    "labs": {"creatinine_mg_dl": 1.2, "egfr": 60, "potassium_mmol_l": 4.5},
                    "symptoms": [],
                    "meds": []
                },
                risk_level="none",
                risk_flags=[],
                status="pending_doctor"
            )
            print(f"Created episode: {episode['episode_id']}")
        except DuplicateKeyError:
            print("Episode already exists")
        
        # Example: Create a recommendation
        try:
            recommendation = db.recommendations.create_recommendation(
                rec_id="R001",
                episode_id="E001",
                plan={
                    "rec_actions": ["maintain current doses"],
                    "rec_monitoring": [{"when": "as_needed"}],
                    "rec_followup_weeks": 2,
                    "rec_tags": []
                },
                based_on_state_version=1,
                status="draft"
            )
            print(f"Created recommendation: {recommendation['rec_id']}")
        except DuplicateKeyError:
            print("Recommendation already exists")
        
        # Example: Add a message
        message = db.messages.create_message(
            episode_id="E001",
            role="user",
            content="My BP is 110/70",
            metadata={"channel": "web"}
        )
        print(f"Created message: {message['_id']}")


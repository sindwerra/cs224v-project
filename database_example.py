"""
Example usage of the HF-Agent Database module.
Demonstrates how to use the database repositories with getters and setters.
"""

from database import HFAgentDatabase
from datetime import datetime
import uuid


def example_workflow():
    """Example workflow demonstrating database operations."""
    
    # Initialize database (uses MONGODB_URI from .env or defaults to localhost)
    with HFAgentDatabase(database_name="hf_agent_db") as db:
        
        print("=" * 60)
        print("HF-Agent Database Example Workflow")
        print("=" * 60)
        
        # 1. Create a patient
        print("\n1. Creating a patient...")
        patient_id = f"P_{uuid.uuid4().hex[:8]}"
        try:
            patient = db.patients.create_patient(
                patient_id=patient_id,
                demographics={
                    "name": "Jane Smith",
                    "age": 72,
                    "gender": "F",
                    "medical_history": ["hypertension", "diabetes"]
                }
            )
            print(f"✓ Created patient: {patient['patient_id']}")
            print(f"  Demographics: {patient['demographics']}")
        except Exception as e:
            print(f"✗ Error creating patient: {e}")
            return
        
        # 2. Create an episode for the patient
        print("\n2. Creating an episode...")
        episode_id = f"E_{uuid.uuid4().hex[:8]}"
        try:
            episode = db.episodes.create_episode(
                episode_id=episode_id,
                patient_id=patient_id,
                patient_state={
                    "vitals": {
                        "sbp": 115,
                        "dbp": 75,
                        "hr": 68,
                        "weight_kg": 75.5
                    },
                    "labs": {
                        "creatinine_mg_dl": 1.1,
                        "egfr": 58,
                        "potassium_mmol_l": 4.3
                    },
                    "symptoms": ["fatigue"],
                    "meds": [
                        {
                            "name": "sacubitril/valsartan",
                            "dose": "49/51mg bid"
                        }
                    ],
                    "adherence": "good"
                },
                risk_level="none",
                risk_flags=[],
                status="pending_doctor"
            )
            print(f"✓ Created episode: {episode['episode_id']}")
            print(f"  State version: {episode['state_version']}")
            print(f"  Risk level: {episode['risk_level']}")
            print(f"  Status: {episode['status']}")
        except Exception as e:
            print(f"✗ Error creating episode: {e}")
            return
        
        # 3. Add conversation messages
        print("\n3. Adding conversation messages...")
        messages = [
            ("user", "Hi, I'm checking in about my heart failure medications."),
            ("assistant", "Hello! I'm here to help. Can you share your current blood pressure and any symptoms?"),
            ("user", "My BP is 115/75 and I've been feeling a bit tired."),
            ("assistant", "Thank you for that information. I'll review your case and get back to you.")
        ]
        
        for role, content in messages:
            message = db.messages.create_message(
                episode_id=episode_id,
                role=role,
                content=content,
                metadata={"channel": "web", "timestamp": datetime.utcnow().isoformat()}
            )
            print(f"✓ Added {role} message")
        
        # 4. Update episode with risk assessment
        print("\n4. Updating episode with risk assessment...")
        updated = db.episodes.update_episode_state(
            episode_id=episode_id,
            patient_state={
                "vitals": {"sbp": 115, "dbp": 75, "hr": 68, "weight_kg": 75.5},
                "labs": {"creatinine_mg_dl": 1.1, "egfr": 58, "potassium_mmol_l": 4.3},
                "symptoms": ["fatigue"],
                "meds": [{"name": "sacubitril/valsartan", "dose": "49/51mg bid"}],
                "adherence": "good",
                "risk_assessment": {
                    "flags": [],
                    "level": "none",
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            risk_level="none",
            risk_flags=[],
            status="pending_doctor"
        )
        if updated:
            updated_episode = db.episodes.get_episode(episode_id)
            print(f"✓ Updated episode state version to: {updated_episode['state_version']}")
        
        # 5. Create a recommendation
        print("\n5. Creating a recommendation...")
        rec_id = f"R_{uuid.uuid4().hex[:8]}"
        try:
            recommendation = db.recommendations.create_recommendation(
                rec_id=rec_id,
                episode_id=episode_id,
                plan={
                    "rec_actions": [
                        {
                            "drug": "sacubitril/valsartan",
                            "change": "49/51mg bid → 97/103mg bid"
                        }
                    ],
                    "rec_monitoring": [
                        {
                            "when": "1-2w",
                            "labs": ["BMP", "Cr", "eGFR", "K+"]
                        }
                    ],
                    "rec_followup_weeks": 2,
                    "rec_tags": []
                },
                based_on_state_version=updated_episode['state_version'],
                status="draft"
            )
            print(f"✓ Created recommendation: {recommendation['rec_id']}")
            print(f"  Based on state version: {recommendation['based_on_state_version']}")
            print(f"  Plan: {recommendation['plan']}")
        except Exception as e:
            print(f"✗ Error creating recommendation: {e}")
            return
        
        # 6. Update recommendation status
        print("\n6. Updating recommendation status...")
        db.recommendations.update_recommendation_status(rec_id, "final")
        print("✓ Updated recommendation status to 'final'")
        
        # 7. Update episode status
        print("\n7. Updating episode status...")
        db.episodes.update_episode_status(episode_id, "approved")
        print("✓ Updated episode status to 'approved'")
        
        # 8. Retrieve data using getters
        print("\n8. Retrieving data using getters...")
        
        # Get patient
        retrieved_patient = db.patients.get_patient(patient_id)
        print(f"✓ Retrieved patient: {retrieved_patient['demographics']['name']}")
        
        # Get all episodes for patient
        patient_episodes = db.episodes.get_episodes_by_patient(patient_id)
        print(f"✓ Retrieved {len(patient_episodes)} episode(s) for patient")
        
        # Get all recommendations for episode
        episode_recommendations = db.recommendations.get_recommendations_by_episode(episode_id)
        print(f"✓ Retrieved {len(episode_recommendations)} recommendation(s) for episode")
        
        # Get conversation messages
        conversation = db.messages.get_messages_by_episode(episode_id)
        print(f"✓ Retrieved {len(conversation)} message(s) from conversation")
        
        # 9. Demonstrate state version checking
        print("\n9. Demonstrating state version checking...")
        # Simulate a new intake that updates the episode
        db.episodes.update_episode_state(
            episode_id=episode_id,
            patient_state={
                "vitals": {"sbp": 118, "dbp": 78, "hr": 70, "weight_kg": 75.2},
                "labs": {"creatinine_mg_dl": 1.15, "egfr": 57, "potassium_mmol_l": 4.4},
                "symptoms": [],
                "meds": [{"name": "sacubitril/valsartan", "dose": "97/103mg bid"}],
                "adherence": "good"
            },
            risk_level="none",
            risk_flags=[],
            status="pending_doctor"
        )
        latest_episode = db.episodes.get_episode(episode_id)
        print(f"✓ Episode state version is now: {latest_episode['state_version']}")
        
        # Mark old recommendations as superseded
        superseded_count = db.recommendations.mark_superseded(
            episode_id,
            latest_episode['state_version']
        )
        print(f"✓ Marked {superseded_count} recommendation(s) as superseded")
        
        # 10. Query by status
        print("\n10. Querying episodes by status...")
        pending_episodes = db.episodes.get_episodes_by_status("pending_doctor")
        print(f"✓ Found {len(pending_episodes)} episode(s) with status 'pending_doctor'")
        
        print("\n" + "=" * 60)
        print("Example workflow completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    example_workflow()


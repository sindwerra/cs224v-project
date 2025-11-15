# Database Usage Guide

This guide explains how to use the MongoDB database module for the HF-Agent project.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Set up your MongoDB connection string in a `.env` file:

```env
MONGODB_URI=mongodb://localhost:27017/
```

Or for MongoDB Atlas:

```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
```

## Quick Start

```python
from database import HFAgentDatabase

# Initialize database connection
with HFAgentDatabase() as db:
    # Create a patient
    patient = db.patients.create_patient(
        patient_id="P001",
        demographics={"name": "John Doe", "age": 65}
    )
    
    # Create an episode
    episode = db.episodes.create_episode(
        episode_id="E001",
        patient_id="P001",
        patient_state={
            "vitals": {"sbp": 110, "dbp": 70, "hr": 65},
            "labs": {"creatinine_mg_dl": 1.2, "egfr": 60},
            "symptoms": []
        },
        risk_level="none",
        status="pending_doctor"
    )
```

## Database Collections

### 1. Patients Collection

Stores patient demographic information.

**Create a patient:**
```python
patient = db.patients.create_patient(
    patient_id="P001",
    demographics={"name": "John Doe", "age": 65, "gender": "M"}
)
```

**Get a patient:**
```python
patient = db.patients.get_patient("P001")
```

**Update patient:**
```python
db.patients.update_patient("P001", demographics={"age": 66})
```

**List patients:**
```python
patients = db.patients.list_patients(limit=10, skip=0)
```

### 2. Episodes Collection

Stores patient episodes with state, risk flags, and status.

**Create an episode:**
```python
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
```

**Get an episode:**
```python
episode = db.episodes.get_episode("E001")
```

**Get episodes by patient:**
```python
episodes = db.episodes.get_episodes_by_patient("P001")
```

**Update episode state (increments state_version):**
```python
db.episodes.update_episode_state(
    episode_id="E001",
    patient_state={...},
    risk_level="moderate",
    risk_flags=["hyperkalemia_moderate"],
    status="pending_doctor"
)
```

**Update episode status:**
```python
db.episodes.update_episode_status("E001", "approved")
```

**Get latest episode for a patient:**
```python
latest = db.episodes.get_latest_episode("P001")
```

**Get episodes by status:**
```python
pending = db.episodes.get_episodes_by_status("pending_doctor")
```

### 3. Recommendations Collection

Stores physician recommendations linked to episodes.

**Create a recommendation:**
```python
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
```

**Get a recommendation:**
```python
rec = db.recommendations.get_recommendation("R001")
```

**Get recommendations by episode:**
```python
recommendations = db.recommendations.get_recommendations_by_episode("E001")
```

**Update recommendation status:**
```python
db.recommendations.update_recommendation_status("R001", "final")
```

**Update recommendation plan:**
```python
db.recommendations.update_recommendation_plan("R001", {...})
```

**Mark superseded recommendations:**
```python
# Marks recommendations based on older state versions as superseded
count = db.recommendations.mark_superseded("E001", current_state_version=3)
```

### 4. Messages Collection

Stores conversation messages for audit and context.

**Create a message:**
```python
message = db.messages.create_message(
    episode_id="E001",
    role="user",
    content="My BP is 110/70",
    metadata={"channel": "web"}
)
```

**Get messages by episode:**
```python
messages = db.messages.get_messages_by_episode("E001")
```

**Get recent messages:**
```python
recent = db.messages.get_recent_messages("E001", n=10)
```

## Best Practices

### 1. Use Context Managers

Always use the database with a context manager to ensure proper connection cleanup:

```python
with HFAgentDatabase() as db:
    # Your code here
    pass
```

### 2. State Version Management

The `state_version` field in episodes is automatically incremented when you update the episode state. Always check that recommendations are based on the current state version:

```python
episode = db.episodes.get_episode("E001")
current_version = episode["state_version"]

# Create recommendation with current version
rec = db.recommendations.create_recommendation(
    rec_id="R001",
    episode_id="E001",
    plan={...},
    based_on_state_version=current_version,
    status="draft"
)
```

### 3. Error Handling

Handle duplicate key errors when creating records:

```python
from pymongo.errors import DuplicateKeyError

try:
    patient = db.patients.create_patient("P001", {...})
except DuplicateKeyError:
    patient = db.patients.get_patient("P001")
```

### 4. Idempotency

For write operations that might be retried, consider using idempotency keys or checking for existing records before creating new ones.

### 5. Indexes

The database automatically creates indexes for optimal query performance:
- `patient_id` (unique)
- `episode_id` (unique)
- `rec_id` (unique)
- `(patient_id, created_at)` for episodes
- `(episode_id, created_at)` for recommendations
- `status` for episodes and recommendations

## Data Model

### Episode Status Values
- `pending_doctor`: Waiting for physician review
- `approved`: Approved by physician
- `denied`: Denied by physician
- `communicated`: Plan communicated to patient
- `closed`: Episode closed
- `escalated`: High-risk escalation triggered

### Recommendation Status Values
- `draft`: Draft recommendation
- `final`: Final recommendation
- `communicated`: Communicated to patient
- `superseded`: Superseded by newer recommendation

### Risk Levels
- `none`: No risk flags
- `moderate`: Moderate risk flags present
- `high`: High-risk flags present (requires escalation)

## Example Workflow

See `database_example.py` for a complete example workflow demonstrating:
1. Creating a patient
2. Creating an episode
3. Adding conversation messages
4. Updating episode state
5. Creating recommendations
6. Managing state versions
7. Querying data

## Connection Pooling

The database uses connection pooling for optimal performance:
- Maximum pool size: 50 connections
- Minimum pool size: 10 connections
- Automatic retry for reads and writes

## Thread Safety

The MongoDB driver is thread-safe. You can use the same `HFAgentDatabase` instance across multiple threads, though it's recommended to create separate instances per thread for better isolation.


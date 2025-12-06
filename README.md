# cs224v-project

Conversational Agent Projects with Genie Worksheets
AI-Powered Heart Failure Medication Assistant: 
Revolutionizing Patient Care Through Intelligent Conversation
ID: HF-AGENT
Difficulty: Beginner Intermediate
Keywords: Heart failure, Application, Conversational Strategy 
Domain:  Medical
Mentor:  Harshit Joshi, harshitj@stanford.edu, PhD Student, Arjun Jain, arjunj@stanford.edu, Masters Student
Other Advisors: Prof. Chieh-Ju Chao (Mayo Clinic)

Question: How can we develop a conversational agent that safely guides heart failure patients through medication titration while monitoring for adverse effects and determining when clinical escalation is necessary?


Motivation: Guideline-directed medical treatment has been shown to be an effective approach in heart failure therapy in studies. However, in real clinical practice, optimization of required medications is a labor-intensive process that involves dedicated follow-up with patients and medication adjustment, and many healthcare systems do not have the required resources to conduct such a task. This led to suboptimal therapy and compromised outcomes in heart failure patients. A conversational agent could provide continuous monitoring and standardized escalation protocols.
Prerequisites: Basic understanding of conversational AI frameworks. Experience with (clinical) decision support systems would be favored.
Project: Leveraging the Genie framework to develop a prototype conversational agent that monitors heart failure medication titration, detects side effects (hypotension, syncope, change in kidney function), tracks lab values (e.g., electrolytes), and triggers physician alerts when needed.

Key challenges:
Agentic Data Collection & Risk Detection: How can we develop an autonomous AI agent that intelligently identifies critical patient-reported data from natural patient conversations, proactively identifies red-flag symptoms or medication issues, and autonomously escalates concerning findings to physicians in real-time?
Autonomous Protocol Execution & Clinical Recommendations: Can we build an agentic system that independently interprets pre-defined titration protocols, autonomously generates evidence-based recommendations (dose modifications, lab orders, program transitions), and proactively guides both patients and physicians through optimal care pathways?

## References: 
1. Heidenreich PA, Bozkurt B, Aguilar D, et al. 2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure: Executive Summary: A Report of the American College of Cardiology/American Heart Association Joint Committee on Clinical Practice Guidelines. Circulation 2022;145(18):e876–94. https://doi.org/10.1161/cir.0000000000001062.
2. Greene SJ, Fonarow GC, DeVore AD, et al. Titration of Medical Therapy for Heart Failure With Reduced Ejection Fraction. J Am Coll Cardiol 2019;73(19):2365–83. https://doi.org/10.1016/j.jacc.2019.02.015.
3. Joshi H, Liu S, Chen J, Weigle R, Lam MS. Controllable and Reliable Knowledge-Intensive Task-Oriented Conversational Agents with Declarative Genie Worksheets. arXiv 2025. https://doi.org/10.48550/arxiv.2407.05674.

## Installation

### Prerequisites
- Python 3.8 or higher
- MongoDB and OpenAI API credentials (found within .env file)

### Step 1: Clone the Repository
```bash
git clone https://github.com/sindwerra/cs224v-project.git
cd cs224v-project
```

### Step 2: Create a Virtual Environment

**Option A: Using Python venv (recommended)**
```bash
python3 -m venv venv
```

**Option B: Using conda**
```bash
conda create -n cs224v-project python=3.8
conda activate cs224v-project
```

### Step 3: Activate the Virtual Environment

**If using Python venv:**
- On macOS/Linux:
  ```bash
  source venv/bin/activate
  ```
- On Windows:
  ```bash
  venv\Scripts\activate
  ```

**If using conda:**
```bash
conda activate cs224v-project
```

### Step 4: Install Dependencies

**If using Python venv:**
```bash
pip install -r requirements.txt
```

**If using conda:**
You can use pip within your conda environment (recommended):
```bash
pip install -r requirements.txt
```

Alternatively, you can install packages via conda if available:
```bash
conda install pymongo python-dotenv rich
```

### Step 5: Set Up Environment Variables
Create a `.env` file in the project root directory and paste the credentials sent in. It should look something like:
```env
MONGODB_URI=your_mongodb_connection_string
OPENAI_API_KEY=your_openai_api_key
```

**Example `.env` file:**
```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
OPENAI_API_KEY=sk-your-openai-api-key-here
```

> **Note:** Make sure to add `.env` to your `.gitignore` file to avoid committing sensitive credentials.

## Running the Program

### Start the Chat Interface
Once you have completed the installation steps, run the main chat interface:

```bash
python chat.py
```

#### Your entry point should look like this:
<img width="1063" height="176" alt="Screenshot 2025-12-05 at 4 27 55 PM" src="https://github.com/user-attachments/assets/ff58e409-b96b-4f59-a74f-6ec417e93429" />


The program will:
1. Connect to your MongoDB database
2. Prompt you to either create a new user or continue with an existing user
3. Start an interactive chat session with the heart failure medication assistant

### Usage
- Enter your messages in the chat interface
- The agent will respond based on the heart failure medication titration protocol
- Chat history is automatically saved to the database
- Type `exit` or `quit` to end the session
- Enjoy!

## Configuration

### Adding File Attachments to RAG

The agent uses Retrieval Augmented Generation (RAG) to access knowledge from attached files. To add additional files to the RAG system:

1. Place your file (PDF, text, etc.) in the project root directory
2. Open `chat.py` and locate the `FILE_ATTACHMENTS` list (around line 18)
3. Add the filename to the list:

```python
FILE_ATTACHMENTS = [
    "Heart Failure Medication Titration Protocol.pdf",
    "your-additional-file.pdf"  # Add your file here
]
```

The agent will automatically use these files to provide more informed responses during conversations.

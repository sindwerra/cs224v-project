import os
from datetime import datetime
from dotenv import load_dotenv

from database import HFAgentDatabase, generate_user_id, validate_email, validate_date
from agent import Agent

from rich.console import Console
from rich.markdown import Markdown

MODEL = "gpt-4o-mini"
FILE_ATTACHMENTS = ["Heart Failure Medication Titration Protocol.pdf"]

def display_chat_history(messages):
    """Display chat history with user and agent messages clearly separated"""
    if not messages:
        print("\n--- No previous messages ---")
        return
    
    print("\n" + "="*60)
    print("Chat History")
    print("="*60)
    
    for i, msg in enumerate(messages, 1):
        user_text = msg.get('user', {}).get('text', '')
        assistant_text = msg.get('assistant', {}).get('text', '')
        user_ts = msg.get('user', {}).get('ts', '')
        assistant_ts = msg.get('assistant', {}).get('ts', '')
        
        # Format timestamp
        if isinstance(user_ts, datetime):
            user_time = user_ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            user_time = str(user_ts)
        
        print(f"\n--- Message {i} ---")
        print(f"\n[USER] ({user_time})")
        print(f"  {user_text}")
        
        if assistant_text:
            if isinstance(assistant_ts, datetime):
                assistant_time = assistant_ts.strftime("%Y-%m-%d %H:%M:%S")
            else:
                assistant_time = str(assistant_ts)
            
            model = msg.get('assistant', {}).get('meta', {}).get('model', 'unknown')
            print(f"\n[AGENT] ({assistant_time}) [Model: {model}]")
            print(f"  {assistant_text}")

def prompt_user_profile(email):
    """Prompt user for profile information"""
    print("\n" + "="*60)
    print("Create User Profile")
    print("="*60)
    
    # Name
    while True:
        name = input("\nFull Name: ").strip()
        if name:
            break
        print("Name cannot be empty. Please try again.")
    
    # Date of Birth
    while True:
        dob = input("Date of Birth (YYYY-MM-DD): ").strip()
        if validate_date(dob):
            break
        print("Invalid date format. Please use YYYY-MM-DD (e.g., 1972-03-09)")
    
    # Sex
    while True:
        sex = input("Sex (M/F): ").strip().upper()
        if sex in ['M', 'F']:
            break
        print("Invalid input. Please enter M or F.")
    
    # Phone
    while True:
        phone = input("Phone Number: ").strip()
        if phone:
            break
        print("Phone number cannot be empty. Please try again.")
    
    # Role
    while True:
        role = input("Role (patient/clinician): ").strip().lower()
        if role in ['patient', 'clinician']:
            break
        print("Invalid role. Please enter 'patient' or 'clinician'.")
    
    return {
        "name": name,
        "dob": dob,
        "sex": sex,
        "phone": phone,
        "email": email,
        "role": role
    }

def main():
    """Main CLI entry point"""
    load_dotenv()
    mongodb_uri = os.getenv('MONGODB_URI')
    
    if not mongodb_uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    
    # Initialize database connection
    db = HFAgentDatabase(mongodb_uri)
    
    # Test connection
    db.ping()

    console = Console()
    
    # CLI
    print("\n" + "="*120)
    print("Heart Failure Agent CLI")
    print(
        "\nA conversational agent that safely guides heart failure patients "
        "through medication titration while monitoring for adverse effects "
        "and determining when clinical escalation is necessary"
    )
    print("="*120)
    
    # Prompt for email
    while True:
        email = input("\nEnter your email address: ").strip()
        if validate_email(email):
            break
        print("Invalid email format. Please try again.")
    
    # Check if user exists
    user = db.get_user_by_email(email)
    
    if user:
        print(f"\n✓ Welcome back, {user['profile']['name']}!")
        print(f"  User ID: {user['_id']}")
        print(f"  Role: {user['role']}")
        user_id = user['_id']
        
        # Check if user has previous messages
        messages = db.get_messages_by_user(user_id)
        load_previous_messages = False
        thread_id = None
        
        if messages:
            # User has previous messages, ask if they want to continue
            while True:
                continue_choice = input("\nWould you like to continue your existing conversation? (yes/no): ").strip().lower()
                if continue_choice in ['yes', 'y', 'no', 'n']:
                    load_previous_messages = continue_choice in ['yes', 'y']
                    break
                print("Invalid input. Please enter 'yes' or 'no'.")
            
            if load_previous_messages:
                # Find the latest message with a thread_id
                for msg in reversed(messages):  # Start from the most recent
                    if msg.get('thread_id'):
                        thread_id = msg['thread_id']
                        break
                
                if thread_id:
                    # Only load messages with the same thread_id (latest conversation)
                    messages = db.get_messages_by_thread_id(thread_id)
                    display_chat_history(messages)
                    print(f"\n✓ Continuing conversation with thread_id: {thread_id}")
                else:
                    # No thread_id found in any message, start fresh
                    print("\n⚠ No previous conversation thread found. Starting a new conversation...")
                    thread_id = None
            else:
                print("\nStarting a new conversation...")
                thread_id = None
        else:
            # Brand new user, no previous messages
            print("\nStarting a new conversation...")
            thread_id = None
    else:
        print(f"\n✗ No user found with email: {email}")
        create_profile = input("\nWould you like to create a new user profile? (yes/no): ").strip().lower()
        
        if create_profile in ['yes', 'y']:
            # Collect profile information
            profile_data = prompt_user_profile(email)
            
            # Generate user ID
            user_id = generate_user_id()
            
            # Prepare data for database
            profile = {
                "name": profile_data["name"],
                "dob": profile_data["dob"],
                "sex": profile_data["sex"]
            }
            
            contact = {
                "phone": profile_data["phone"],
                "email": profile_data["email"]
            }
            
            # Create user
            try:
                db.create_user(
                    user_id=user_id,
                    role=profile_data["role"],
                    profile=profile,
                    contact=contact
                )
                print(f"\n✓ User profile created successfully!")
                print(f"  User ID: {user_id}")
                print(f"  Name: {profile_data['name']}")
                print(f"  Role: {profile_data['role']}")
                thread_id = None  # New user, no previous conversation
            except Exception as e:
                print(f"\n✗ Error creating user: {e}")
                return
        else:
            print("\nUser profile creation cancelled.")
            return
    
    # Initialize agent with thread_id if continuing conversation
    agent = Agent(model=MODEL, file_attachments=FILE_ATTACHMENTS, thread_id=thread_id)
    
    # Conversation loop
    print("\n" + "="*60)
    print("Current Session")
    print("="*60)
    print("\nType your message (or 'exit'/'quit' to end conversation):")
    
    while True:
        # User input
        user_query = input("\n[YOU] ").strip()
        
        # Check for exit commands
        if user_query.lower() in ['exit', 'quit', 'q']:
            print("\n✓ Conversation ended. Goodbye!")
            break
        
        if not user_query:
            print("Please enter a message or type 'exit' to quit.")
            continue
        
        # Generate agent response
        try:
            assistant_response = agent.generate_response(user_query)
            
            # Save message to database (both user and assistant)
            try:
                db.create_message(
                    user_id=user_id,
                    user_text=user_query,
                    assistant_text=assistant_response,
                    model=agent.get_model(),
                    thread_id=agent.thread_id
                )
                
                # Display the exchange
                print(f"\n[AGENT] [Model: {agent.get_model()}]")
                console.print(Markdown(assistant_response))
                # print(f"  {assistant_response}")
            except Exception as e:
                print(f"\n✗ Error saving message: {e}")
                # Still display the response even if saving fails
                print(f"\n[AGENT] [Model: {agent.get_model()}]")
                print(f"  {assistant_response}")
        except Exception as e:
            print(f"\n✗ Error generating response: {e}")
            continue

if __name__ == "__main__":
    main()

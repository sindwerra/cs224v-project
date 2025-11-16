import os
from dotenv import load_dotenv

from database import HFAgentDatabase, generate_user_id, validate_email, validate_date

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
    
    print("\n" + "="*60)
    print("HF Agent CLI")
    print("="*60)
    
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
            except Exception as e:
                print(f"\n✗ Error creating user: {e}")
        else:
            print("\nUser profile creation cancelled.")

if __name__ == "__main__":
    main()

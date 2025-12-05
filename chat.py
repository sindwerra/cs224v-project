import os
from datetime import datetime
from dotenv import load_dotenv

from database import HFAgentDatabase, generate_user_id, validate_email, validate_date
from agent import Agent

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

MODEL = "gpt-4o-mini"
FILE_ATTACHMENTS = ["Heart Failure Medication Titration Protocol.pdf"]

def display_chat_history(messages):
    """Display chat history with user and agent messages clearly separated"""
    console = Console()
    
    if not messages:
        console.print(Panel(
            "[dim]No previous messages[/dim]",
            title="[bold cyan]Chat History[/bold cyan]",
            border_style="dim"
        ))
        return

    console.print("\n")
    console.print(Panel(
        f"[bold]Found {len(messages)} message(s)[/bold]",
        title="[bold cyan]Chat History[/bold cyan]",
        border_style="cyan"
    ))
    
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
        
        # User message panel
        if user_text:
            user_panel = Panel(
                user_text,
                title=f"[bold blue]YOU[/bold blue] [dim]({user_time})[/dim]",
                border_style="blue",
                box=box.ROUNDED
            )
            console.print(user_panel)
        
        # Assistant message panel
        if assistant_text:
            if isinstance(assistant_ts, datetime):
                assistant_time = assistant_ts.strftime("%Y-%m-%d %H:%M:%S")
            else:
                assistant_time = str(assistant_ts)
            
            model = msg.get('assistant', {}).get('meta', {}).get('model', 'unknown')
            assistant_title = f"[bold green]AGENT[/bold green] [dim]({assistant_time})[/dim] [dim]• Model: {model}[/dim]"
            
            assistant_panel = Panel(
                Markdown(assistant_text),
                title=assistant_title,
                border_style="green",
                box=box.ROUNDED
            )
            console.print(assistant_panel)
        
        # Add spacing between messages
        if i < len(messages):
            console.print()

def prompt_user_profile(email, console):
    """Prompt user for profile information"""
    console.print("\n")
    console.print(Panel(
        "[bold]Please provide the following information to create your profile[/bold]",
        title="[bold cyan]Create User Profile[/bold cyan]",
        border_style="cyan"
    ))
    
    # Name
    while True:
        name = Prompt.ask("\n[bold blue]Full Name[/bold blue]")
        if name:
            break
        console.print("[red]Name cannot be empty. Please try again.[/red]")
    
    # Date of Birth
    while True:
        dob = Prompt.ask("[bold blue]Date of Birth[/bold blue] (YYYY-MM-DD)", default="1972-03-09")
        if validate_date(dob):
            break
        console.print("[red]Invalid date format. Please use YYYY-MM-DD (e.g., 1972-03-09)[/red]")
    
    # Sex
    while True:
        sex = Prompt.ask("[bold blue]Sex[/bold blue] (M/F)", choices=["M", "F"], default="M").upper()
        if sex in ['M', 'F']:
            break
    
    # Phone
    while True:
        phone = Prompt.ask("[bold blue]Phone Number[/bold blue]")
        if phone:
            break
        console.print("[red]Phone number cannot be empty. Please try again.[/red]")
    
    # Role
    while True:
        role = Prompt.ask("[bold blue]Role[/bold blue]", choices=["patient", "clinician"], default="patient").lower()
        if role in ['patient', 'clinician']:
            break
    
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
    
    # CLI Header
    console.print("\n")
    welcome_text = Text()
    welcome_text.append("Heart Failure Agent CLI\n\n", style="bold cyan")
    welcome_text.append(
        "A conversational agent that safely guides heart failure patients "
        "through medication titration while monitoring for adverse effects "
        "and determining when clinical escalation is necessary",
        style="dim"
    )
    
    console.print(Panel(
        Align.center(welcome_text),
        border_style="cyan",
        box=box.DOUBLE
    ))
    
    # Prompt for email
    while True:
        email = Prompt.ask("\n[bold blue]Enter your email address[/bold blue]")
        if validate_email(email):
            break
        console.print("[red]Invalid email format. Please try again.[/red]")
    
    # Check if user exists
    user = db.get_user_by_email(email)
    
    if user:
        # Create a table for user info
        user_table = Table(show_header=False, box=None, padding=(0, 2))
        user_table.add_row("[bold green]✓[/bold green]", f"[bold]Welcome back, {user['profile']['name']}![/bold]")
        user_table.add_row("", f"[dim]User ID:[/dim] {user['_id']}")
        user_table.add_row("", f"[dim]Role:[/dim] {user['role']}")
        
        console.print("\n")
        console.print(Panel(
            user_table,
            border_style="green",
            box=box.ROUNDED
        ))
        
        user_id = user['_id']
        
        # Check if user has previous messages
        messages = db.get_messages_by_user(user_id)
        load_previous_messages = False
        thread_id = None
        
        if messages:
            # User has previous messages, ask if they want to continue
            load_previous_messages = Confirm.ask(
                "\n[bold yellow]Would you like to continue your existing conversation?[/bold yellow]"
            )
            
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
                    console.print(f"\n[bold green]✓[/bold green] [dim]Continuing conversation with thread_id: {thread_id}[/dim]")
                else:
                    # No thread_id found in any message, start fresh
                    console.print("\n[bold yellow]⚠[/bold yellow] [yellow]No previous conversation thread found. Starting a new conversation...[/yellow]")
                    thread_id = None
            else:
                console.print("\n[dim]Starting a new conversation...[/dim]")
                thread_id = None
        else:
            # Brand new user, no previous messages
            console.print("\n[dim]Starting a new conversation...[/dim]")
            thread_id = None
    else:
        console.print("\n")
        console.print(Panel(
            f"[red]✗[/red] [bold]No user found with email:[/bold] {email}",
            border_style="red",
            box=box.ROUNDED
        ))
        
        create_profile = Confirm.ask(
            "\n[bold yellow]Would you like to create a new user profile?[/bold yellow]"
        )
        
        if create_profile:
            # Collect profile information
            profile_data = prompt_user_profile(email, console)
            
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
                with console.status("[bold green]Creating user profile...", spinner="dots"):
                    db.create_user(
                        user_id=user_id,
                        role=profile_data["role"],
                        profile=profile,
                        contact=contact
                    )
                
                # Create success table
                success_table = Table(show_header=False, box=None, padding=(0, 2))
                success_table.add_row("[bold green]✓[/bold green]", "[bold]User profile created successfully![/bold]")
                success_table.add_row("", f"[dim]User ID:[/dim] {user_id}")
                success_table.add_row("", f"[dim]Name:[/dim] {profile_data['name']}")
                success_table.add_row("", f"[dim]Role:[/dim] {profile_data['role']}")
                
                console.print("\n")
                console.print(Panel(
                    success_table,
                    border_style="green",
                    box=box.ROUNDED
                ))
                thread_id = None  # New user, no previous conversation
            except Exception as e:
                console.print(f"\n[bold red]✗[/bold red] [red]Error creating user:[/red] {e}")
                return
        else:
            console.print("\n[dim]User profile creation cancelled.[/dim]")
            return
    
    # Initialize agent with thread_id if continuing conversation
    agent = Agent(model=MODEL, file_attachments=FILE_ATTACHMENTS, thread_id=thread_id)
    
    # Conversation loop
    console.print("\n")
    console.print(Panel(
        "[bold]Type your message below (or 'exit'/'quit' to end conversation)[/bold]",
        title="[bold cyan]Current Session[/bold cyan]",
        border_style="cyan"
    ))

    # Set initial prompt based on whether this is a new or continuing conversation
    if thread_id is None:
        # New conversation: prompt for condition and medication doses
        initial_prompt = (
            "Welcome! To get started, please share:\n\n"
            "1. Your current condition (e.g., any symptoms you're experiencing, "
            "how you've been feeling)\n"
            "2. Your current medication doses (please list each medication and its current dose)\n\n"
            "This information will help me provide personalized guidance based on the "
            "Heart Failure Medication Titration Protocol."
        )
    else:
        # Continuing conversation: check-in prompt for medications, blood pressure and symptoms
        initial_prompt = (
            "Before we continue, please share:\n\n"
            "1. Your current titration regime (please list each medication and its current dose)\n"
            "2. Your most recent blood pressure reading (systolic/diastolic)\n"
            "3. Any new or worsening symptoms (e.g., dizziness, shortness of breath, swelling, chest discomfort)\n\n"
            "I need this information to follow the Heart Failure Medication Titration Protocol and provide safe "
            "titration recommendations or monitoring guidance."
        )

    console.print("\n")
    assistant_panel = Panel(
        Markdown(initial_prompt),
        title=f"[bold green]AGENT[/bold green] [dim]• Model: {agent.get_model()}[/dim]",
        border_style="green",
        box=box.ROUNDED
    )
    console.print(assistant_panel)

    # Record the proactive assistant message so the conversation history stays consistent
    try:
        db.create_message(
            user_id=user_id,
            user_text=None,
            assistant_text=initial_prompt,
            model=agent.get_model(),
            thread_id=agent.thread_id
        )
    except Exception as e:
        console.print(f"\n[bold red]✗[/bold red] [red]Error saving initial prompt:[/red] {e}")
    
    while True:
        # User input
        console.print()
        user_query = Prompt.ask("[bold blue]YOU[/bold blue]").strip()
        
        # Check for exit commands
        if user_query.lower() in ['exit', 'quit', 'q']:
            console.print("\n")
            console.print(Panel(
                "[bold green]✓[/bold green] [bold]Conversation ended. Goodbye![/bold]",
                border_style="green",
                box=box.ROUNDED
            ))
            break
        
        if not user_query:
            console.print("[yellow]Please enter a message or type 'exit' to quit.[/yellow]")
            continue
        
        # Display user message
        user_panel = Panel(
            user_query,
            title="[bold blue]YOU[/bold blue]",
            border_style="blue",
            box=box.ROUNDED
        )
        console.print(user_panel)
        
        # Generate agent response
        try:
            with console.status("[bold green]Thinking...", spinner="dots"):
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
                console.print()
                assistant_panel = Panel(
                    Markdown(assistant_response),
                    title=f"[bold green]AGENT[/bold green] [dim]• Model: {agent.get_model()}[/dim]",
                    border_style="green",
                    box=box.ROUNDED
                )
                console.print(assistant_panel)
            except Exception as e:
                console.print(f"\n[bold red]✗[/bold red] [red]Error saving message:[/red] {e}")
                # Still display the response even if saving fails
                console.print()
                assistant_panel = Panel(
                    Markdown(assistant_response),
                    title=f"[bold green]AGENT[/bold green] [dim]• Model: {agent.get_model()}[/dim]",
                    border_style="green",
                    box=box.ROUNDED
                )
                console.print(assistant_panel)
        except Exception as e:
            console.print(f"\n[bold red]✗[/bold red] [red]Error generating response:[/red] {e}")
            continue

if __name__ == "__main__":
    main()

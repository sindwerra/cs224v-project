import random
from typing import Optional

class Agent:
    """Agent class for generating responses to user queries"""
    
    def __init__(self, model: str = "placeholder-model-v1"):
        """
        Initialize the Agent
        
        Args:
            model: Model identifier for the agent (default: placeholder model)
        """
        self.model = model
        self.placeholder_responses = [
            "Thank you for sharing that information. I'm analyzing your data and will provide recommendations shortly.",
            "I understand your concern. Based on the information provided, I recommend monitoring your symptoms closely.",
            "That's important information. Let me help you understand what this means for your care plan.",
            "I've noted your update. This will be reviewed and we'll adjust your treatment plan as needed.",
            "Thank you for the update. I'll forward this information to your care team for review.",
            "Based on your input, I suggest we continue with the current monitoring protocol.",
            "I appreciate you sharing this. Your healthcare provider will be notified of any changes needed.",
            "This information is helpful. Let's keep tracking these metrics and I'll provide updates on next steps."
        ]
    
    def generate_response(self, user_query: str, context: Optional[list] = None) -> str:
        """
        Generate a response to the user's query
        
        Args:
            user_query: The user's message/query
            context: Optional conversation history for context
        
        Returns:
            Generated response string
        """
        # For now, return a random placeholder response
        # This will be replaced with actual LLM integration later
        response = random.choice(self.placeholder_responses)
        
        # Add some variation based on query length
        if len(user_query) < 20:
            response = "I understand. Can you provide more details?"
        elif "?" in user_query:
            response = "That's a great question. Let me provide some guidance on that."
        
        return response
    
    def get_model(self) -> str:
        """Get the current model identifier"""
        return self.model

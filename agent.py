import random
import os
from typing import Optional

from openai_responder import OpenAIResponder

class Agent:
    """Agent class for generating responses to user queries"""
    
    def __init__(self, model: str = "placeholder-model-v1"):
        """
        Initialize the Agent
        
        Args:
            model: Model identifier for the agent (default: placeholder model)
        """
        self.model = model
        self.open_ai_responder = self.create_openai_responder(self.model)
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
        Generate a LLM agent response to the user's query
        
        Args:
            user_query: The user's message/query
            context: Optional conversation history for context
        
        Returns:
            Generated response string
        """

        assert self.open_ai_responder is not None, "OpenAIResponder not initialized"
        
        response = self.open_ai_responder.generate_response(user_query, context)
        
        return response
    
    def get_model(self) -> str:
        """Get the current model identifier"""
        return self.model
    
    def create_openai_responder(self, model: str) -> OpenAIResponder:
        """Create an OpenAIResponder instance"""
        return OpenAIResponder(model=model, api_key=os.getenv("OPENAI_API_KEY"))

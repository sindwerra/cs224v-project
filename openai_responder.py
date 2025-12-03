from typing import Optional, List, Dict, Tuple
import time
from openai import OpenAI

class OpenAIResponder:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        file_attachments: Optional[List[str]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
        # 1. Upload files
        self.file_ids = []
        if file_attachments:
            self.file_ids = self._upload_files(file_attachments)
        
        # 2. Set default instructions that prioritize attached files
        if system_prompt:
            self.default_instructions = system_prompt
        elif file_attachments:
            # If files are attached but no custom prompt, create one that prioritizes them
            file_names = ", ".join(file_attachments)
            self.default_instructions = f"""You are a medical assistant specializing in heart failure medication management. 

CRITICAL: You have access to the following document(s): {file_names}

ALWAYS prioritize information from these attached document(s) as your PRIMARY source of information. When answering questions about heart failure medication titration, dosing, protocols, or clinical guidelines:

1. FIRST search and reference the attached document(s) for specific information
2. ONLY use general medical knowledge if the specific information is not found in the attached document(s)
3. When referencing the protocol, cite specific sections or page numbers when possible
4. If the user asks about information that contradicts the protocol, clarify that you are following the attached protocol document

Do not rely on general medical knowledge when the protocol document contains specific guidance."""
        else:
            self.default_instructions = "You are a helpful assistant."

        # 3. Create the Assistant with file_search tool enabled
        # Files are attached to each message, and the system prompt ensures they're prioritized
        # This approach works reliably across OpenAI SDK versions
        self.assistant = self.client.beta.assistants.create(
            name="Heart Failure Medication Agent",
            instructions=self.default_instructions,
            model=self.model,
            tools=[{"type": "file_search"}],
        )

    def generate_response(
        self,
        user_query: str,
        # We accept an existing thread_id to keep the memory alive
        thread_id: Optional[str] = None, 
        # We keep these for compatibility, but 'context' is less critical now
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Returns:
            (response_text, thread_id)
        """
        
        # A. Use existing thread OR create a new one
        if not thread_id:
            # Create a new thread (fresh memory)
            print("Creating new conversation thread...")
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            
            # If you have manual 'context' from a database, inject it here once
            if context:
                for msg in context:
                    if msg['role'] == 'user':
                        self.client.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=msg['content']
                        )
        
        # B. Add the NEW user message to the thread
        # Attach files to each message to ensure they're available for file_search
        # The system prompt ensures the agent prioritizes these files
        attachments = []
        if self.file_ids:
            attachments = [
                {"file_id": f_id, "tools": [{"type": "file_search"}]} 
                for f_id in self.file_ids
            ]

        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_query,
            attachments=attachments
        )

        # C. Run the Assistant on this thread
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions=system_prompt  # Optional override
        )

        # D. Poll for result
        print(f"Processing on Thread {thread_id}...")
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

        if run.status == 'completed':
            messages = self.client.beta.threads.messages.list(thread_id=thread_id)
            # OpenAI returns newest first; we want the latest assistant reply
            new_reply = messages.data[0].content[0].text.value
            return new_reply, thread_id
        else:
            return f"Error: {run.status}", thread_id

    def _upload_files(self, file_paths: List[str]) -> List[str]:
        ids = []
        for path in file_paths:
            with open(path, "rb") as f:
                file_obj = self.client.files.create(file=f, purpose="assistants")
            ids.append(file_obj.id)
        return ids

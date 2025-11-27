from typing import Optional, List, Dict, Tuple
import time
from openai import OpenAI

class OpenAIResponder:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        file_attachments: Optional[List[str]] = None,
        system_prompt: str = "You are a helpful assistant."
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.default_instructions = system_prompt
        
        # 1. Upload files
        self.file_ids = []
        if file_attachments:
            self.file_ids = self._upload_files(file_attachments)

        # 2. Create the Assistant once
        self.assistant = self.client.beta.assistants.create(
            name="Context Helper",
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
        # We attach the files to this specific message so the model can see them
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

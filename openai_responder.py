from typing import Optional, List, Dict, Any

from openai import OpenAI


class OpenAIResponder:
    """
    Thin wrapper around the OpenAI Responses API.

    Usage:
        responder = OpenAIResponder(model="gpt-5")
        reply = responder.generate_response("Hello!", context=[...])
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
    ) -> None:
        """
        Initialize the OpenAI client.

        Args:
            model: OpenAI model name (e.g. "gpt-5", "gpt-5-mini", etc.)
            api_key: Optional explicit API key. If None, uses OPENAI_API_KEY env var.
        """
        client_kwargs: Dict[str, Any] = {}
        if api_key is not None:
            client_kwargs["api_key"] = api_key

        self.client = OpenAI(**client_kwargs)
        self.model = model

    def generate_response(
        self,
        user_query: str,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Call the OpenAI Responses API and return a string reply.

        Args:
            user_query: The latest user message.
            context: Optional list of prior messages, each like:
                     {"role": "user" | "assistant" | "system", "content": "<text>"}
            system_prompt: Optional system message to prepend.

        Returns:
            The model's response text.
        """
        messages: List[Dict[str, str]] = []

        # Optional system message
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Optional prior context (must already be in OpenAI message format)
        if context:
            messages.extend(context)

        # Current user message
        messages.append({"role": "user", "content": user_query})

        # Responses API expects `input` to be a list of message objects
        response = self.client.responses.create(
            model=self.model,
            input=messages,
        )

        # New SDKs expose a convenience output_text field
        # (falls back to manual extraction if needed)
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()

        # Fallback: walk the structured output
        try:
            first_output = response.output[0]
            first_content = first_output.content[0]
            return first_content.text.strip()
        except Exception:
            # Very defensive: last resort stringification
            return str(response)

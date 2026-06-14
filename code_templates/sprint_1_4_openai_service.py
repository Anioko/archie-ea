"""
OpenAI Service for Architecture Assistant
Sprint 1.4: Real LLM Integration

Direct integration with OpenAI API (not wrapper-based).

INSTALLATION:
    pip install openai==1.12.0 tiktoken==0.6.0

CONFIGURATION:
    export OPENAI_API_KEY="sk-..."
"""

from datetime import datetime
from typing import Dict, List, Optional

import openai
import tiktoken
from flask import current_app

from app.extensions import db
from app.models.llm_usage import LLMUsage


class OpenAIService:
    """
    Direct OpenAI API integration with token tracking and cost monitoring
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt - 4 - turbo"):
        """
        Initialize OpenAI service

        Args:
            api_key: OpenAI API key (defaults to config)
            model: Model to use (gpt - 4 - turbo, gpt - 4, gpt - 3.5 - turbo)
        """
        self.api_key = api_key or current_app.config.get("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        # Initialize client
        self.client = openai.OpenAI(api_key=self.api_key)

        # Initialize tokenizer
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback for new models
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        operation: str = "completion",
    ) -> str:
        """
        Generate text completion

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0 - 2)
            max_tokens: Maximum tokens to generate
            tenant_id: Tenant ID for usage tracking
            user_id: User ID for usage tracking
            session_id: Session ID for usage tracking
            operation: Operation name (e.g., 'gap_analysis', 'option_generation')

        Returns:
            str: Generated text

        Raises:
            openai.OpenAIError: On API errors
        """
        start_time = datetime.utcnow()

        try:
            # Count input tokens
            input_tokens = sum(self.count_tokens(m["content"]) for m in messages)

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
            )

            # Extract response
            content = response.choices[0].message.content
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost
            cost = self.estimate_cost(input_tokens, output_tokens)

            # Track usage
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._track_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                response_time_ms=int(response_time),
                success=True,
            )

            return content

        except openai.OpenAIError as e:
            # Track failed attempt
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._track_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                operation=operation,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time_ms=int(response_time),
                success=False,
                error_message=str(e),
            )

            raise

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost in USD

        Pricing (as of 2024):
        - GPT - 4 Turbo: $0.01/1K input, $0.03/1K output
        - GPT - 4: $0.03/1K input, $0.06/1K output
        - GPT - 3.5 Turbo: $0.0005/1K input, $0.0015/1K output
        """
        pricing = {
            "gpt - 4 - turbo": {"input": 0.01, "output": 0.03},
            "gpt - 4": {"input": 0.03, "output": 0.06},
            "gpt - 3.5 - turbo": {"input": 0.0005, "output": 0.0015},
        }

        # Default to GPT - 4 Turbo pricing
        rates = pricing.get(self.model, pricing["gpt - 4 - turbo"])

        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return round(input_cost + output_cost, 4)

    def _track_usage(
        self,
        tenant_id: Optional[int],
        user_id: Optional[int],
        session_id: Optional[int],
        operation: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        response_time_ms: int,
        success: bool,
        error_message: Optional[str] = None,
    ):
        """Track LLM usage in database"""

        usage = LLMUsage(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            provider="openai",
            model=self.model,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
        )

        db.session.add(usage)

        try:
            db.session.commit()
        except Exception as e:
            # Don't fail the request if usage tracking fails
            current_app.logger.error(f"Failed to track LLM usage: {e}")
            db.session.rollback()


# Example usage:

"""
from app.services.llm.openai_service import OpenAIService

def generate_gap_analysis(session_id, tenant_id, user_id, context):
    llm = OpenAIService(model="gpt - 4 - turbo")

    messages = [
        {
            "role": "system",
            "content": "You are an expert Enterprise Architect..."
        },
        {
            "role": "user",
            "content": f"Analyze gaps for: {context}"
        }
    ]

    analysis = llm.generate_completion(
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        operation='gap_analysis'
    )

    return analysis
"""

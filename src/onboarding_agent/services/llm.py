"""Model-agnostic LLM service using LiteLLM.

All LLM calls in the pipeline go through this service.
Handles rate limiting, retries, and token budget tracking.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import litellm
import structlog
from pydantic import BaseModel

from onboarding_agent.config import get_settings

logger = structlog.get_logger()


class LLMService:
    """Wraps LiteLLM for model-agnostic LLM calls with rate limiting."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_retries = settings.llm_max_retries

        # Rate limiting state
        self._request_times: list[float] = []
        self._max_rpm = 30  # conservative default
        self._lock = asyncio.Lock()

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def _enforce_rate_limit(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Remove requests older than 60s
            self._request_times = [t for t in self._request_times if now - t < 60]
            if len(self._request_times) >= self._max_rpm:
                sleep_time = 60 - (now - self._request_times[0])
                if sleep_time > 0:
                    logger.info("rate_limit_wait", sleep_seconds=round(sleep_time, 1))
                    await asyncio.sleep(sleep_time)
            self._request_times.append(time.monotonic())

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_format: type[BaseModel] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Make an LLM completion call.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The user/analysis prompt.
            response_format: Optional Pydantic model for structured output.
            temperature: Override default temperature.

        Returns:
            Parsed response content as dict, or structured output if response_format given.
        """
        await self._enforce_rate_limit()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "num_retries": self.max_retries,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        logger.debug("llm_call_start", model=self.model)
        response = await litellm.acompletion(**kwargs)

        # Track tokens
        usage = response.usage
        if usage:
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens
            logger.debug(
                "llm_call_complete",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )

        content = response.choices[0].message.content
        return {"content": content, "usage": usage}

    def get_token_summary(self) -> dict[str, int]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
    PermissionDeniedError,
)
from openai.types.chat import ChatCompletionMessageParam
import json
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_smith.llm.response import LLMResponse


class Client:
    """Call an OpenAI-compatible model with key rotation and retries."""

    def __init__(
        self,
        api_url: str,
        model_name: str,
        max_tokens: int,
        api_keys: list[str],
        stop: str = "<end_code>",
    ):
        """Configure the provider, model, output limit, and API keys."""

        self.api_url = api_url
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.stop = stop
        self.current_api_key_index = 0
        self.total_requests = 0
        self.client = OpenAI(
            base_url=api_url, api_key=api_keys[self.current_api_key_index]
        )
        self.api_keys = api_keys

    def generate(self, conversation: list[ChatCompletionMessageParam]) -> LLMResponse:
        """Generate one tracked model response."""

        max_retry = 5
        cooldown = 0
        retries = 0
        start_time = time.perf_counter()
        while True:
            try:
                self.total_requests += 1
                provider_options = {}
                if "openrouter.ai" in self.api_url:
                    provider_options["extra_body"] = {
                        "usage": {"include": True},
                    }
                res = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=conversation,
                    max_tokens=self.max_tokens,
                    stop=self.stop,
                    **provider_options,
                )
                usage = res.usage
                if usage:
                    input_tokens = usage.prompt_tokens
                    output_tokens = usage.completion_tokens
                else:
                    delayed_usage = self._fetch_openrouter_usage(res.id)
                    if not delayed_usage:
                        raise ValueError("Can't track API usage.")
                    input_tokens, output_tokens = delayed_usage
                content = res.choices[0].message.content
                if not content:
                    content = ""
                end_time = time.perf_counter()
                return LLMResponse(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_time_ms=(end_time - start_time) * 1000,
                    retries=retries,
                    llm_output=content,
                )
            except (
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as e:
                cooldown = min(2**retries, 30)
                retries += 1
                if retries >= max_retry + 1:  # la premiere attemps + les retries
                    raise e
                print(f"API error: {e}. Retrying in {cooldown} seconds...")
                time.sleep(cooldown)
            except (PermissionDeniedError, RateLimitError) as e:
                print(f"Rate limit or permission error: {e}")
                if retries >= max_retry:
                    raise e
                cooldown = min(max(3, 2**retries), 20)
                if self.current_api_key_index + 1 < len(self.api_keys):
                    self.current_api_key_index += 1
                    self.client.api_key = self.api_keys[self.current_api_key_index]
                    print(
                        f"Switching to API key #{self.current_api_key_index + 1} "
                        f"of {len(self.api_keys)} in {cooldown}s..."
                    )
                else:
                    print(f"No spare API key, retrying in {cooldown}s...")
                retries += 1
                time.sleep(cooldown)

    def _fetch_openrouter_usage(
        self, generation_id: str
    ) -> tuple[int, int] | None:
        """Fetch delayed usage metadata for an OpenRouter generation."""

        if "openrouter.ai" not in self.api_url:
            return None
        delays = (1, 2, 4, 8, 16, 30)
        url = (
            f"{self.api_url.rstrip('/')}/generation?"
            f"{urlencode({'id': generation_id})}"
        )
        request = Request(
            url,
            headers={"Authorization": f"Bearer {self.client.api_key}"},
        )
        for attempt in range(len(delays) + 1):
            try:
                with urlopen(request, timeout=10) as response:
                    data = json.load(response).get("data", {})
                input_tokens = data.get("native_tokens_prompt")
                if input_tokens is None:
                    input_tokens = data.get("tokens_prompt")
                output_tokens = data.get("native_tokens_completion")
                if output_tokens is None:
                    output_tokens = data.get("tokens_completion")
                if isinstance(input_tokens, int) and isinstance(
                    output_tokens, int
                ):
                    return input_tokens, output_tokens
            except (OSError, TypeError, ValueError, URLError):
                pass
            if attempt < len(delays):
                time.sleep(delays[attempt])
        return None

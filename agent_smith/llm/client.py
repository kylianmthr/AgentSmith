from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
    PermissionDeniedError,
)
from openai.types.chat import ChatCompletionMessageParam
import time

from agent_smith.llm.response import LLMResponse


class Client:
    def __init__(
        self,
        api_url: str,
        model_name: str,
        max_tokens: int,
        api_keys: list[str],
        stop: str = "<end_code>",
    ):
        self.api_url = api_url
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.stop = stop
        self.current_api_key_index = 0
        self.client = OpenAI(
            base_url=api_url, api_key=api_keys[self.current_api_key_index]
        )
        self.api_keys = api_keys

    def generate(
        self, conversation: list[ChatCompletionMessageParam]
    ) -> LLMResponse:
        max_retry = 5
        cooldown = 0
        retries = 0
        while True:
            try:
                start_time = time.perf_counter()
                res = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=conversation,
                    max_tokens=self.max_tokens,
                    stop=self.stop,
                )
                usage = res.usage
                if not usage:
                    raise ValueError("Can't track API usage.")
                content = res.choices[0].message.content
                if not content:
                    content = ""
                end_time = time.perf_counter()
                return LLMResponse(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    request_time_ms=(end_time - start_time) * 1000,
                    retries=retries,
                    llm_output=content,
                )
            except (
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as e:
                print(f"API error: {e}. Retrying in {cooldown} seconds...")
                cooldown = min(2**retries, 30)
                retries += 1
                if (
                    retries >= max_retry + 1
                ):  # la premiere attemps + les retries
                    raise e
                time.sleep(cooldown)
            except (PermissionDeniedError, RateLimitError) as e:
                print(
                    f"Permission denied: {e}. Check your API key and permissions."
                )
                if (
                    self.current_api_key_index + 1 < len(self.api_keys)
                    and retries < max_retry + 1
                ):
                    cooldown = min(2**retries, 30)
                    print(f"Switching to the next API key in {cooldown}...")
                    self.current_api_key_index += 1
                    print("Before:", self.client.api_key)
                    self.client.api_key = self.api_keys[
                        self.current_api_key_index
                    ]
                    print("After:", self.client.api_key)
                    retries += 1
                    time.sleep(cooldown)
                else:
                    raise e

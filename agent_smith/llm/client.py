from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
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
        api_key: str,
        stop: str = "<end_code>",
    ):
        self.api_url = api_url
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.stop = stop
        self.client = OpenAI(base_url=api_url, api_key=api_key)

    def generate(self, conversation: list[ChatCompletionMessageParam]) -> LLMResponse:
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
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            ) as e:
                cooldown = min(2**retries, 30)
                retries += 1
                if retries >= max_retry + 1:  # la premiere attemps + les retries
                    raise e
                time.sleep(cooldown)

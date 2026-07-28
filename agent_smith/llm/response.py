from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    request_time_ms: float = Field(ge=0)
    # model_name: str = Field(min_length=1)
    # api_url: str
    retries: int = Field(ge=0)
    llm_output: str

import os
from dotenv import load_dotenv


class DotEnvLoader:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key: None | list[str] = None

    def load(self):
        api_key = os.getenv("API_KEY")
        if api_key:
            self.api_key = api_key.split(",")

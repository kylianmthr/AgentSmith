import os
from dotenv import load_dotenv


class DotEnvLoader:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = None

    def load(self):
        self.api_key = os.getenv("API_KEY")

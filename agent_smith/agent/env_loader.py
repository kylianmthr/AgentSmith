import os
from dotenv import load_dotenv


class DotEnvLoader:
    """Load API keys from the process environment or a dotenv file."""

    def __init__(self) -> None:
        """Load dotenv values and initialize key storage."""

        load_dotenv()
        self.api_key: None | list[str] = None

    def load(self):
        """Populate the configured API key list."""

        api_key = os.getenv("API_KEY")
        if api_key:
            self.api_key = api_key.split(",")
            print(f"{len(self.api_key)} API key(s) loaded from environment")

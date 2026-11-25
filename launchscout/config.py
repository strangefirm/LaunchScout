"""Central configuration: loads .env and builds the LLM every agent shares."""
import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import LLM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env", override=True)

MODEL = os.getenv("MODEL", "deepseek/deepseek-chat")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))


def is_local_model() -> bool:
    return MODEL.startswith("ollama/")


def get_llm() -> LLM:
    """Return the configured LLM (DeepSeek API or a local Ollama model)."""
    if is_local_model():
        return LLM(
            model=MODEL,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=TEMPERATURE,
            timeout=600,  # local models can be slow
        )
    if MODEL.startswith("deepseek/") and not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is missing in .env")
    return LLM(model=MODEL, temperature=TEMPERATURE, timeout=180)


def check_env() -> list[str]:
    """Return a list of human-readable problems with the configuration."""
    problems = []
    if not os.getenv("SERPER_API_KEY"):
        problems.append("SERPER_API_KEY is missing in .env (get a free key at serper.dev)")
    if MODEL.startswith("deepseek/") and not os.getenv("DEEPSEEK_API_KEY"):
        problems.append("DEEPSEEK_API_KEY is missing in .env")
    return problems

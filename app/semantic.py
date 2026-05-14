from functools import lru_cache
from pathlib import Path
import yaml

SEMANTIC_PATH = Path(__file__).resolve().parent.parent / "semantic_model.yml"


@lru_cache(maxsize=1)
def load_semantic_model() -> dict:
    with SEMANTIC_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def load_semantic_text() -> str:
    return SEMANTIC_PATH.read_text(encoding="utf-8")

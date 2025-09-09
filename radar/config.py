from pathlib import Path
import json
from typing import Union

def load_companies(path: Union[str, Path]) -> list[dict]:
    path = Path(path)
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    elif isinstance(data, list):
        return data
    else:
        return []

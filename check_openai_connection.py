from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is missing. Run configureGPT.bat.")
    model = os.getenv("AI_REVIEW_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    retrieved = OpenAI().models.retrieve(model)
    print("OPENAI API CONNECTION SUCCESSFUL")
    print(f"Model accessible: {retrieved.id}")
    print("No review was generated, so this test used no response tokens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

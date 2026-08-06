from __future__ import annotations

import getpass
from pathlib import Path


def update_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    prefix = f"{key}="
    updated = False
    output: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)
    if not updated:
        if output and output[-1].strip():
            output.append("")
        output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parent
    env_path = root / ".env"
    print("Paste your OpenAI API key. The key is hidden while typing.")
    api_key = getpass.getpass("OPENAI_API_KEY: ").strip()
    if not api_key:
        print("No key entered. Nothing changed.")
        return 1
    if not api_key.startswith("sk-"):
        print("WARNING: The value does not begin with the usual sk- prefix.")
    update_env(env_path, "OPENAI_API_KEY", api_key)
    print("OpenAI API key saved to .env.")
    print("The key was not written to Excel or displayed in the terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

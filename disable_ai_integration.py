from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


AI_SETTINGS = {
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "AI_MARKET_MODEL",
    "AI_MARKET_CACHE_DAYS",
    "AI_MARKET_MAX_NEW_PER_SCAN",
}

AI_FILES = [
    "ai_market_models.py",
    "ai_market_pricer.py",
    "ai_market_workbook.py",
    "restore_ai_market_prices.py",
    "configure_ai_market_pricer.py",
    "configureAIMarketPricer.bat",
    "testAIMarketPricer.bat",
    "apply_low_cost_ai_settings.py",
    "configureGPT.bat",
    "testGPTConnection.bat",
    "runGPTSmartReview.bat",
    "runGPTQueueUrgent.bat",
    "ai_review_openai.py",
    "ai_review_models.py",
    "ai_review_logic.py",
    "ai_review_excel.py",
    "ai_review_cache.py",
    "run_ai_review.py",
    "check_openai_connection.py",
    "configure_openai_env.py",
    "data/ai-market-price-cache.sqlite",
    "data/ai-review-cache.sqlite",
]

AI_GLOBS = [
    "install-phase5.6.3*.bat",
    "README-PHASE5.6.3*",
    "PHASE5.6.3*-VERSION.txt",
    "test_phase563*.py",
    "tests/test_ai_market_pricer.py",
]


def remove_openai_settings(env_path: Path, backup_dir: Path) -> int:
    if not env_path.exists():
        return 0

    shutil.copy2(env_path, backup_dir / "env-before-ai-disable.txt")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    removed = 0
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in AI_SETTINGS or key.startswith("OPENAI_") or key.startswith("AI_MARKET_"):
            removed += 1
            continue
        kept.append(line)

    temporary = env_path.with_suffix(".env.phase564.tmp")
    temporary.write_text(
        "\n".join(kept) + ("\n" if kept else ""),
        encoding="utf-8",
    )
    os.replace(temporary, env_path)
    return removed


def move_ai_files(root: Path, backup_dir: Path) -> int:
    moved = 0
    sources = {root / relative_name for relative_name in AI_FILES}
    for pattern in AI_GLOBS:
        sources.update(path for path in root.glob(pattern) if path.is_file())

    for source in sorted(sources):
        if not source.exists():
            continue
        destination = backup_dir / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved += 1
    return moved


def main() -> int:
    root = Path(__file__).resolve().parent
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = root / "backups" / f"phase5.6.4-ai-disabled-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    settings_removed = remove_openai_settings(root / ".env", backup_dir)
    files_moved = move_ai_files(root, backup_dir)

    print("AI INTEGRATION DISABLED")
    print(f"OpenAI/AI settings removed from .env: {settings_removed}")
    print(f"AI files and caches moved to backup: {files_moved}")
    print(f"Backup folder: {backup_dir}")
    print("eBay and POKEMON_TCG_API_KEY settings were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

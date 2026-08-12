from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "payload" / "update-pokemon-market-daily.bat").read_text(
        encoding="utf-8"
    )
    installer = (root / "install-phase5.6.5.1-daily-bat-fix.bat").read_text(
        encoding="utf-8"
    )

    expected = (
        '"& \'./.venv/Scripts/python.exe\' \'./update_pokemon_market.py\' '
        '2>&1 | Tee-Object -FilePath \'./pokemon-market-daily.log\'; '
        'exit $LASTEXITCODE"'
    ).replace("/", "\\")

    assert expected in launcher
    assert "2^>^&1" not in launcher
    assert "^| Tee-Object" not in launcher
    assert "exit $LASTEXITCODE" in launcher
    assert "update_pokemon_market.py" not in installer.split("copy /Y", 1)[-1]
    assert 'copy /Y "payload\\update-pokemon-market-daily.bat"' in installer
    print("PASS: Phase 5.6.5.1 corrects only the daily launcher pipeline.")


if __name__ == "__main__":
    main()

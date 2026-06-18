from pathlib import Path

from core.parsing import parse_file, parse_text


def test_parse_text_normalizes_newlines() -> None:
    assert parse_text("  Ligne 1\r\nLigne 2\rLigne 3  ") == "Ligne 1\nLigne 2\nLigne 3"


def test_parse_eml_extracts_plain_text(tmp_path: Path) -> None:
    eml = tmp_path / "rfx008792.eml"
    eml.write_text(
        "From: test@example.com\n"
        "To: dest@example.com\n"
        "Subject: RFX008792\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Bonjour,\n"
        "Voici le texte brut du RFX008792.\n",
        encoding="utf-8",
    )

    texte = parse_file(eml)

    assert "RFX008792" in texte
    assert "texte brut" in texte


def test_parse_txt_file(tmp_path: Path) -> None:
    txt = tmp_path / "rfx008792.txt"
    txt.write_text("Texte libre du RFX008792", encoding="utf-8")

    assert parse_file(txt) == "Texte libre du RFX008792"
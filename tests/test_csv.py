from digisac import ler_csv_usuarios
import tempfile
from pathlib import Path
import csv
import digisac
import os

def test_ler_csv_usuarios(tmp_path, monkeypatch):
    csv_file = tmp_path / "usuarios_digisac.csv"
    # create CSV with ; delimiter
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        f.write("Nome;Status\n")
        f.write("Alice;Ativo\n")
        f.write("Bob;Inativo\n")
        f.write("Carlos;ativo\n")

    monkeypatch.setattr(digisac, "CSV_USUARIOS", str(csv_file))

    usuarios = ler_csv_usuarios()
    # only Alice and Carlos (case-insensitive ativo)
    assert "Alice" in usuarios
    assert "Carlos" in usuarios
    assert "Bob" not in usuarios
    assert len(usuarios) == 2

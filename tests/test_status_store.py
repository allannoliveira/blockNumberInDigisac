import json
import csv
from pathlib import Path
from digisac import load_status_store, save_status_store, init_log, registrar_log
import os
import tempfile

def test_save_and_load_status_store(monkeypatch, tmp_path):
    temp_file = tmp_path / "status_store_test.json"
    # monkeypatch module constant
    monkeypatch.setenv("DONT_USE_ENV", "1")  # no-op, just example
    # patch the filename constant in module
    import digisac
    monkeypatch.setattr(digisac, "STATUS_STORE_FILE", str(temp_file))

    store = {"5511999999999": "GREEN"}
    save_status_store(store)
    loaded = load_status_store()
    assert loaded == store

def test_init_log_and_registrar_log(monkeypatch, tmp_path):
    import digisac
    log_path = tmp_path / "log_execucao_test.csv"
    monkeypatch.setattr(digisac, "LOG_CSV", str(log_path))

    # ensure init creates header
    init_log()
    assert log_path.exists()
    with open(log_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert rows[0][0] == "data_hora"

    # append a log entry
    registrar_log("5511999999999", "Usuario Teste", "GREEN", "RED", "ts", "BLOQUEADO", "obs")
    with open(log_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert len(rows) == 2
        assert "Usuario Teste" in rows[1]

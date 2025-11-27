import digisac
from digisac import ler_planilha
from unittest.mock import MagicMock
import pytest

def test_ler_planilha_monkeypatch(monkeypatch):
    # prepare fake rows like gspread would return
    fake_rows = [
        {"phone": "5511999999999", "phoneQuality": "green", "Timestamp": "2025-01-01"},
        {"phone": "", "phoneQuality": "green", "Timestamp": "2025-01-01"},
        {"phone": "5511888888888", "phoneQuality": "invalid", "Timestamp": "2025-01-02"},
        {"phone": "5511777777777", "phoneQuality": "RED", "Timestamp": "2025-01-03"},
    ]

    # fake Credentials.from_service_account_file
    fake_creds = MagicMock()
    monkeypatch.setattr(digisac, "Credentials", MagicMock(from_service_account_file=MagicMock(return_value=fake_creds)))

    # fake client and worksheet
    fake_tab = MagicMock()
    fake_tab.get_all_records.return_value = fake_rows

    fake_sheet = MagicMock(open_by_key=MagicMock(return_value=MagicMock(worksheet=MagicMock(return_value=fake_tab))))
    fake_client = MagicMock(open_by_key=MagicMock(return_value=MagicMock(worksheet=MagicMock(return_value=fake_tab))))
    # monkeypatch gspread.authorize to return fake client
    monkeypatch.setattr(digisac, "gspread", MagicMock(authorize=MagicMock(return_value=fake_client)))

    # now call ler_planilha
    results = ler_planilha()
    # should include only rows with phone and valid quality (GREEN, RED)
    phones = [r["telefone"] for r in results]
    assert "5511999999999" in phones
    assert "5511777777777" in phones
    assert len(results) == 2

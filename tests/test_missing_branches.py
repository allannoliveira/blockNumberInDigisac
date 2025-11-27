# tests/test_missing_branches.py
import digisac
from unittest.mock import MagicMock
from pathlib import Path
import types

# ---------------------------
# load_status_store: arquivo não existe
# ---------------------------
def test_load_status_store_file_missing(monkeypatch, tmp_path):
    fake_path = tmp_path / "naoexiste.json"
    monkeypatch.setattr(digisac, "STATUS_STORE_FILE", str(fake_path))

    result = digisac.load_status_store()
    assert result == {}  # esperado quando arquivo não existe


# ---------------------------
# ler_csv_usuarios: CSV não existe
# ---------------------------
def test_ler_csv_usuarios_missing(monkeypatch, tmp_path):
    fake_csv = tmp_path / "missing.csv"
    monkeypatch.setattr(digisac, "CSV_USUARIOS", str(fake_csv))

    usuarios = digisac.ler_csv_usuarios()
    assert usuarios == []  # esperado


# ---------------------------
# adicionar_restricao: falha após clicar em opção
# ---------------------------
def test_adicionar_restricao_error_after_click(monkeypatch):
    class Page:
        def get_by_test_id(self, *a, **k):
            return MagicMock()
        def locator(self, *a, **k):
            return MagicMock()
        def get_by_role(self, *a, **k):
            # Primeiro branch: não existe remove button
            el = MagicMock()
            el.is_visible.return_value = False
            # Simula falha quando tenta clicar na opção de API
            el.click.side_effect = Exception("falha depois de clicar")
            return el
        @property
        def keyboard(self):
            class K:
                def press(self2, *a, **k): pass
            return K()

    page = Page()
    success, msg = digisac.adicionar_restricao(page, "User", "API-ESCALAS-")
    assert success is False
    assert "Erro" in msg


# ---------------------------
# remover_restricao: falha depois de remover
# ---------------------------
def test_remover_restricao_error_after_remove(monkeypatch):
    class Page:
        def get_by_test_id(self, *a, **k):
            return MagicMock()
        def get_by_role(self, *a, **k):
            # remove button existe, mas o click falha
            el = MagicMock()
            el.is_visible.return_value = True
            el.click.side_effect = Exception("erro ao clicar")
            return el
        @property
        def keyboard(self):
            class K:
                def press(self2, *a, **k): pass
            return K()

    page = Page()
    success, msg = digisac.remover_restricao(page, "User", "API-ESCALAS-")
    # dependendo da implementação, pode retornar False com mensagem de erro
    assert success is False or (isinstance(msg, str) and ("Erro" in msg or "erro" in msg))


# ---------------------------
# automacao_digisac: telefone não está no mapa (branch não coberto)
# ---------------------------
def test_automacao_digisac_telefone_fora_mapa(monkeypatch, tmp_path):
    # Simula um telefone que não está no MAPA_ESCALAS
    planilha = [
        {"telefone": "5511000000000", "qualidade": "RED", "timestamp": "ts"}
    ]
    usuarios = ["User"]

    monkeypatch.setattr(digisac, "load_status_store", lambda: {"5511000000000": "GREEN"})
    monkeypatch.setattr(digisac, "save_status_store", lambda store: None)
    monkeypatch.setattr(digisac, "registrar_log", lambda *a, **k: None)

    # Mocks para Playwright (versão corrigida)
    class FakePage:
        def goto(self, *a, **k):
            return None
        def wait_for_timeout(self, *a, **k):
            return None
        def get_by_test_id(self, *a, **k):
            # retorna um objeto com click/fill/press/wait_for
            m = MagicMock()
            m.click = lambda *a, **k: None
            m.fill = lambda *a, **k: None
            m.press = lambda *a, **k: None
            m.wait_for = lambda *a, **k: None
            return m
        def locator(self, *a, **k):
            return MagicMock(click=lambda *a, **k: None)
        def get_by_role(self, *a, **k):
            return MagicMock(is_visible=lambda *a, **k: False, click=lambda *a, **k: None)
        @property
        def keyboard(self):
            class K:
                def press(self2, *a, **k): return None
            return K()

    class FakeBrowser:
        def __init__(self):
            self._page = FakePage()
        def new_page(self):
            # retorna um FakePage funcional (não None) para que page.goto exista
            return self._page
        def close(self):
            return None

    class FakeChromium:
        def launch(self, headless=False):
            # aceita o argumento headless (como no código real)
            return FakeBrowser()

    class FakeP:
        def __enter__(self):
            # retorna um objeto que tem atributo 'chromium' (instância)
            return types.SimpleNamespace(chromium=FakeChromium())
        def __exit__(self, exc_type, exc, tb):
            return False

    # Substitui sync_playwright por um contexto fake
    monkeypatch.setattr(digisac, "sync_playwright", lambda: FakeP())

    # Execução — não deve levantar exceção mesmo que o telefone não esteja em MAPA_ESCALAS
    digisac.automacao_digisac(usuarios, planilha)

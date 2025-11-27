# tests/test_ui_funcs_and_main.py
import types
from unittest.mock import MagicMock
import pytest
import digisac

# -------------------------
# Helpers: fake page elements
# -------------------------
class FakeElement:
    def __init__(self, visible=True, raise_on_visible=False, raise_on_click=False):
        self._visible = visible
        self._raise_on_visible = raise_on_visible
        self._raise_on_click = raise_on_click

    def click(self, *a, **k):
        if self._raise_on_click:
            raise Exception("click error")
        return None

    def fill(self, *a, **k):
        return None

    def press(self, *a, **k):
        return None

    def wait_for(self, *a, **k):
        return None

    def is_visible(self, timeout=None):
        if self._raise_on_visible:
            raise Exception("is_visible error")
        return self._visible


class FakePageBase:
    def goto(self, *a, **k): return None
    def wait_for_timeout(self, *a, **k): return None

    # default implementations return a FakeElement (overridden per-test if needed)
    def get_by_test_id(self, *args, **kwargs):
        return FakeElement()

    def locator(self, *args, **kwargs):
        return FakeElement()

    def get_by_role(self, role=None, name=None, **kwargs):
        # default: returns not-visible remove button
        return FakeElement(visible=False)

    @property
    def keyboard(self):
        class K:
            def press(self, *a, **k): return None
        return K()


# -------------------------
# TESTS buscar_usuario_por_nome
# -------------------------
def test_buscar_usuario_por_nome_found(monkeypatch):
    class Page(FakePageBase):
        def get_by_test_id(self, *args, **kwargs):
            # return an element where wait_for does not raise -> found
            return FakeElement()

    page = Page()
    assert digisac.buscar_usuario_por_nome(page, "Nome Qualquer") is True

def test_buscar_usuario_por_nome_not_found(monkeypatch):
    class Page(FakePageBase):
        def get_by_test_id(self, *args, **kwargs):
            # element whose wait_for raises -> not found
            el = FakeElement()
            def wait_for(*a, **k):
                raise Exception("not found")
            el.wait_for = wait_for
            return el

    page = Page()
    assert digisac.buscar_usuario_por_nome(page, "Nome Falho") is False


# -------------------------
# TESTS adicionar_restricao
# -------------------------
def test_adicionar_restricao_already_restricted(monkeypatch):
    # get_by_role for "Remove X" returns visible True -> already restricted path
    class Page(FakePageBase):
        def get_by_test_id(self, *a, **k):
            return FakeElement()
        def locator(self, *a, **k):
            return FakeElement()
        def get_by_role(self, *a, **k):
            # remove button visible
            return FakeElement(visible=True)

        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    page = Page()
    success, msg = digisac.adicionar_restricao(page, "Usuario X", "API-ESCALAS-")
    assert success is True
    assert "já estava restrita" in msg

def test_adicionar_restricao_adds_success(monkeypatch):
    # API not present initially, so .get_by_role for Remove will raise or be non-visible
    # then the option click path occurs and save is clicked -> success
    class Page(FakePageBase):
        def __init__(self):
            self._clicked_option = False

        def get_by_test_id(self, *a, **k):
            return FakeElement()

        def locator(self, *a, **k):
            return FakeElement()

        def get_by_role(self, *a, **k):
            # first call could be the "Remove API" check -> return element that raises is_visible
            # but to simulate "not present" we'll return an element whose is_visible raises -> triggers except and continues
            return FakeElement(visible=False, raise_on_visible=True)

        def get_by_role_option(self, *a, **k):
            # simulate selecting option
            return FakeElement()

        def __getattr__(self, name):
            # ensure any unknown get_by_role(name=nome_api) works by returning FakeElement that supports click
            if name.startswith("get_by_role"):
                return lambda *a, **k: FakeElement()
            raise AttributeError

        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    page = Page()
    # monkeypatch page.get_by_role for the option click case (the code calls page.get_by_role(name=nome_api).click())
    # we'll set a method that returns a FakeElement with click defined
    page.get_by_role = lambda *a, **k: FakeElement(visible=False)

    success, msg = digisac.adicionar_restricao(page, "Usuario Y", "API-ESCALAS-")
    # should succeed via add path
    assert success is True
    assert "restrição" in msg or "restrita" in msg

def test_adicionar_restricao_error_returns_false(monkeypatch):
    # Simulate an exception inside the function
    class Page(FakePageBase):
        def get_by_test_id(self, *a, **k):
            return FakeElement()
        def get_by_role(self, *a, **k):
            # the subsequent .click will raise
            return FakeElement(visible=False, raise_on_click=True)

    page = Page()
    success, msg = digisac.adicionar_restricao(page, "Usuario Z", "API-ESCALAS-")
    assert success is False
    assert "Erro ao adicionar restrição" in msg or "Erro" in msg


# -------------------------
# TESTS remover_restricao
# -------------------------
def test_remover_restricao_already_liberada(monkeypatch):
    # Simula o botão remove NÃO visível -> já estava liberada
    class Page(FakePageBase):
        def get_by_test_id(self, *a, **k):
            return FakeElement()
        def get_by_role(self, *a, **k):
            # simulate that remove button is not visible
            return FakeElement(visible=False)

        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    page = Page()
    success, msg = digisac.remover_restricao(page, "Usuario A", "API-ESCALAS-")
    assert success is True
    assert "já estava liberada" in msg

def test_remover_restricao_remove_success(monkeypatch):
    # Simula presença do remove button (visível) e clique bem sucedido
    class Page(FakePageBase):
        def get_by_test_id(self, *a, **k):
            return FakeElement()
        def get_by_role(self, *a, **k):
            # return a visible remove button
            return FakeElement(visible=True)
        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    page = Page()
    success, msg = digisac.remover_restricao(page, "Usuario B", "API-ESCALAS-")
    assert success is True
    assert "restrição removida" in msg or "liberada" in msg or "removida" in msg

def test_remover_restricao_handles_exception_and_reports_liberada(monkeypatch):
    # Simula get_by_role que lança exceção => função interpreta como já liberada e retorna True
    class Page(FakePageBase):
        def get_by_test_id(self, *a, **k):
            return FakeElement()
        def get_by_role(self, *a, **k):
            raise Exception("not found")

        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    page = Page()
    success, msg = digisac.remover_restricao(page, "Usuario C", "API-ESCALAS-")
    assert success is True
    assert "já estava liberada" in msg or "não estava restrita" in msg or "já estava liberada" in msg


# -------------------------
# TESTS main() flow
# -------------------------
def test_main_no_planilha(monkeypatch, tmp_path):
    # Simula planilha vazia -> registrar_log(..., "SEM_DADOS")
    monkeypatch.setattr(digisac, "ler_planilha", lambda: [])
    monkeypatch.setattr(digisac, "ler_csv_usuarios", lambda: ["u1"])
    called = {}
    def fake_registrar_log(telefone, usuario, qa, qn, ts, acao, obs=""):
        called["acao"] = acao
    monkeypatch.setattr(digisac, "registrar_log", fake_registrar_log)

    # run
    digisac.main()
    assert called.get("acao") == "SEM_DADOS"

def test_main_no_usuarios(monkeypatch, tmp_path):
    # Simula CSV sem usuários -> registrar_log(..., "ERRO_CSV")
    monkeypatch.setattr(digisac, "ler_planilha", lambda: [{"telefone":"x","qualidade":"GREEN","timestamp":"t"}])
    monkeypatch.setattr(digisac, "ler_csv_usuarios", lambda: [])
    called = {}
    def fake_registrar_log(*args, **kwargs):
        called["acao"] = args[5] if len(args) > 5 else kwargs.get("acao")
    monkeypatch.setattr(digisac, "registrar_log", fake_registrar_log)

    digisac.main()
    assert called.get("acao") == "ERRO_CSV"

def test_main_runs_automacao(monkeypatch, tmp_path):
    # Simula planilha e CSV com dados e verifica que automacao_digisac é chamada
    monkeypatch.setattr(digisac, "ler_planilha", lambda: [{"telefone":"x","qualidade":"GREEN","timestamp":"t"}])
    monkeypatch.setattr(digisac, "ler_csv_usuarios", lambda: ["u1", "u2"])

    called = {}
    def fake_automacao(usuarios, planilha):
        called["ok"] = True
        # ensure the function receives the same lists
        called["usuarios_len"] = len(usuarios)
        called["planilha_len"] = len(planilha)
    monkeypatch.setattr(digisac, "automacao_digisac", fake_automacao)

    digisac.main()
    assert called.get("ok", False) is True
    assert called.get("usuarios_len") == 2
    assert called.get("planilha_len") == 1

import digisac
from digisac import automacao_digisac
from unittest.mock import MagicMock
import types

def test_automacao_flow_block(monkeypatch, tmp_path):
    # pega um telefone mapeado
    phone = list(digisac.MAPA_ESCALAS.keys())[0]
    usuarios = ["Usuario A"]
    planilha = [{"telefone": phone, "qualidade": "RED", "timestamp": "ts1"}]

    # status store anterior para forçar bloqueio
    monkeypatch.setattr(digisac, "load_status_store", lambda: {phone: "GREEN"})

    saved = {}
    def fake_save(store):
        saved.update(store)
    monkeypatch.setattr(digisac, "save_status_store", fake_save)

    # funções de UI / automação: força comportamento esperado
    monkeypatch.setattr(digisac, "buscar_usuario_por_nome", lambda page, nome: True)
    monkeypatch.setattr(digisac, "adicionar_restricao", lambda page, usuario, nome_api_arg: (True, "restrição adicionada"))
    monkeypatch.setattr(digisac, "remover_restricao", lambda page, usuario, nome_api_arg: (True, "removed"))
    monkeypatch.setattr(digisac, "registrar_log", lambda *args, **kwargs: None)

    # ---------- fake Playwright mais completo ----------
    class FakeElement:
        def __init__(self, visible=True):
            self._visible = visible

        def click(self, *a, **k): return None
        def fill(self, *a, **k): return None
        def press(self, *a, **k): return None
        def wait_for(self, *a, **k): return None
        def is_visible(self, timeout=None):
            # aceita timeout e retorna flag
            return self._visible

    class FakePage:
        def goto(self, *a, **k): return None
        def wait_for_timeout(self, t): return None

        def get_by_test_id(self, *args, **kwargs):
            # retorna um elemento com métodos click/fill/press/wait_for
            return FakeElement()

        def locator(self, *args, **kwargs):
            return FakeElement()

        def get_by_role(self, role=None, name=None, **kwargs):
            # se for procurar "Remove ..." podemos simular visibilidade False por default
            # retorna um FakeElement que tem is_visible() e click()
            # Alguns caminhos do código chamam is_visible() e depois .click()
            return FakeElement(visible=False)

        def keyboard(self):
            # não usado diretamente; o código usa page.keyboard.press("Escape"),
            # então vamos colocar um objeto com press
            class K:
                def press(self, *a, **k): return None
            return K()

        # para compatibilidade, deixar page.keyboard.press funcionar
        @property
        def keyboard(self):
            class K:
                def press(self, *a, **k): return None
            return K()

    class FakeBrowser:
        def __init__(self):
            self._page = FakePage()
        def new_page(self):
            return self._page
        def close(self): return None

    class FakeChromium:
        def launch(self, headless=True):
            # aceita headless kwarg (o código chama headless=False)
            return FakeBrowser()

    # sync_playwright() usado como gerador de contexto "with sync_playwright() as p:"
    class FakeSyncPlaywrightCtx:
        def __enter__(self):
            # retorna um objeto com atributo 'chromium' que tem método launch(...)
            return types.SimpleNamespace(chromium=FakeChromium())
        def __exit__(self, exc_type, exc, tb):
            return False

    # monkeypatcha a função sync_playwright para retornar o contexto
    monkeypatch.setattr(digisac, "sync_playwright", lambda: FakeSyncPlaywrightCtx())

    # Também monkeypatch quaisquer constantes que façam IO real (opcional)
    # evita criação de arquivos reais durante o teste
    monkeypatch.setattr(digisac, "LOG_CSV", str(tmp_path / "log_execucao_test.csv"))
    monkeypatch.setattr(digisac, "STATUS_STORE_FILE", str(tmp_path / "status_store_test.json"))

    # Executa a automação
    automacao_digisac(usuarios, planilha)

    # Verifica que o status foi atualizado e salvo
    assert saved.get(phone) == "RED"

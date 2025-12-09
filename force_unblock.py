# force_unblock.py (versão resiliente)
from playwright.sync_api import sync_playwright
import csv, os, re, sys, time, traceback
from datetime import datetime

# ============================================
# CONFIGURAÇÕES
# ============================================
DIGI_EMAIL = "suporte@solidasaude.com"          # <-- preencha seu e-mail do Digisac
DIGI_PASSWORD = "Solida@2025"        # <-- preencha sua senha do Digisac
CSV_USUARIOS = "usuarios_digisac.cleaned.csv"
ERROR_SCREENSHOT = "error_screenshot.png"

# Mapas dos números → APIs
MAPA_ESCALAS = {
    "5511952134811": "API-ESCALAS-",
    "5511936182483": "API-ESCALASII-",
    "5511936182489": "API-ESCALASIII-"
}

# ============================================
# Helper: leitura CSV (simples, tolerante)
# ============================================
def ler_csv_usuarios_simples():
    usuarios = []
    if not os.path.exists(CSV_USUARIOS):
        print("CSV não encontrado:", CSV_USUARIOS)
        return usuarios

    # Detecta delimitador na primeira linha
    with open(CSV_USUARIOS, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline()
        sep = ";" if ";" in first else ","

    with open(CSV_USUARIOS, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            nome = (row.get("Nome") or row.get("nome") or "").strip()
            status = (row.get("Status") or row.get("status") or "").strip().lower()

            if not nome:
                for v in row.values():
                    if v and str(v).strip():
                        nome = str(v).strip()
                        break

            if nome and status in ("ativo", "active", "sim", "1", "true"):
                usuarios.append(nome)

    print(f"✔ {len(usuarios)} usuários ATIVOS encontrados no CSV")
    return usuarios

# ============================================
# Helper: navegação resiliente com retries
# ============================================
def safe_goto(page, url, retries=3, delay=2, wait_for_selector=None):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            # tenta navegar
            print(f" -> Navegando para {url} (tentativa {attempt}/{retries})")
            page.goto(url, timeout=30000, wait_until="load")
            # opcional: espera por um seletor que indica sucesso de carregamento
            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=10000)
            return True
        except Exception as e:
            last_error = e
            print(f"   ⚠ Navegação falhou (attempt {attempt}): {e}")
            # tenta capturar screenshot útil
            try:
                page.screenshot(path=f"{ERROR_SCREENSHOT}", timeout=2000)
                print(f"   📸 Screenshot salvo em {ERROR_SCREENSHOT}")
            except Exception:
                pass
            time.sleep(delay * attempt)
    # após retries
    print("   ❌ Falha ao navegar para a página após várias tentativas.")
    print("   Possíveis causas: conexão de internet instável, VPN/proxy/firewall bloqueando, site indisponível, problemas de DNS ou inspeção TLS.")
    print("   Tente abrir a URL no navegador manualmente ou verifique rede / proxy.")
    if last_error:
        print("   Último erro (trace):")
        traceback.print_exception(type(last_error), last_error, last_error.__traceback__)
    return False

# ============================================
# Busca usuário no Digisac
# ============================================
def buscar_usuario_por_nome(page, nome):
    try:
        page.goto("https://integralidademedica.digisac.co/users", timeout=30000)
        page.wait_for_timeout(1500)
        page.get_by_test_id("users-list-input-filter").click()
        page.get_by_test_id("users-list-input-filter").fill(nome)
        page.get_by_test_id("users-list-input-filter").press("Enter")
        page.wait_for_timeout(1500)
        page.get_by_test_id("users-list-button-actions-0").wait_for(timeout=4000)
        return True
    except Exception:
        return False

# ============================================
# Remove restrição (robusto)
# ============================================
def remover_restricao_robusta(page, nome_api):
    try:
        page.get_by_test_id("users-list-button-actions-0").click()
        page.wait_for_timeout(800)
        page.get_by_test_id("users-list-button-actions-0-edit").click()
        page.wait_for_timeout(1500)
        root = page.locator("#restrictedServices")
        try:
            chevrons = root.locator("svg.lucide-chevron-down")
            if chevrons.count() > 0:
                chevrons.first.click()
            else:
                icon = root.locator(".text-inputSelect-default-icon .lucide")
                if icon.count() > 0:
                    icon.first.click()
                else:
                    root.click()
            page.wait_for_timeout(600)
        except Exception:
            try:
                root.click(); page.wait_for_timeout(600)
            except Exception:
                pass

        try:
            remove_button = page.get_by_role("button", name=f"Remove {nome_api}")
            if not remove_button.is_visible(timeout=1500):
                page.keyboard.press("Escape"); page.wait_for_timeout(400)
                return True, "já estava liberada"
            remove_button.click(); page.wait_for_timeout(700)
        except Exception:
            page.keyboard.press("Escape"); page.wait_for_timeout(400)
            return True, "já estava liberada"

        try:
            page.get_by_test_id("users-form-button-save").click()
            page.wait_for_timeout(1200)
        except Exception:
            return False, "Erro ao salvar"

        return True, "restrição removida"

    except Exception as e:
        return False, f"Erro: {e}"

# ============================================
# MAIN: execução forçada de desbloqueio
# ============================================
def main(argv):
    if len(argv) < 2:
        print("Uso: python force_unblock.py <telefone_com_55>")
        return

    telefone = re.sub(r'\D', '', argv[1])
    if telefone not in MAPA_ESCALAS:
        print("⚠ Telefone não configurado em MAPA_ESCALAS.")
        return

    nome_api = MAPA_ESCALAS[telefone]
    print(f"🔓 Iniciando DESBLOQUEIO MANUAL da API: {nome_api}")

    usuarios = ler_csv_usuarios_simples()
    if not usuarios:
        print("⚠ Nenhum usuário ativo encontrado no CSV.")
        return

    print(f"➡ Processando {len(usuarios)} usuários...\n")

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            # Navegação com retries para a tela de login
            ok = safe_goto(page, "https://integralidademedica.digisac.co/login", retries=3, delay=2, wait_for_selector='[data-testid="login-input-email"]')
            if not ok:
                print("Falha ao acessar a página de login. Verifique rede e tente novamente.")
                return

            # espera pelo form e preenche
            try:
                page.get_by_test_id("login-input-email").wait_for(timeout=8000)
                page.get_by_test_id("login-input-email").fill(DIGI_EMAIL)
                page.get_by_test_id("login-input-password").fill(DIGI_PASSWORD)
                page.get_by_test_id("login-button-submit").click()
            except Exception as e:
                print("⚠ Erro ao localizar/preencher campos de login:", e)
                page.screenshot(path=ERROR_SCREENSHOT)
                print(f"Screenshot salvo em {ERROR_SCREENSHOT}")
                return

            # espera pós-login (aumentado)
            page.wait_for_timeout(7000)
            print("✔ Login realizado (espera concluída)\n")

            # itera usuários
            for i, nome_usuario in enumerate(usuarios, 1):
                print(f"[{i}/{len(usuarios)}] 👤 {nome_usuario}")
                if not buscar_usuario_por_nome(page, nome_usuario):
                    print("   ❌ Usuário não encontrado")
                    continue
                ok, msg = remover_restricao_robusta(page, nome_api)
                print("   →", msg)

        except Exception as e:
            print("Erro crítico durante execução:")
            traceback.print_exception(type(e), e, e.__traceback__)
            try:
                if browser:
                    # tenta capturar screenshot da última página
                    page.screenshot(path=ERROR_SCREENSHOT)
                    print(f"Screenshot salvo em {ERROR_SCREENSHOT}")
            except Exception:
                pass
        finally:
            try:
                if browser:
                    browser.close()
            except Exception:
                pass

    print("\n✔ FINALIZADO! Todas as tentativas de desbloqueio foram feitas.\n")

# ============================================
if __name__ == "__main__":
    main(sys.argv)

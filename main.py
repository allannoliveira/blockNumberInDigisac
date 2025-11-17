from playwright.sync_api import sync_playwright
import time
import csv
import re

# -----------------------------------------------------------
# CONFIGURAÇÕES
# -----------------------------------------------------------
DIGISAC_EMAIL = "add_email"
DIGISAC_PASSWORD = "add_pass"

CSV_FILE = r"C:\Users\allan.oliveira_boasn\Documents\bloqueio digisac\usuarios_digisac.csv"


# -----------------------------------------------------------
# NORMALIZAÇÃO DO NOME
# -----------------------------------------------------------
def extrair_nome(texto):
    """
    Extrai apenas o nome real removendo qualquer sufixo após ' - '.
    Exemplo:
    'Adriana Cruz - Escalas' → 'Adriana Cruz'
    """
    if not texto:
        return ""

    texto = texto.strip()
    texto = re.sub(r"\s*-\s*.*$", "", texto)
    return texto.strip()


# -----------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# -----------------------------------------------------------
def block_numbers():

    with sync_playwright() as pw:

        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()

        print("Realizando login...")

        page.goto("https://integralidademedica.digisac.co/login")

        page.get_by_test_id("login-input-email").fill(DIGISAC_EMAIL)
        page.get_by_test_id("login-input-password").fill(DIGISAC_PASSWORD)
        page.get_by_test_id("login-button-submit").click()

        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print("Abrindo lista de usuários...")
        page.goto("https://integralidademedica.digisac.co/users?archivedAt=unarchived")
        time.sleep(2)

        # -----------------------------------------------------------
        # PROCESSA O CSV
        # -----------------------------------------------------------
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")

            for row in reader:
                nome_bruto = row.get("Nome", "").strip()
                email_csv = row.get("Email", "").strip()

                if nome_bruto:
                    nome = extrair_nome(nome_bruto)
                else:
                    nome = extrair_nome(email_csv)

                if not nome:
                    print("\nLinha ignorada (sem nome).")
                    continue

                print("\n------------------------------------")
                print(f"Processando usuário: {nome}")
                print("------------------------------------")

                # -----------------------------------------------------------
                # FILTRAR USUÁRIO
                # -----------------------------------------------------------
                filtro = page.get_by_test_id("users-list-input-filter")
                filtro.fill("")
                time.sleep(0.3)

                filtro.fill(nome)
                time.sleep(1.2)

                # -----------------------------------------------------------
                # ABRE MENU DE AÇÕES → EDITAR
                # -----------------------------------------------------------
                try:
                    page.get_by_test_id("users-list-button-actions-0").click()
                    time.sleep(0.4)

                    page.get_by_test_id("users-list-button-actions-0-edit").click()
                    time.sleep(1)
                except Exception as e:
                    print(f"Não foi possível abrir o usuário: {nome}")
                    print(f"Detalhes: {e}")
                    continue

                page.wait_for_load_state("networkidle")
                time.sleep(1)

                # -----------------------------------------------------------
                # APLICA OS BLOQUEIOS
                # -----------------------------------------------------------
                try:
                    page.locator("div").filter(
                        has_text=re.compile(r"^Selecionar$")
                    ).nth(1).click()
                    time.sleep(0.5)

                    page.get_by_text("API-ANTECIPE-").click()
                    time.sleep(0.3)

                    page.locator(
                        ".nebula-ds.flex.w-full.items-center.border.bg-inputSelect-default-background."
                        "rounded-input.px-4.min-h-10.transition.ring-\\[3px\\] > "
                        ".nebula-ds.flex > .gap-1 > .p-0"
                    ).click()
                    time.sleep(0.3)

                    page.get_by_text("API-DOCUMENTAÇÃO-").click()
                    time.sleep(0.3)

                    page.locator(
                        ".nebula-ds.flex.w-full.items-center.border.bg-inputSelect-default-background."
                        "rounded-input.px-4.min-h-10.transition.ring-\\[3px\\] > "
                        ".nebula-ds.flex > .gap-1 > .p-0"
                    ).click()
                    time.sleep(0.3)

                    page.get_by_text("API-FINANCEIRO-").click()
                    time.sleep(0.3)

                    page.get_by_text("API-ANTECIPE-5511952133226API").click()
                    time.sleep(0.3)

                    page.get_by_role("option", name="API-SETORESSATÉLITES-").click()
                    time.sleep(0.3)

                    page.get_by_text("API-ANTECIPE-5511952133226API").click()
                    time.sleep(0.3)

                    page.get_by_role("option", name="API-SUPERVISÃO/LIDERANÇA-").click()
                    time.sleep(0.3)

                    print("Bloqueios aplicados.")
                except Exception as e:
                    print(f"Erro ao aplicar bloqueios para {nome}")
                    print(f"Detalhes: {e}")

                # -----------------------------------------------------------
                # SALVAR
                # -----------------------------------------------------------
                try:
                    page.get_by_test_id("users-form-button-save").click()
                    print("Alterações salvas.")
                except Exception as e:
                    print(f"Não foi possível salvar {nome}")
                    print(f"Detalhes: {e}")

                # Retorna à lista
                page.goto("https://integralidademedica.digisac.co/users?archivedAt=unarchived")
                time.sleep(1.5)

        print("\nProcesso finalizado.")


# -----------------------------------------------------------
# EXECUTA
# -----------------------------------------------------------
block_numbers()

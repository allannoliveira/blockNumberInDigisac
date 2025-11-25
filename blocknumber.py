from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import time

# --------------------------
# CONFIGURAÇÕES DO GOOGLE SHEETS
# --------------------------
SHEET_KEY = "1G9d4lsjtbJzvwNxghPBoQvjm5aKItoVluNoMgko7vuQ"
SHEET_TAB = "BASE"  # altere se o nome da aba for diferente

# --------------------------
# CONFIGURAÇÕES DO DIGISAC
# --------------------------
DIGI_EMAIL = "SEU_EMAIL_AQUI"
DIGI_PASSWORD = "SUA_SENHA_AQUI"

# --------------------------
# LER PLANILHA (VERSÃO NOVA, CORRIGIDA)
# --------------------------
def ler_planilha():
    print("Lendo planilha...")

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_KEY)
    tab = sheet.worksheet(SHEET_TAB)

    linhas = tab.get_all_records()

    dados = []

    for linha in linhas:
        telefone = str(linha.get("phone", "")).strip()
        qualidade = str(linha.get("phoneQuality", "")).strip().upper()

        if (
            telefone.isdigit() and
            len(telefone) >= 12 and
            qualidade in ["RED", "YELLOW", "GREEN"]
        ):
            dados.append({
                "telefone": telefone,
                "qualidade": qualidade
            })

    return dados


# --------------------------
# AUTOMAÇÃO DIGISAC
# --------------------------
def automacao_digisac(dados):
    print("Iniciando automação no Digisac...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # LOGIN
        page.goto("https://app.digisac.com.br/login")
        page.fill("input[type='email']", DIGI_EMAIL)
        page.fill("input[type='password']", DIGI_PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_timeout(6000)

        # IR PARA USUÁRIOS
        page.goto("https://app.digisac.com.br/app/users")
        page.wait_for_timeout(5000)

        for item in dados:
            telefone = item["telefone"]
            qualidade = item["qualidade"]

            print(f"Processando {telefone} | Qualidade: {qualidade}")

            # PESQUISAR NÚMERO
            page.fill("input[placeholder='Pesquisar']", telefone)
            page.wait_for_timeout(2500)

            # ABRIR PERFIL
            try:
                page.get_by_test_id("users-list-button-actions-0").click()
                page.get_by_test_id("users-list-button-actions-0-edit").click()
                page.wait_for_timeout(2000)
            except:
                print(f"Número não encontrado: {telefone}")
                continue

            # BLOQUEAR / DESBLOQUEAR
            try:
                page.get_by_test_id("user-profile-status").click()
                time.sleep(1)

                if qualidade == "RED":
                    print("Status RED -> Desativando...")
                    page.get_by_text("Desativar").click()
                else:
                    print("Status GREEN/YELLOW -> Ativando...")
                    page.get_by_text("Ativar").click()

            except Exception as e:
                print(f"Erro ao alterar status: {e}")

            page.wait_for_timeout(2000)

        print("Processo finalizado!")
        browser.close()


# --------------------------
# EXECUÇÃO
# --------------------------
if __name__ == "__main__":
    dados = ler_planilha()
    print(f"{len(dados)} números válidos encontrados")
    automacao_digisac(dados)

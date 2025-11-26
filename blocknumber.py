from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import time
import csv
import json
import os
from datetime import datetime

# ================================
# CONFIGURAÇÕES
# ================================
SHEET_KEY = "1G9d4lsjtbJzvwNxghPBoQvjm5aKItoVluNoMgko7vuQ"
SHEET_TAB = "BASE"

DIGI_EMAIL = "suporte@boasnovasgestao.com"
DIGI_PASSWORD = "Solida@2025"

CSV_USUARIOS = "usuarios_digisac.csv"

STATUS_STORE_FILE = "status_store.json"
LOG_CSV = "log_execucao.csv"

MAPA_ESCALAS = {
    "5511952134811": "API-ESCALAS-",
    "5511936182483": "API-ESCALASII-",
    "5511936182489": "API-ESCALASIII-"
}

QUALITY_RANK = {
    "GREEN": 0,
    "YELLOW": 1,
    "RED": 2
}

# ------------------------------
# LOG
# ------------------------------
def init_log():
    if not os.path.exists(LOG_CSV):
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["data_hora","telefone","qualidade_antiga","qualidade_nova","timestamp_planilha","acao","observacao"])

def registrar_log(telefone, qual_antiga, qual_nova, ts, acao, obs=""):
    init_log()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            telefone,
            qual_antiga if qual_antiga else "",
            qual_nova if qual_nova else "",
            ts if ts else "",
            acao,
            obs
        ])
    print(f"[LOG] {telefone} | {acao} | {obs}")

# ------------------------------
# STATUS STORE
# ------------------------------
def load_status_store():
    if os.path.exists(STATUS_STORE_FILE):
        with open(STATUS_STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_status_store(store):
    with open(STATUS_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

# ------------------------------
# GOOGLE SHEETS
# ------------------------------
def ler_planilha():
    print("\n📄 Lendo planilha Google Sheets...")

    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_KEY)
    tab = sheet.worksheet(SHEET_TAB)

    linhas = tab.get_all_records()

    dados = []
    for linha in linhas:
        telefone = str(linha.get("phone", "")).strip()
        qualidade = str(linha.get("phoneQuality", "")).strip().upper()
        timestamp = linha.get("Timestamp", "")

        if telefone and qualidade in QUALITY_RANK:
            dados.append({
                "telefone": telefone,
                "qualidade": qualidade,
                "timestamp": timestamp
            })

    print(f"✔ {len(dados)} números válidos carregados")
    return dados

# ------------------------------
# CSV USUÁRIOS
# ------------------------------
def ler_csv_usuarios():
    usuarios = []
    if not os.path.exists(CSV_USUARIOS):
        return usuarios
    with open(CSV_USUARIOS, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            usuarios.append({"nome": row.get("Nome","").strip()})
    return usuarios

# ------------------------------
# REGRAS
# ------------------------------
def deve_bloquear(qual_antiga, qual_nova):
    if qual_antiga is None:
        return False
    return qual_nova == "RED" and qual_antiga != "RED"

def deve_desbloquear(qual_antiga, qual_nova):
    if qual_antiga == "RED" and qual_nova in ("YELLOW", "GREEN"):
        return True
    return False

# ------------------------------
# AUTOMAÇÃO DIGISAC
# ------------------------------
def automacao_digisac(usuarios, planilha):
    print("\n🤖 Iniciando automação no Digisac...")
    status_store = load_status_store()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # LOGIN
        page.goto("https://integralidademedica.digisac.co/login")
        page.get_by_test_id("login-input-email").fill(DIGI_EMAIL)
        page.get_by_test_id("login-input-password").fill(DIGI_PASSWORD)
        page.get_by_test_id("login-button-submit").click()
        page.wait_for_timeout(7000)

        # PROCESSA TELEFONES
        for item in planilha:
            telefone = item["telefone"]
            qualidade = item["qualidade"]
            ts = item["timestamp"]

            qual_antiga = status_store.get(telefone)

            # BLOQUEIO
            if deve_bloquear(qual_antiga, qualidade):
                print(f"\n⛔ BLOQUEAR {telefone} ({qual_antiga} → {qualidade})")

                page.goto("https://integralidademedica.digisac.co/users")
                page.wait_for_timeout(2000)
                page.fill("[data-testid='users-list-input-filter']", telefone)
                page.wait_for_timeout(2000)

                try:
                    page.get_by_test_id("users-list-button-actions-0").click()
                    page.get_by_test_id("users-list-button-actions-0-edit").click()
                except:
                    registrar_log(telefone, qual_antiga, qualidade, ts, "ERRO_ABRIR", "Não encontrou o usuário")
                    continue

                # DESATIVAR
                try:
                    page.get_by_test_id("user-profile-status").click()
                    page.get_by_text("Desativar").click()
                except:
                    registrar_log(telefone, qual_antiga, qualidade, ts, "ERRO_DESATIVAR")
                    continue

                # RESTRIÇÕES
                if telefone in MAPA_ESCALAS:
                    try:
                        page.locator("#restrictedServices .text-inputSelect-default-icon").click()
                        page.get_by_text("API-ESCALAS-").click()

                        page.locator(".nebula-ds.flex > .css-1wy0on6 > div:nth-child(3) > .lucide").click()
                        page.get_by_text("API-ESCALASII-").click()

                        page.locator(".nebula-ds.flex > .css-1wy0on6 > div:nth-child(3) > .lucide").click()
                        page.get_by_text("API-ESCALASIII-").click()

                        page.get_by_test_id("users-form-button-save").click()
                    except:
                        registrar_log(telefone, qual_antiga, qualidade, ts, "ERRO_APIS")

                registrar_log(telefone, qual_antiga, qualidade, ts, "BLOQUEADO", "Qualidade caiu para RED")
                status_store[telefone] = qualidade
                continue

            # DESBLOQUEIO
            if deve_desbloquear(qual_antiga, qualidade):
                print(f"\n🟢 DESBLOQUEAR {telefone} ({qual_antiga} → {qualidade})")

                page.goto("https://integralidademedica.digisac.co/users")
                page.wait_for_timeout(2000)
                page.fill("[data-testid='users-list-input-filter']", telefone)
                page.wait_for_timeout(2000)

                try:
                    page.get_by_test_id("users-list-button-actions-0").click()
                    page.get_by_test_id("users-list-button-actions-0-edit").click()
                except:
                    registrar_log(telefone, qual_antiga, qualidade, ts, "ERRO_ABRIR", "Não encontrou usuário p/ desbloqueio")
                    continue

                # REMOVE APIs
                try:
                    page.get_by_role("button", name="Remove API-ESCALAS-").click()
                    page.get_by_role("button", name="Remove API-ESCALASII-").click()
                    page.get_by_role("button", name="Remove API-ESCALASIII-").click()
                except:
                    pass

                # ATIVAR
                try:
                    page.get_by_test_id("user-profile-status").click()
                    page.get_by_text("Ativar").click()
                except:
                    registrar_log(telefone, qual_antiga, qualidade, ts, "ERRO_ATIVAR")
                    continue

                page.get_by_test_id("users-form-button-save").click()

                registrar_log(telefone, qual_antiga, qualidade, ts, "DESBLOQUEADO", "Qualidade voltou para YELLOW/GREEN")
                status_store[telefone] = qualidade
                continue

            status_store[telefone] = qualidade

    save_status_store(status_store)
    print("\n🎉 Finalizado com sucesso!")

# ================================
# MAIN
# ================================
def main():
    print("🚀 Iniciando script de bloqueio/desbloqueio Digisac...\n")

    planilha = ler_planilha()
    usuarios = ler_csv_usuarios()

    # NOVA REGRA: SE NÃO HÁ NÚMEROS, NÃO ENTRA NO DIGISAC
    if len(planilha) == 0:
        print("⚠ Nenhum número encontrado na planilha. Nada a fazer.\n")
        registrar_log("", "", "", "", "SEM_DADOS", "Nenhum telefone encontrado — execução encerrada")
        return

    # Se tem números → segue fluxo normal
    automacao_digisac(usuarios, planilha)

    print("\n✔ Script finalizado completamente!")

if __name__ == "__main__":
    main()

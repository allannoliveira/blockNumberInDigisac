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

# Mapeamento telefone → nome da API (sem o telefone no final)
MAPA_ESCALAS = {
    "5511952134811": "API-ESCALAS-",
    "5511936182483": "API-ESCALASII-",
    "5511936182489": "API-ESCALASIII-"
}

QUALITY_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}


# ------------------------------
# LOG
# ------------------------------
def init_log():
    if not os.path.exists(LOG_CSV):
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "data_hora", "telefone", "usuario_digisac", "qualidade_antiga", 
                "qualidade_nova", "timestamp_planilha", "acao", "observacao"
            ])


def registrar_log(telefone, usuario, qual_antiga, qual_nova, ts, acao, obs=""):
    init_log()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            telefone,
            usuario if usuario else "",
            qual_antiga if qual_antiga else "",
            qual_nova if qual_nova else "",
            ts if ts else "",
            acao,
            obs
        ])
    print(f"[LOG] {telefone} | {usuario} | {acao} | {obs}")


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
# PLANILHA GOOGLE
# ------------------------------
def ler_planilha():
    print("\n📄 Lendo planilha Google Sheets...")

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
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
    """Retorna lista de nomes dos usuários do Digisac (apenas ativos)"""
    usuarios = []
    
    if not os.path.exists(CSV_USUARIOS):
        print("❌ CSV de usuários não encontrado!")
        return usuarios

    with open(CSV_USUARIOS, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        
        for row in reader:
            nome = row.get("Nome", "").strip()
            status = row.get("Status", "").strip()
            
            # Só adiciona usuários ativos
            if nome and status.lower() == "ativo":
                usuarios.append(nome)

    print(f"✔ {len(usuarios)} usuários ativos carregados do CSV")
    return usuarios


# ------------------------------
# REGRAS
# ------------------------------
def deve_bloquear(qual_antiga, qual_nova):
    """Bloquear = adicionar restrição quando fica RED"""
    return qual_antiga is not None and qual_nova == "RED" and qual_antiga != "RED"


def deve_desbloquear(qual_antiga, qual_nova):
    """Desbloquear = remover restrição quando sai de RED"""
    return qual_antiga == "RED" and qual_nova in ("YELLOW", "GREEN")


# ------------------------------
# AUTOMAÇÃO - BUSCAR USUÁRIO
# ------------------------------
def buscar_usuario_por_nome(page, nome):
    """
    Busca um usuário específico pelo nome no Digisac.
    Retorna True se encontrou, False se não encontrou.
    """
    try:
        page.goto("https://integralidademedica.digisac.co/users", timeout=30000)
        page.wait_for_timeout(2000)

        # Busca pelo nome
        page.get_by_test_id("users-list-input-filter").click()
        page.get_by_test_id("users-list-input-filter").fill(nome)
        page.get_by_test_id("users-list-input-filter").press("Enter")
        page.wait_for_timeout(2000)

        # Verifica se encontrou o usuário
        page.get_by_test_id("users-list-button-actions-0").wait_for(timeout=5000)
        return True
    except:
        return False


# ------------------------------
# AUTOMAÇÃO - ADICIONAR RESTRIÇÃO (BLOQUEAR)
# ------------------------------
def adicionar_restricao(page, usuario, nome_api):
    """
    Adiciona uma API na lista de restrições do usuário.
    Retorna (sucesso: bool, mensagem: str)
    """
    try:
        # Clica nos 3 pontinhos e depois em Editar
        page.get_by_test_id("users-list-button-actions-0").click()
        page.wait_for_timeout(1000)
        page.get_by_test_id("users-list-button-actions-0-edit").click()
        page.wait_for_timeout(2000)
        
        # Abre o dropdown de "Restringir acesso a conexões"
        page.locator("#restrictedServices > .nebula-ds.flex.w-full.items-center.border > .nebula-ds > .css-1wy0on6 > .text-inputSelect-default-icon > .lucide").click()
        page.wait_for_timeout(1000)
        
        # Verifica se a API já está na lista (opcional - para não duplicar)
        try:
            # Tenta encontrar o botão "Remove" da API
            remove_button = page.get_by_role("button", name=f"Remove {nome_api}")
            if remove_button.is_visible():
                print(f"    ℹ️  API '{nome_api}' já estava restrita")
                # Fecha sem salvar
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                return True, "já estava restrita"
        except:
            pass  # API não está na lista, continua para adicionar
        
        # Clica na opção da API para adicionar
        page.get_by_role("option", name=nome_api).click()
        page.wait_for_timeout(1000)
        
        # Salva as alterações
        page.get_by_test_id("users-form-button-save").click()
        page.wait_for_timeout(2000)
        
        return True, "restrição adicionada"
            
    except Exception as e:
        return False, f"Erro ao adicionar restrição: {str(e)}"


# ------------------------------
# AUTOMAÇÃO - REMOVER RESTRIÇÃO (DESBLOQUEAR)
# ------------------------------
def remover_restricao(page, usuario, nome_api):
    """
    Remove uma API da lista de restrições do usuário.
    Retorna (sucesso: bool, mensagem: str)
    """
    try:
        # Clica nos 3 pontinhos e depois em Editar
        page.get_by_test_id("users-list-button-actions-0").click()
        page.wait_for_timeout(1000)
        page.get_by_test_id("users-list-button-actions-0-edit").click()
        page.wait_for_timeout(2000)
        
        # Verifica se a API está na lista de restrições
        try:
            # Tenta clicar no botão "Remove API-XXX"
            remove_button = page.get_by_role("button", name=f"Remove {nome_api}")
            
            if not remove_button.is_visible(timeout=2000):
                print(f"    ℹ️  API '{nome_api}' já estava liberada")
                # Fecha sem salvar
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                return True, "já estava liberada"
            
            # Remove a API
            remove_button.click()
            page.wait_for_timeout(1000)
            
        except Exception as e:
            print(f"    ℹ️  API '{nome_api}' não estava restrita")
            # Fecha sem salvar
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            return True, "já estava liberada"
        
        # Salva as alterações
        page.get_by_test_id("users-form-button-save").click()
        page.wait_for_timeout(2000)
        
        return True, "restrição removida"
            
    except Exception as e:
        return False, f"Erro ao remover restrição: {str(e)}"


# ------------------------------
# AUTOMAÇÃO DIGISAC - PRINCIPAL
# ------------------------------
def automacao_digisac(usuarios, planilha):
    print("\n🤖 Iniciando automação no Digisac...")
    status_store = load_status_store()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # LOGIN
        print("🔐 Fazendo login no Digisac...")
        page.goto("https://integralidademedica.digisac.co/login")
        page.get_by_test_id("login-input-email").click()
        page.get_by_test_id("login-input-email").fill(DIGI_EMAIL)
        page.get_by_test_id("login-input-password").click()
        page.get_by_test_id("login-input-password").fill(DIGI_PASSWORD)
        page.get_by_test_id("login-button-submit").click()
        page.wait_for_timeout(7000)
        print("✔ Login realizado com sucesso!\n")

        # PROCESSA PLANILHA
        for idx, item in enumerate(planilha, 1):
            telefone = item["telefone"]
            qualidade = item["qualidade"]
            ts = item["timestamp"]

            print(f"\n{'='*60}")
            print(f"[{idx}/{len(planilha)}] 📞 Telefone: {telefone} | Qualidade: {qualidade}")
            print(f"{'='*60}")

            qual_antiga = status_store.get(telefone)

            # Verifica se precisa fazer alguma ação
            precisa_bloquear = deve_bloquear(qual_antiga, qualidade)
            precisa_desbloquear = deve_desbloquear(qual_antiga, qualidade)

            if not precisa_bloquear and not precisa_desbloquear:
                print(f"  ℹ️  Sem ação necessária (qualidade: {qual_antiga} → {qualidade})")
                status_store[telefone] = qualidade
                continue

            # Verifica se o telefone está no mapa de APIs
            if telefone not in MAPA_ESCALAS:
                print(f"  ⚠️  Telefone não está no MAPA_ESCALAS - ignorando")
                registrar_log(telefone, "", qual_antiga, qualidade, ts, "IGNORADO",
                              "Telefone não está no MAPA_ESCALAS")
                status_store[telefone] = qualidade
                continue

            nome_api = MAPA_ESCALAS[telefone]
            acao = "BLOQUEAR" if precisa_bloquear else "DESBLOQUEAR"
            
            print(f"\n🎯 Ação necessária: {acao}")
            print(f"📌 API: {nome_api}")
            print(f"👥 Processando {len(usuarios)} usuários...\n")

            # Processa cada usuário do CSV
            usuarios_processados = 0
            usuarios_com_erro = 0

            for idx_user, nome_usuario in enumerate(usuarios, 1):
                print(f"  [{idx_user}/{len(usuarios)}] 👤 {nome_usuario}")

                # Busca o usuário no Digisac
                if not buscar_usuario_por_nome(page, nome_usuario):
                    print(f"    ❌ Usuário não encontrado no Digisac")
                    registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts, 
                                  "ERRO_NAO_ENCONTRADO", "Usuário não encontrado")
                    usuarios_com_erro += 1
                    continue

                # BLOQUEAR (adicionar restrição)
                if precisa_bloquear:
                    sucesso, msg = adicionar_restricao(page, nome_usuario, nome_api)
                    
                    if sucesso:
                        print(f"    ✔ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "BLOQUEADO", msg)
                        usuarios_processados += 1
                    else:
                        print(f"    ❌ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "ERRO_BLOQUEAR", msg)
                        usuarios_com_erro += 1

                # DESBLOQUEAR (remover restrição)
                elif precisa_desbloquear:
                    sucesso, msg = remover_restricao(page, nome_usuario, nome_api)
                    
                    if sucesso:
                        print(f"    ✔ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "DESBLOQUEADO", msg)
                        usuarios_processados += 1
                    else:
                        print(f"    ❌ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "ERRO_DESBLOQUEAR", msg)
                        usuarios_com_erro += 1

            # Resumo do telefone
            print(f"\n  📊 Resumo:")
            print(f"     ✔ Processados: {usuarios_processados}")
            print(f"     ❌ Erros: {usuarios_com_erro}")
            
            # Atualiza o status
            status_store[telefone] = qualidade

        browser.close()

    save_status_store(status_store)
    print("\n" + "="*60)
    print("🎉 Automação finalizada com sucesso!")
    print("="*60)


# ================================
# MAIN
# ================================
def main():
    print("="*60)
    print("🚀 Script Digisac - Bloqueio/Desbloqueio de APIs")
    print("="*60)

    planilha = ler_planilha()
    usuarios = ler_csv_usuarios()

    if len(planilha) == 0:
        registrar_log("", "", "", "", "", "SEM_DADOS", "Planilha sem números")
        print("⚠ Nada a fazer - planilha vazia.")
        return

    if len(usuarios) == 0:
        registrar_log("", "", "", "", "", "ERRO_CSV", "CSV sem usuários ativos")
        print("⚠ Nada a fazer - CSV não tem usuários ativos.")
        return

    print(f"\n📊 Resumo:")
    print(f"   • {len(planilha)} telefones na planilha")
    print(f"   • {len(usuarios)} usuários ativos no CSV")
    print(f"   • {len(MAPA_ESCALAS)} APIs configuradas")

    automacao_digisac(usuarios, planilha)
    print("\n✔ Script concluído!")


if __name__ == "__main__":
    main()
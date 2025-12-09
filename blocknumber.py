from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import time
import csv
import json
import os
from datetime import datetime, date, timezone, timedelta
import re
import sys
import io

# ================================
# FORÇA UTF-8 NO STDOUT/STDERR (corrige UnicodeEncodeError no Windows)
# ================================
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# ================================
# CONFIGURAÇÕES
# ================================
SHEET_KEY = "1G9d4lsjtbJzvwNxghPBoQvjm5aKItoVluNoMgko7vuQ"
SHEET_TAB = "BASE"

DIGI_EMAIL = "suporte@solidasaude.com"
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
# HELPERS DE DATA / DETECÇÃO
# ------------------------------
def is_date_like(s):
    if not s:
        return False
    s = str(s).strip()
    if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', s):
        return True
    if re.search(r'\d{4}-\d{1,2}-\d{1,2}', s):
        return True
    if re.search(r'T\d{2}:\d{2}', s):
        return True
    return False


def parse_timestamp(ts_str):
    if not ts_str:
        return None

    ts_raw = str(ts_str).strip()
    ts_raw = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', ts_raw)

    formatos = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(ts_raw, fmt)
        except Exception:
            pass

    try:
        t = ts_raw
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        return datetime.fromisoformat(t)
    except Exception:
        pass

    try:
        t = re.sub(r'\s*\(.*\)$', '', ts_raw)
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        return datetime.fromisoformat(t)
    except Exception:
        pass

    try:
        t = ts_raw.replace("T", " ").replace("Z", "")
        for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
            try:
                return datetime.strptime(t, fmt)
            except Exception:
                pass
    except Exception:
        pass

    if is_date_like(ts_raw):
        print(f"⚠️  Não foi possível parsear timestamp: '{ts_str}'")
    return None


def get_date_from_timestamp(ts_str):
    dt = parse_timestamp(ts_str)
    if dt:
        return dt.date()
    return None


# ------------------------------
# PLANILHA GOOGLE (ROBUSTA - usa header textual se existir)
# ------------------------------
def ler_planilha(filtrar_hoje=True):
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
    print(f"📊 Total de linhas na planilha: {len(linhas)}")

    usa_indices = False
    if linhas and all(str(k).isdigit() for k in map(str, linhas[0].keys())):
        print("⚠️ Cabeçalhos numéricos detectados — fallback por índices será usado")
        usa_indices = True

    phone_candidates = ["phone", "telefone", "tel", "phone_number", "phonenumber", "phone e164", "num", "numero"]
    quality_candidates = ["phonequality", "quality", "qualidade", "status", "phone_quality"]
    ts_candidates = ["timestamp", "date", "data", "created_at", "horario", "time"]

    dados = []
    dados_hoje = []
    hoje = date.today()
    print(f"📅 Data de hoje: {hoje.strftime('%d/%m/%Y')}")

    if usa_indices:
        valores = tab.get_all_values()
        if not valores:
            return []
        print("DEBUG - primeiras 8 linhas (valores):")
        for i, row in enumerate(valores[:8], 1):
            print(f"  {i}: {row}")

        header_row = valores[0]
        data_rows = valores[1:]
        if len(valores) >= 2:
            second = valores[1]
            second_join = " ".join([str(x).strip().lower() for x in second])
            if any(h in second_join for h in ("timestamp", "phone", "phonequality", "origem", "telefone")):
                header_row = second
                data_rows = valores[2:]

        header_map = {}
        for idx, colname in enumerate(header_row):
            header_map[str(colname).strip().lower()] = idx

        def find_idx_from_header(candidates):
            for cand in candidates:
                for hk, hi in header_map.items():
                    if cand in hk:
                        return hi
            return None

        phone_idx = find_idx_from_header(phone_candidates)
        qual_idx = find_idx_from_header(quality_candidates)
        ts_idx = find_idx_from_header(ts_candidates)

        if phone_idx is None or qual_idx is None or ts_idx is None:
            scan_rows = data_rows[:50]
            for r in scan_rows:
                for idx, val in enumerate(r):
                    v = str(val).strip()
                    v_digits = re.sub(r'\D', '', v)
                    if phone_idx is None and (v_digits.startswith("55") or v.startswith("+55")) and len(v_digits) >= 10:
                        phone_idx = idx
                    if ts_idx is None and ("/" in v or "-" in v or "T" in v) and any(ch.isdigit() for ch in v):
                        ts_idx = idx
                    if qual_idx is None and v.upper() in ("GREEN", "YELLOW", "RED"):
                        qual_idx = idx

        for row in data_rows:
            telefone = ""
            qualidade = ""
            timestamp = ""
            try:
                if phone_idx is not None and phone_idx < len(row):
                    telefone = re.sub(r'\D', '', str(row[phone_idx]))
                if qual_idx is not None and qual_idx < len(row):
                    qualidade = str(row[qual_idx]).strip().upper()
                if ts_idx is not None and ts_idx < len(row):
                    timestamp = str(row[ts_idx]).strip()
            except Exception:
                pass

            if telefone and qualidade in QUALITY_RANK:
                item = {"telefone": telefone, "qualidade": qualidade, "timestamp": timestamp, "origem": ""}
                dados.append(item)
                if is_date_like(timestamp) and get_date_from_timestamp(timestamp) == hoje:
                    dados_hoje.append(item)

    else:
        print(f"\n🔍 Colunas encontradas: {list(linhas[0].keys())}")
        print("DEBUG - primeiras 3 linhas raw:")
        for i, linha in enumerate(linhas[:3], 1):
            print(f"  {i}: {linha}")

        def find_key_in_row_keys(row_keys, candidates):
            for c in candidates:
                for k in row_keys:
                    if c in str(k).strip().lower():
                        return k
            for k in row_keys:
                key_l = str(k).strip().lower()
                for c in candidates:
                    if c in key_l:
                        return k
            return None

        for linha in linhas:
            k_phone = find_key_in_row_keys(linha.keys(), phone_candidates)
            k_quality = find_key_in_row_keys(linha.keys(), quality_candidates)
            k_ts = find_key_in_row_keys(linha.keys(), ts_candidates)

            telefone = ""
            try:
                telefone = str(linha.get(k_phone, "")).strip()
                telefone = re.sub(r'\D', '', telefone)
            except Exception:
                telefone = ""

            qualidade = str(linha.get(k_quality, "")).strip().upper() if k_quality else ""
            timestamp = str(linha.get(k_ts, "")).strip() if k_ts else ""
            origem = linha.get("Origem", "") or linha.get("origem", "")

            if telefone and qualidade in QUALITY_RANK:
                item = {"telefone": telefone, "qualidade": qualidade, "timestamp": timestamp, "origem": origem}
                dados.append(item)
                if is_date_like(timestamp) and get_date_from_timestamp(timestamp) == hoje:
                    dados_hoje.append(item)

    print(f"\n📊 Resumo da planilha:")
    print(f"   • Total de registros válidos: {len(dados)}")
    print(f"   • Registros de HOJE ({hoje.strftime('%d/%m/%Y')}): {len(dados_hoje)}")

    if dados:
        print(f"\n📋 Todos os registros na planilha (amostra):")
        for d in dados[:10]:
            data_reg = get_date_from_timestamp(d['timestamp']) if is_date_like(d['timestamp']) else None
            eh_hoje = "✅ HOJE" if data_reg == hoje else ""
            print(f"   • {d['telefone']} | {d['qualidade']} | {d['timestamp']} {eh_hoje}")

    if filtrar_hoje:
        if len(dados_hoje) == 0:
            print(f"\n⚠️  Nenhum registro encontrado para hoje ({hoje.strftime('%d/%m/%Y')})")
            print(f"   Datas encontradas na planilha (amostra):")
            datas_unicas = set()
            for d in dados:
                if is_date_like(d['timestamp']):
                    dr = get_date_from_timestamp(d['timestamp'])
                    if dr:
                        datas_unicas.add(dr)
            for data_unica in sorted(datas_unicas, reverse=True)[:5]:
                print(f"      • {data_unica.strftime('%d/%m/%Y')}")
        return dados_hoje
    else:
        return dados


# ------------------------------
# CSV USUÁRIOS (robusta: corrige linhas com ; inicial)
# ------------------------------
def ler_csv_usuarios():
    usuarios = []

    if not os.path.exists(CSV_USUARIOS):
        print("❌ CSV de usuários não encontrado!")
        return usuarios

    # Lê o arquivo raw, corrige linhas que começam com ';' (deslocamento)
    cleaned_lines = []
    with open(CSV_USUARIOS, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if not lines:
        print("❌ CSV vazio!")
        return usuarios

    header = lines[0].rstrip("\n\r")
    cleaned_lines.append(header + "\n")
    corrected_count = 0
    for ln in lines[1:]:
        if ln.startswith(";"):
            ln = ln[1:]  # remove o primeiro ';' que desloca as colunas
            corrected_count += 1
        cleaned_lines.append(ln)

    cleaned_path = CSV_USUARIOS.replace(".csv", ".cleaned.csv")
    try:
        with open(cleaned_path, "w", encoding="utf-8", newline="") as f:
            f.writelines(cleaned_lines)
        if corrected_count:
            print(f"✔ Corrigi {corrected_count} linhas com ';' inicial. Arquivo limpo salvo em: {cleaned_path}")
    except Exception as e:
        print(f"⚠️ Não consegui gravar arquivo limpo: {e}")

    from io import StringIO
    safe_stream = StringIO("".join(cleaned_lines))
    reader = csv.DictReader(safe_stream, delimiter=";")

    for row in reader:
        nome = (row.get("Nome") or row.get("nome") or "").strip()
        status = (row.get("Status") or row.get("status") or "").strip()

        if not nome:
            for v in row.values():
                if v and str(v).strip():
                    nome = str(v).strip()
                    break

        if nome and status and status.strip().lower() in ("ativo", "active", "sim", "yes", "1", "true"):
            usuarios.append(nome)

    print(f"✔ {len(usuarios)} usuários ativos carregados do CSV")
    return usuarios


# ------------------------------
# REGRAS
# ------------------------------
def deve_bloquear(qual_antiga, qual_nova):
    if qual_nova != "RED":
        return False
    if qual_antiga is None:
        return True
    return qual_antiga != "RED"


def deve_desbloquear(qual_antiga, qual_nova):
    return qual_antiga == "RED" and qual_nova in ("YELLOW", "GREEN")


# ------------------------------
# AUTOMAÇÃO - BUSCAR USUÁRIO
# ------------------------------
def buscar_usuario_por_nome(page, nome):
    try:
        page.goto("https://integralidademedica.digisac.co/users", timeout=30000)
        page.wait_for_timeout(2000)

        page.get_by_test_id("users-list-input-filter").click()
        page.get_by_test_id("users-list-input-filter").fill(nome)
        page.get_by_test_id("users-list-input-filter").press("Enter")
        page.wait_for_timeout(2000)

        page.get_by_test_id("users-list-button-actions-0").wait_for(timeout=5000)
        return True
    except:
        return False


# ------------------------------
# AUTOMAÇÃO - ADICIONAR RESTRIÇÃO (BLOQUEAR) - VERSÃO ROBUSTA
# ------------------------------
def adicionar_restricao(page, usuario, nome_api):
    try:
        page.get_by_test_id("users-list-button-actions-0").click()
        page.wait_for_timeout(1000)
        page.get_by_test_id("users-list-button-actions-0-edit").click()
        page.wait_for_timeout(2000)

        restricted_root = page.locator("#restrictedServices")

        try:
            chevrons = restricted_root.locator("svg.lucide-chevron-down")
            if chevrons.count() > 0:
                chevrons.first.click()
            else:
                icon = restricted_root.locator(".text-inputSelect-default-icon .lucide")
                if icon.count() > 0:
                    icon.first.click()
                else:
                    restricted_root.click()
            page.wait_for_timeout(700)
        except Exception:
            try:
                restricted_root.click()
                page.wait_for_timeout(700)
            except Exception as e2:
                return False, f"Erro ao abrir dropdown de restrictedServices: {str(e2)}"

        try:
            remove_button = page.get_by_role("button", name=f"Remove {nome_api}")
            if remove_button.is_visible(timeout=1500):
                print(f"    ℹ️  API '{nome_api}' já estava restrita")
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                return True, "já estava restrita"
        except Exception:
            pass

        try:
            option = page.get_by_role("option", name=nome_api)
            option.wait_for(state="visible", timeout=3000)
            option.click()
            page.wait_for_timeout(800)
        except Exception:
            try:
                opt_alt = page.locator(f"role=option >> text={nome_api}")
                if opt_alt.count() > 0:
                    opt_alt.first.click()
                    page.wait_for_timeout(800)
                else:
                    return False, f"Opção '{nome_api}' não encontrada no dropdown"
            except Exception as e2:
                return False, f"Erro ao selecionar opção '{nome_api}': {str(e2)}"

        try:
            page.get_by_test_id("users-form-button-save").click()
            page.wait_for_timeout(2000)
        except Exception as e:
            return False, f"Erro ao salvar formulário: {str(e)}"

        return True, "restrição adicionada"

    except Exception as e:
        return False, f"Erro ao adicionar restrição: {str(e)}"


# ------------------------------
# AUTOMAÇÃO - REMOVER RESTRIÇÃO (DESBLOQUEAR) - VERSÃO ROBUSTA
# ------------------------------
def remover_restricao(page, usuario, nome_api):
    try:
        page.get_by_test_id("users-list-button-actions-0").click()
        page.wait_for_timeout(1000)
        page.get_by_test_id("users-list-button-actions-0-edit").click()
        page.wait_for_timeout(2000)

        restricted_root = page.locator("#restrictedServices")

        try:
            remove_button = page.get_by_role("button", name=f"Remove {nome_api}")
            if not remove_button.is_visible(timeout=1500):
                try:
                    chevrons = restricted_root.locator("svg.lucide-chevron-down")
                    if chevrons.count() > 0:
                        chevrons.first.click()
                    else:
                        icon = restricted_root.locator(".text-inputSelect-default-icon .lucide")
                        if icon.count() > 0:
                            icon.first.click()
                        else:
                            restricted_root.click()
                    page.wait_for_timeout(700)
                except Exception:
                    pass

            if not remove_button.is_visible(timeout=1500):
                print(f"    ℹ️  API '{nome_api}' já estava liberada ou não encontrada")
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                return True, "já estava liberada"

            remove_button.click()
            page.wait_for_timeout(800)

        except Exception:
            print(f"    ℹ️  API '{nome_api}' não estava restrita")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            return True, "já estava liberada"

        try:
            page.get_by_test_id("users-form-button-save").click()
            page.wait_for_timeout(2000)
        except Exception as e:
            return False, f"Erro ao salvar formulário: {str(e)}"

        return True, "restrição removida"

    except Exception as e:
        return False, f"Erro ao remover restrição: {str(e)}"


# ------------------------------
# AUTOMAÇÃO DIGISAC - PRINCIPAL
# ------------------------------
def automacao_digisac(usuarios, planilha):
    print("\n🤖 Iniciando automação no Digisac...")
    status_store = load_status_store()

    print(f"\n📦 Status armazenado anteriormente:")
    if status_store:
        for tel, qual in status_store.items():
            print(f"   • {tel}: {qual}")
    else:
        print("   (nenhum - primeira execução)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # LOGIN
        print("\n🔐 Fazendo login no Digisac...")
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
            origem = item.get("origem", "")

            print(f"\n{'='*60}")
            print(f"[{idx}/{len(planilha)}] 📞 Telefone: {telefone}")
            print(f"   📍 Origem: {origem}")
            print(f"   🎨 Qualidade: {qualidade}")
            print(f"   📅 Timestamp: {ts}")
            print(f"{'='*60}")

            qual_antiga = status_store.get(telefone)
            print(f"   📦 Status anterior armazenado: {qual_antiga if qual_antiga else 'NENHUM (primeira vez)'}")

            precisa_bloquear = deve_bloquear(qual_antiga, qualidade)
            precisa_desbloquear = deve_desbloquear(qual_antiga, qualidade)

            if not precisa_bloquear and not precisa_desbloquear:
                print(f"\n  ℹ️  Sem ação necessária (qualidade: {qual_antiga} → {qualidade})")
                status_store[telefone] = qualidade
                continue

            if telefone not in MAPA_ESCALAS:
                print(f"\n  ⚠️  Telefone não está no MAPA_ESCALAS - ignorando")
                registrar_log(telefone, "", qual_antiga, qualidade, ts, "IGNORADO",
                              "Telefone não está no MAPA_ESCALAS")
                status_store[telefone] = qualidade
                continue

            nome_api = MAPA_ESCALAS[telefone]
            acao = "BLOQUEAR" if precisa_bloquear else "DESBLOQUEAR"

            print(f"\n  🎯 Ação necessária: {acao}")
            print(f"  📌 API: {nome_api}")
            print(f"  👥 Processando {len(usuarios)} usuários...\n")

            usuarios_processados = 0
            usuarios_com_erro = 0

            for idx_user, nome_usuario in enumerate(usuarios, 1):
                print(f"    [{idx_user}/{len(usuarios)}] 👤 {nome_usuario}")

                if not buscar_usuario_por_nome(page, nome_usuario):
                    print(f"      ❌ Usuário não encontrado no Digisac")
                    registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                  "ERRO_NAO_ENCONTRADO", "Usuário não encontrado")
                    usuarios_com_erro += 1
                    continue

                if precisa_bloquear:
                    sucesso, msg = adicionar_restricao(page, nome_usuario, nome_api)

                    if sucesso:
                        print(f"      ✔ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "BLOQUEADO", msg)
                        usuarios_processados += 1
                    else:
                        print(f"      ❌ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "ERRO_BLOQUEAR", msg)
                        usuarios_com_erro += 1

                elif precisa_desbloquear:
                    sucesso, msg = remover_restricao(page, nome_usuario, nome_api)

                    if sucesso:
                        print(f"      ✔ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "DESBLOQUEADO", msg)
                        usuarios_processados += 1
                    else:
                        print(f"      ❌ {msg}")
                        registrar_log(telefone, nome_usuario, qual_antiga, qualidade, ts,
                                      "ERRO_DESBLOQUEAR", msg)
                        usuarios_com_erro += 1

            print(f"\n  📊 Resumo:")
            print(f"     ✔ Processados: {usuarios_processados}")
            print(f"     ❌ Erros: {usuarios_com_erro}")

            status_store[telefone] = qualidade

        browser.close()

    save_status_store(status_store)
    print("\n" + "="*60)
    print("🎉 Automação finalizada com sucesso!")
    print("="*60)


# ------------------------------
# DESBLOQUEIO MANUAL
# ------------------------------
def desbloquear_manual(telefone):
    """
    Executa o fluxo de DESBLOQUEIO apenas para o telefone informado.
    - Procura a última entrada da planilha para esse telefone (filtrar_hoje=False)
    - Se encontrar, chama automacao_digisac() com apenas esse registro
    """
    telefone_norm = re.sub(r'\D', '', str(telefone))
    if not telefone_norm:
        print("⚠ Telefone inválido.")
        return

    # Verifica configuração de mapa
    if telefone_norm not in MAPA_ESCALAS:
        print("⚠ Telefone não está no MAPA_ESCALAS. Verifique o número.")
        return

    # Carrega usuários
    usuarios = ler_csv_usuarios()
    if len(usuarios) == 0:
        print("⚠ CSV de usuários não contém usuários ativos. Aborte.")
        return

    # Carrega toda a planilha (não filtra por hoje) e procura última ocorrência do telefone
    planilha_todas = ler_planilha(filtrar_hoje=False)
    if not planilha_todas:
        print("⚠ Não há registros na planilha para buscar.")
        return

    # Normaliza telefones na planilha e encontra o mais recente (baseado em timestamp parseado)
    encontrados = []
    for item in planilha_todas:
        tel = re.sub(r'\D', '', str(item.get("telefone", "")))
        if tel == telefone_norm:
            # tenta extrair timestamp (pode ser vazio)
            dt = parse_timestamp(item.get("timestamp"))
            encontrados.append((dt, item))

    if not encontrados:
        print(f"⚠ Nenhum registro encontrado na planilha para o telefone {telefone_norm}")
        return

    # Escolhe o registro mais recente (dt pode ser None - colocamos no final)
    encontrados_sorted = sorted(encontrados, key=lambda x: (x[0] is None, x[0]), reverse=True)
    registro = encontrados_sorted[0][1]
    print(f"✔ Registro selecionado para desbloqueio: {registro}")

    # Processa somente esse registro
    automacao_digisac(usuarios, [registro])


# ================================
# MAIN
# ================================
def main():
    # Permite execução CLI para desbloqueio manual:
    # exemplo: python blocknumber.py desbloquear 5511936182483
    if len(sys.argv) >= 3 and sys.argv[1].lower() in ("desbloquear", "desbloquear_manual", "unlock"):
        telefone_arg = sys.argv[2]
        print(f"Modo: DESBLOQUEIO MANUAL para {telefone_arg}")
        desbloquear_manual(telefone_arg)
        return

    print("="*60)
    print("🚀 Script Digisac - Bloqueio/Desbloqueio de APIs")
    print(f"📅 Executando em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*60)

    planilha = ler_planilha(filtrar_hoje=True)
    usuarios = ler_csv_usuarios()

    if len(planilha) == 0:
        registrar_log("", "", "", "", "", "SEM_DADOS", "Nenhum registro de hoje na planilha")
        print("\n⚠ Nada a fazer - nenhum registro de hoje encontrado na planilha.")
        print("\n💡 DICA: Verifique se a planilha tem dados com a data de hoje.")
        print("   Se quiser processar todos os dados (ignorando a data), ")
        print("   altere 'filtrar_hoje=True' para 'filtrar_hoje=False' na função main()")
        return

    if len(usuarios) == 0:
        registrar_log("", "", "", "", "", "ERRO_CSV", "CSV sem usuários ativos")
        print("⚠ Nada a fazer - CSV não tem usuários ativos.")
        return

    print(f"\n📊 Resumo para processamento:")
    print(f"   • {len(planilha)} telefones para processar (de hoje)")
    print(f"   • {len(usuarios)} usuários ativos no CSV")
    print(f"   • {len(MAPA_ESCALAS)} APIs configuradas")

    automacao_digisac(usuarios, planilha)
    print("\n✔ Script concluído!")


if __name__ == "__main__":
    main()

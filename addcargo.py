# digisac_bulk_update_optimized.py
# Script Playwright (sync) - Otimizado para não recarregar página após salvar
# Após salvar, apenas limpa o filtro e pesquisa o próximo usuário

import os
import csv
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# -------- Config --------
CSV_PATH = "usuarios_digisac.csv"
LOG_JSON = "logs_results.json"
LOG_CSV = "logs_results.csv"
SCREENSHOT_DIR = "screenshots"

BASE_URL = "https://integralidademedica.digisac.co"
LOGIN_URL = f"{BASE_URL}/login"
USERS_URL = f"{BASE_URL}/users"

LOGIN_EMAIL = "suporte@solidasaude.com"
LOGIN_PASSWORD = "Solida@2025"

HEADLESS = False
DEFAULT_TIMEOUT = 20000  # ms
WAIT_SHORT = 300         # ms
WAIT_MED = 800           # ms
WAIT_LONG = 1400         # ms
PAUSE_AFTER_SAVE = 1000  # ms - aguarda a página atualizar após salvar

Path(SCREENSHOT_DIR).mkdir(exist_ok=True)

# -------- CSV helpers --------
def detect_delimiter(line: str) -> str:
    return ";" if line.count(";") >= line.count(",") else ","

def read_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        content = f.read()
    lines = [ln for ln in content.splitlines() if ln.strip() != ""]
    if not lines:
        return []
    delim = detect_delimiter(lines[0])
    reader = csv.reader(lines, delimiter=delim)
    rows = list(reader)
    if not rows:
        return []
    header = rows[0]
    clean_header = []
    for i, h in enumerate(header):
        s = str(h).strip() if h is not None else ""
        clean_header.append(s if s != "" else f"col_{i}")
    result = []
    for r in rows[1:]:
        if len(r) < len(clean_header):
            r = r + [""] * (len(clean_header) - len(r))
        elif len(r) > len(clean_header):
            r = r[: len(clean_header)]
        item = {k: (v.strip() if v is not None else "") for k, v in zip(clean_header, r)}
        result.append(item)
    return result

# -------- Logs --------
def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_csv(path: str, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

# -------- Utils --------
def screenshot_on_fail(page, nome: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = nome.replace(" ", "_").replace("/", "_")[:60] or "user"
    path = os.path.join(SCREENSHOT_DIR, f"fail_{safe_name}_{ts}.png")
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        try:
            page.screenshot(path=path)
        except Exception:
            pass
    return path

def wait_ms(page, ms: int):
    page.wait_for_timeout(ms)

def safe_print(msg: str):
    """Print seguro que não quebra com caracteres especiais"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'ignore').decode('ascii'))
    except Exception:
        pass

# -------- Main flow --------
def process_all():
    users = read_csv(CSV_PATH)
    if not users:
        safe_print(f"Aviso: CSV vazio ou não encontrado ({CSV_PATH}). Nada a processar.")
        return

    logs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        # Login
        try:
            page.goto(LOGIN_URL)
            page.get_by_test_id("login-input-email").click()
            page.get_by_test_id("login-input-email").fill(LOGIN_EMAIL)
            page.get_by_test_id("login-input-email").press("Tab")
            page.get_by_test_id("login-input-password").fill(LOGIN_PASSWORD)
            page.get_by_test_id("login-button-submit").click()
            wait_ms(page, WAIT_LONG)
            safe_print("Login realizado.")
        except Exception as exc:
            safe_print(f"Erro no login: {exc}")
            traceback.print_exc()
            browser.close()
            return

        # Navega para página de usuários APENAS UMA VEZ
        try:
            safe_print("Navegando para página de usuários...")
            page.goto(USERS_URL)
            wait_ms(page, WAIT_LONG)
            safe_print("Página de usuários carregada. Iniciando processamento...")
        except Exception as exc:
            safe_print(f"Erro ao navegar para usuários: {exc}")
            traceback.print_exc()
            browser.close()
            return

        for idx, row in enumerate(users):
            nome = row.get("Nome") or row.get("nome") or row.get("Name") or row.get("name") or row.get("col_0") or ""
            email_user = row.get("Email") or row.get("email") or row.get("col_1") or ""
            log = {"nome": nome, "email": email_user, "time": datetime.now(timezone.utc).isoformat(), "status": "pending", "message": ""}

            try:
                safe_print(f"\n{'='*60}")
                safe_print(f"[{idx+1}/{len(users)}] Processando: {nome}")
                safe_print(f"{'='*60}")
                
                # Se não for o primeiro usuário, aguarda a página atualizar após salvar anterior
                if idx > 0:
                    safe_print("Aguardando página atualizar após salvar usuário anterior...")
                    wait_ms(page, PAUSE_AFTER_SAVE)
                
                # Clica no filtro e digita o nome (não precisa limpar, já está em branco)
                safe_print("Clicando no campo de filtro...")
                page.get_by_test_id("users-list-input-filter").click()
                wait_ms(page, WAIT_SHORT)
                
                # Digita diretamente o nome do usuário atual
                safe_print(f"Digitando nome no filtro: {nome}")
                page.get_by_test_id("users-list-input-filter").fill(nome)
                wait_ms(page, WAIT_LONG)
                
                # Aguarda a lista filtrar
                safe_print("Aguardando lista filtrar...")
                wait_ms(page, WAIT_MED)

                # Clica no primeiro resultado (usuário filtrado)
                safe_print("Abrindo menu de ações...")
                page.get_by_test_id("users-list-button-actions-0").click()
                wait_ms(page, WAIT_SHORT)
                
                safe_print("Clicando em editar...")
                page.get_by_test_id("users-list-button-actions-0-edit").click()
                wait_ms(page, WAIT_LONG)

                # Abre o campo DEPARTAMENTO usando XPATH
                safe_print("Abrindo departamento pelo XPATH...")
                page.locator('xpath=//*[@id="departments"]/div[1]').click()
                wait_ms(page, WAIT_SHORT)

                # Seleciona ESCALAS II
                safe_print("Selecionando ESCALAS II...")
                page.get_by_role("option", name="ESCALAS II", exact=True).click()
                wait_ms(page, WAIT_SHORT)

                # Clica no ícone para adicionar outro departamento
                safe_print("Clicando para adicionar outro departamento...")
                page.locator(
                    r".nebula-ds.flex.w-full.items-center.border.bg-inputSelect-default-background.rounded-input.px-4.min-h-10.transition.ring-\[3px\] > .nebula-ds.flex > .css-1wy0on6 > div:nth-child(3) > .lucide"
                ).click()
                wait_ms(page, WAIT_SHORT)

                # Seleciona ESCALAS III
                safe_print("Selecionando ESCALAS III...")
                page.get_by_role("option", name="ESCALAS III").click()
                wait_ms(page, WAIT_SHORT)

                # Salva usuário
                safe_print("Salvando usuário...")
                page.get_by_test_id("users-form-button-save").click()
                
                # Aguarda o salvamento processar
                safe_print("Aguardando salvamento...")
                wait_ms(page, WAIT_LONG)

                log["status"] = "success"
                log["message"] = "Departamentos ESCALAS II e III adicionados com sucesso."
                safe_print(f"✓ [OK] Sucesso: {nome}")
                
                # NÃO recarrega a página - ela já atualiza automaticamente
                # Próximo loop já começará limpando o filtro e pesquisando o próximo nome
                
            except Exception as e:
                ss_path = ""
                try:
                    ss_path = screenshot_on_fail(page, nome)
                except Exception:
                    ss_path = ""
                log["status"] = "failed"
                log["message"] = f"{str(e)} | screenshot: {ss_path}\n{traceback.format_exc()}"
                safe_print(f"✗ [ERRO] Falha no usuário '{nome}': {e}")
                safe_print(f"  Screenshot salvo em: {ss_path}")

            finally:
                logs.append(log)

        browser.close()

    # Salvar logs
    save_json(LOG_JSON, logs)
    rows = []
    for l in logs:
        rows.append({"nome": l["nome"], "email": l["email"], "time": l["time"], "status": l["status"], "message": l["message"]})
    save_csv(LOG_CSV, rows)

    succ = sum(1 for x in logs if x["status"] == "success")
    fail = sum(1 for x in logs if x["status"] == "failed")
    safe_print(f"\n{'='*60}")
    safe_print(f"RESUMO FINAL")
    safe_print(f"{'='*60}")
    safe_print(f"Total processados: {len(logs)}")
    safe_print(f"✓ Sucesso: {succ}")
    safe_print(f"✗ Falhas: {fail}")
    safe_print(f"\nLogs salvos em:")
    safe_print(f"  - JSON: {LOG_JSON}")
    safe_print(f"  - CSV: {LOG_CSV}")
    if fail:
        safe_print(f"  - Screenshots: {SCREENSHOT_DIR}/")

if __name__ == "__main__":
    process_all()
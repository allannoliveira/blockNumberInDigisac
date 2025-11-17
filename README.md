
# Automatização de bloqueio — Digisac (Playwright + CSV)

Página de documentação e instruções para executar o script de automação que busca usuários no Digisac, aplica bloqueios e salva alterações a partir de uma lista CSV.

----------

## Conteúdo

-   Descrição
    
-   Pré-requisitos
    
-   Arquivos
    
-   Estrutura do CSV
    
-   Instalação
    
-   Uso
    
-   Logs e resultados
    
-   Dicas e solução de problemas
    
-   Licença
    

----------

## Descrição

Este repositório contém um script Python (Playwright sincronizado) que:

1.  Faz login no Digisac com e-mail e senha.
    
2.  Lê uma lista de usuários de um arquivo CSV.
    
3.  Para cada usuário, pesquisa no Digisac, abre o perfil (menu Ações → Editar), aplica um conjunto de seleções/blocos e salva.
    
4.  Retorna à lista e repete até processar todos os usuários.
    

O objetivo é automatizar o bloqueio/aplicação de tags/configurações por usuário com base no CSV.

----------

## Pré-requisitos

-   Python 3.8+
    
-   Playwright para Python
    
-   Navegador Chromium (Playwright instala automaticamente)
    
-   Acesso válido ao Digisac (e-mail e senha com permissão para editar usuários)
    
-   Arquivo CSV com a lista de usuários (texto separado por `;`)
    

----------

## Arquivos

-   `main.py` — script principal (Playwright).
    
-   `usuarios_digisac.csv` — lista de usuários a processar.
    
    -   Local (no ambiente atual): `/mnt/data/usuarios_digisac.csv`
        

> Observação: no repositório GitHub, substitua o link do CSV pelo local correto do seu storage/artefato, ou inclua o arquivo no repositório se apropriado. Para o ambiente de execução local, o path utilizado no script é o fornecido acima.

----------

## Estrutura do CSV esperado

O script atual espera um CSV com delimitador `;` e cabeçalho contendo ao menos as colunas:

`Nome;Email;Cargos;Departamentos;Tabela de horários;Status` 

Notas sobre formatos observados:

-   Algumas linhas podem ter a coluna `Nome` vazia e o nome real aparecer na coluna `Email` (ex.: `Adriele Souza - Escalas`). O script trata esse caso.
    
-   O script extrai apenas o nome real removendo sufixos após `-` (por exemplo, `- Escalas`, `- Escalistas`, `- Escalas II`, etc).
    
-   Arquivo lido com encoding `utf-8-sig` para suportar BOM.
    

**Local do CSV usado durante desenvolvimento/exemplo:**  
`/mnt/data/usuarios_digisac.csv`

(Se quiser usar outro arquivo, atualize a constante `CSV_FILE` no `main.py`.)

----------

## Instalação (rápido)

1.  Clone este repositório:
    

`git clone <repo-url> cd <repo-folder>` 

2.  Crie e ative ambiente virtual (opcional, recomendado):
    

`python -m venv .venv # Windows .venv\Scripts\activate # Linux / macOS  source .venv/bin/activate` 

3.  Instale dependências:
    

`pip install playwright
python -m playwright install` 

4.  Coloque o CSV no caminho esperado ou atualize `CSV_FILE` no script com o novo path.
    

----------

## Configuração (credenciais)

No `main.py`, altere as variáveis:

`DIGISAC_EMAIL = "seu_email@dominio.com" DIGISAC_PASSWORD = "sua_senha" CSV_FILE = r"C:\caminho\para\usuarios_digisac.csv"` 

Mantenha o arquivo CSV no encoding `utf-8`/`utf-8-sig`. Para ambientes mais seguros, considere usar variáveis de ambiente em vez de gravar credenciais em texto.

----------

## Execução

Execute o script com Python:

`python main.py` 

O Playwright abrirá uma janela do Chromium (modo não-headless por padrão) e o script fará o login e processará cada usuário listado no CSV.

----------

## Logs e relatórios

O script imprime no console o progresso (usuários processados, erros ao buscar ou salvar etc.).  
Sugestões de melhorias:

-   Gerar CSVs separados para `sucesso.csv` e `falha.csv`.
    
-   Salvar capturas de tela em pontos de erro (`page.screenshot(...)`) para diagnóstico.
    

----------

## Dicas e solução de problemas

-   **UnicodeEncodeError no Windows:** configure o terminal para UTF-8 antes de rodar `chcp 65001`, ou use prints sem emojis. O script de exemplo já usa mensagens compatíveis com Windows.
    
-   **Seletor não encontrado:** a interface do Digisac pode mudar. Inspecione os elementos (DevTools) e atualize os `data-testid` ou seletores no script.
    
-   **Tempo de carregamento:** se páginas carregarem devagar, aumente `time.sleep(...)` ou use `page.wait_for_selector(...)` mais robustos.
    
-   **Headless:** para rodar em background, altere `pw.chromium.launch(headless=False)` para `headless=True`. Teste em não-headless primeiro.
    
-   **Ambiente CI:** instale navegadores do Playwright (`python -m playwright install --with-deps`) e garanta dependências do sistema no runner.
    

----------

## Boas práticas de segurança

-   **Não** comite credenciais no Git. Use variáveis de ambiente ou cofre de segredos.
    
-   Teste o script com um CSV reduzido (2-3 usuários) antes de rodar em toda a base.
    
-   Considere adicionar confirmações manuais para operações destrutivas.
    

----------

## Exemplo de código (trecho)

Trecho de login e leitura do CSV (exemplo simplificado):

`from playwright.sync_api import sync_playwright import csv with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://integralidademedica.digisac.co/login")
    page.get_by_test_id("login-input-email").fill(DIGISAC_EMAIL)
    page.get_by_test_id("login-input-password").fill(DIGISAC_PASSWORD)
    page.get_by_test_id("login-button-submit").click() # leitura CSV CSV_FILE = "/mnt/data/usuarios_digisac.csv"  with  open(CSV_FILE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";") for row in reader:
        nome = row.get("Nome", "")
        ...` 

----------

## Referência ao arquivo de exemplo (CSV)

Arquivo de entrada usado no exemplo de desenvolvimento:

`/mnt/data/usuarios_digisac.csv`

> No GitHub, se preferir disponibilizar o CSV de exemplo no repositório, mova o arquivo para a raiz do repositório e atualize `CSV_FILE` com o caminho relativo.

----------

## Licença

Distribua conforme a política do seu projeto (por exemplo MIT). Adicione um arquivo `LICENSE` se desejar.

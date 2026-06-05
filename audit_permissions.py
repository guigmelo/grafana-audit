#!/usr/bin/env python3
"""
=============================================================================
 Script 2: Auditoria e Inventário de Permissões do Grafana
=============================================================================
 Varre todas as pastas e dashboards do Grafana, identifica permissões
 atribuídas diretamente a usuários nominais (não a times/teams) e exporta
 um relatório CSV de não conformidade.

 Níveis de permissão auditados:
   - 1 = Viewer
   - 2 = Editor
   - 4 = Admin

 Requisitos:
   - pip install requests python-dotenv
   - Configurar .env com GRAFANA_URL e GRAFANA_API_KEY

 Uso:
   python audit_permissions.py

 Saída:
   inventario_grafana.csv
=============================================================================
"""

import os
import sys
import csv
import json
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

load_dotenv()

GRAFANA_URL = os.getenv("GRAFANA_URL", "").rstrip("/")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY", "")

# Fallback: se não tiver API Key, usar Basic Auth
GRAFANA_ADMIN_USER = os.getenv("GRAFANA_ADMIN_USER", "")
GRAFANA_ADMIN_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "")

# Determinar modo de autenticação
if GRAFANA_API_KEY:
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GRAFANA_API_KEY}",
    }
    AUTH = None
    AUTH_MODE = "Bearer Token"
elif GRAFANA_ADMIN_USER:
    HEADERS = {"Content-Type": "application/json"}
    AUTH = (GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD)
    AUTH_MODE = "Basic Auth"
else:
    print("❌ Nenhuma credencial configurada. Defina GRAFANA_API_KEY ou GRAFANA_ADMIN_USER no .env")
    sys.exit(1)

# Nome do arquivo CSV de saída
CSV_OUTPUT = "inventario_grafana.csv"

# Mapeamento de níveis de permissão
PERMISSION_LABELS = {
    1: "Viewer",
    2: "Editor",
    4: "Admin",
}

# Cache de e-mails de usuários (evita chamadas repetidas à API)
_email_cache: dict[int, str] = {}


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def log_ok(msg: str):
    print(f"  ✅  {msg}")


def log_warn(msg: str):
    print(f"  ⚠️  {msg}")


def log_err(msg: str):
    print(f"  ❌  {msg}")


def log_section(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def api_get(endpoint: str, params: dict = None) -> requests.Response | None:
    """
    Faz uma requisição GET à API do Grafana com tratamento de erros.
    Retorna o objeto Response ou None em caso de erro de conexão.
    """
    url = f"{GRAFANA_URL}{endpoint}"
    try:
        resp = requests.get(url, headers=HEADERS, auth=AUTH, params=params, timeout=30)
        return resp
    except requests.exceptions.ConnectionError:
        log_err(f"Erro de conexão ao acessar {url}")
        return None
    except requests.exceptions.Timeout:
        log_err(f"Timeout ao acessar {url}")
        return None


def obter_email_usuario(user_id: int) -> str:
    """
    Obtém o e-mail de um usuário pelo ID, com cache para evitar chamadas repetidas.
    Usa /api/users/{id} (requer permissão de Admin).
    """
    if user_id in _email_cache:
        return _email_cache[user_id]

    resp = api_get(f"/api/users/{user_id}")
    if resp and resp.status_code == 200:
        data = resp.json()
        email = data.get("email", "")
        _email_cache[user_id] = email
        return email
    elif resp and resp.status_code == 403:
        # Token sem permissão para ver dados do usuário — tentar buscar via org users
        resp2 = api_get("/api/org/users")
        if resp2 and resp2.status_code == 200:
            for u in resp2.json():
                _email_cache[u.get("userId", u.get("id", 0))] = u.get("email", "")
            return _email_cache.get(user_id, f"user_id_{user_id}@desconhecido")
        _email_cache[user_id] = f"user_id_{user_id}@desconhecido"
        return _email_cache[user_id]
    else:
        _email_cache[user_id] = f"user_id_{user_id}@desconhecido"
        return _email_cache[user_id]


# ---------------------------------------------------------------------------
# Etapa 1: Listar todas as pastas
# ---------------------------------------------------------------------------

def listar_pastas() -> list[dict]:
    """
    Lista todas as pastas do Grafana via /api/folders com paginação.
    Retorna lista de dicts com uid, title e id de cada pasta.
    """
    log_section("ETAPA 1: Listando todas as pastas")

    todas_pastas = []
    page = 1
    limit = 100

    while True:
        resp = api_get("/api/folders", params={"limit": limit, "page": page})
        if not resp or resp.status_code != 200:
            if resp:
                log_err(f"Erro ao listar pastas (HTTP {resp.status_code})")
            break

        pastas = resp.json()
        if not pastas:
            break

        todas_pastas.extend(pastas)

        # Se recebeu menos que o limit, não há mais páginas
        if len(pastas) < limit:
            break
        page += 1

    log_ok(f"{len(todas_pastas)} pasta(s) encontrada(s)")
    for p in todas_pastas:
        print(f"      📁 {p['title']} (UID: {p['uid']})")

    return todas_pastas


# ---------------------------------------------------------------------------
# Etapa 2: Listar todos os dashboards
# ---------------------------------------------------------------------------

def listar_dashboards() -> list[dict]:
    """
    Lista todos os dashboards via /api/search?type=dash-db com paginação.
    Retorna lista de dicts com uid, title, folderUid e folderTitle.
    """
    log_section("ETAPA 2: Listando todos os dashboards")

    todos_dashboards = []
    page = 1
    limit = 100

    while True:
        resp = api_get("/api/search", params={"type": "dash-db", "limit": limit, "page": page})
        if not resp or resp.status_code != 200:
            if resp:
                log_err(f"Erro ao listar dashboards (HTTP {resp.status_code})")
            break

        dashboards = resp.json()
        if not dashboards:
            break

        todos_dashboards.extend(dashboards)

        if len(dashboards) < limit:
            break
        page += 1

    log_ok(f"{len(todos_dashboards)} dashboard(s) encontrado(s)")
    for d in todos_dashboards:
        folder_title = d.get("folderTitle", "General")
        print(f"      📊 {d['title']} (Pasta: {folder_title})")

    return todos_dashboards


# ---------------------------------------------------------------------------
# Etapa 3: Consultar permissões
# ---------------------------------------------------------------------------

def obter_permissoes_pasta(folder_uid: str) -> list[dict]:
    """Obtém permissões de uma pasta via /api/folders/{uid}/permissions."""
    resp = api_get(f"/api/folders/{folder_uid}/permissions")
    if resp and resp.status_code == 200:
        return resp.json()
    elif resp:
        log_warn(f"Não foi possível obter permissões da pasta UID={folder_uid} (HTTP {resp.status_code})")
    return []


def obter_permissoes_dashboard(dash_uid: str) -> list[dict]:
    """Obtém permissões de um dashboard via /api/dashboards/uid/{uid}/permissions."""
    resp = api_get(f"/api/dashboards/uid/{dash_uid}/permissions")
    if resp and resp.status_code == 200:
        return resp.json()
    elif resp:
        log_warn(f"Não foi possível obter permissões do dashboard UID={dash_uid} (HTTP {resp.status_code})")
    return []


# ---------------------------------------------------------------------------
# Etapa 4: Filtrar permissões não conformes
# ---------------------------------------------------------------------------

def filtrar_permissoes_nominais(permissoes: list[dict]) -> list[dict]:
    """
    Filtra permissões onde um usuário nominal (userId > 0) possui permissão
    diretamente atribuída (Viewer=1, Editor=2 ou Admin=4).

    Ignora:
    - Permissões de role (Org Viewer/Editor/Admin) — campo 'role' preenchido
    - Permissões de time (teamId > 0)
    - userLogin == 'admin' (admin built-in do Grafana)

    Retorna lista de permissões não conformes.
    """
    nao_conformes = []

    for perm in permissoes:
        user_id = perm.get("userId", 0)
        team_id = perm.get("teamId", 0)
        role = perm.get("role", "")
        permission_level = perm.get("permission", 0)
        user_login = perm.get("userLogin", "")

        # Ignorar permissões baseadas em role organizacional ou team
        if role:
            continue
        if team_id > 0:
            continue

        # Considerar apenas permissões de usuários nominais
        if user_id > 0 and permission_level in (1, 2, 4):
            # Ignorar o usuário admin built-in (opcional, mas recomendado)
            if user_login == "admin":
                continue
            nao_conformes.append(perm)

    return nao_conformes


# ---------------------------------------------------------------------------
# Etapa 5: Gerar CSV
# ---------------------------------------------------------------------------

def exportar_csv(registros: list[dict]):
    """
    Exporta os registros de não conformidade para o arquivo CSV.

    Colunas:
    - Tipo (Folder ou Dashboard)
    - Nome da Pasta Pai
    - Nome do Recurso
    - ID do Usuário
    - E-mail do Usuário
    - Nível de Permissão
    """
    log_section("ETAPA 5: Exportando relatório CSV")

    colunas = [
        "Tipo",
        "Nome da Pasta Pai",
        "Nome do Recurso",
        "ID do Usuário",
        "E-mail do Usuário",
        "Nível de Permissão",
    ]

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
        writer.writeheader()

        for reg in registros:
            writer.writerow(reg)

    log_ok(f"Relatório exportado para '{CSV_OUTPUT}' com {len(registros)} registro(s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  GRAFANA — Auditoria de Permissões Nominais")
    print("=" * 60)
    print(f"  URL:  {GRAFANA_URL}")
    print(f"  Auth: {AUTH_MODE}")
    print("=" * 60)

    # Verificar conectividade com o Grafana
    try:
        resp = requests.get(f"{GRAFANA_URL}/api/health", timeout=10)
        if resp.status_code != 200:
            log_err(f"Grafana não respondeu corretamente (HTTP {resp.status_code}).")
            sys.exit(1)
        log_ok("Conexão com Grafana estabelecida.")
    except requests.exceptions.ConnectionError:
        log_err(f"Não foi possível conectar ao Grafana em {GRAFANA_URL}")
        sys.exit(1)

    # Coletar dados
    pastas = listar_pastas()
    dashboards = listar_dashboards()

    # Criar mapa de UIDs de pastas para nomes (para referência nos dashboards)
    mapa_pastas = {p["uid"]: p["title"] for p in pastas}

    # Lista de todos os registros de não conformidade
    registros_nao_conformes = []

    # --- Auditar permissões das pastas ---
    log_section("ETAPA 3: Auditando permissões das pastas")

    for pasta in pastas:
        permissoes = obter_permissoes_pasta(pasta["uid"])
        nao_conformes = filtrar_permissoes_nominais(permissoes)

        if nao_conformes:
            print(f"\n  📁 Pasta '{pasta['title']}' — {len(nao_conformes)} permissão(ões) nominal(is)")

        for perm in nao_conformes:
            user_id = perm["userId"]
            email = perm.get("userEmail", "") or obter_email_usuario(user_id)
            nivel = PERMISSION_LABELS.get(perm["permission"], f"Desconhecido ({perm['permission']})")

            print(f"      👤 User ID={user_id} | {email} | {nivel}")

            registros_nao_conformes.append({
                "Tipo": "Folder",
                "Nome do Recurso": pasta["title"],
                "Nome da Pasta Pai": "—",
                "ID do Usuário": user_id,
                "E-mail do Usuário": email,
                "Nível de Permissão": nivel,
            })

    # --- Auditar permissões dos dashboards ---
    log_section("ETAPA 4: Auditando permissões dos dashboards")

    for dash in dashboards:
        dash_uid = dash["uid"]
        dash_title = dash["title"]
        folder_uid = dash.get("folderUid", "")
        folder_title = dash.get("folderTitle", "") or mapa_pastas.get(folder_uid, "General")

        permissoes = obter_permissoes_dashboard(dash_uid)
        nao_conformes = filtrar_permissoes_nominais(permissoes)

        if nao_conformes:
            print(f"\n  📊 Dashboard '{dash_title}' — {len(nao_conformes)} permissão(ões) nominal(is)")

        for perm in nao_conformes:
            user_id = perm["userId"]
            email = perm.get("userEmail", "") or obter_email_usuario(user_id)
            nivel = PERMISSION_LABELS.get(perm["permission"], f"Desconhecido ({perm['permission']})")

            print(f"      👤 User ID={user_id} | {email} | {nivel}")

            registros_nao_conformes.append({
                "Tipo": "Dashboard",
                "Nome do Recurso": dash_title,
                "Nome da Pasta Pai": folder_title,
                "ID do Usuário": user_id,
                "E-mail do Usuário": email,
                "Nível de Permissão": nivel,
            })

    # --- Exportar CSV ---
    exportar_csv(registros_nao_conformes)

    # --- Resumo final ---
    log_section("RESUMO DA AUDITORIA")
    print(f"  Pastas auditadas:       {len(pastas)}")
    print(f"  Dashboards auditados:   {len(dashboards)}")
    print(f"  Não conformidades:      {len(registros_nao_conformes)}")
    print(f"  Arquivo de saída:       {CSV_OUTPUT}")

    if registros_nao_conformes:
        print(f"\n  ⚠️  Foram encontradas {len(registros_nao_conformes)} permissão(ões) nominal(is)!")
        print(f"  Revise o arquivo '{CSV_OUTPUT}' para detalhes.\n")
    else:
        print(f"\n  ✅  Nenhuma permissão nominal encontrada. Tudo em conformidade! 🎉\n")


if __name__ == "__main__":
    main()

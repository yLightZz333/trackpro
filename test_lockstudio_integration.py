import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error
import threading
import time

sys.path.insert(0, r"C:\Users\SnyX\.gemini\antigravity\scratch\trackpro")

from server import TrackProHandler, HTTPServer, init_db, get_db, calculate_financial_metrics

def run_tests():
    print("=" * 60)
    print("INICIANDO SUÍTE DE TESTES AUTOMATIZADOS: TRACKPRO <-> LOCKSTUDIO")
    print("=" * 60)

    # Inicializa banco de dados e sementes
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # 1. Obter ou criar tokens de teste
    # User 1 (Lucas com dados)
    token_user_1 = "lst_live_test_user1_token_12345"
    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active)
        VALUES (1, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET token = excluded.token, active = 1
    """, (token_user_1,))

    # User 2 (Conta isolada / Novo Produtor)
    token_user_2 = "lst_live_test_user2_token_67890"
    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active)
        VALUES (2, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET token = excluded.token, active = 1
    """, (token_user_2,))

    # Token Revogado
    token_revoked = "lst_live_test_revoked_token_99999"
    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active)
        VALUES (3, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET token = excluded.token, active = 0
    """, (token_revoked,))

    conn.commit()
    conn.close()

    # Inicia servidor HTTP local em porta efêmera para os testes
    test_port = 8765
    server_address = ('127.0.0.1', test_port)
    httpd = HTTPServer(server_address, TrackProHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    base_url = f"http://127.0.0.1:{test_port}"

    def make_request(path, headers=None):
        req = urllib.request.Request(f"{base_url}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.getcode()
                body = json.loads(response.read().decode('utf-8'))
                return status, body
        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read().decode('utf-8'))
            return status, body

    # -------------------------------------------------------------
    # TESTE 1: Autenticação Válida com Bearer Token
    # -------------------------------------------------------------
    print("\n[TESTE 1] Autenticação Válida via Header 'Authorization: Bearer <TOKEN>' em /api/v1/metrics/summary...")
    status, body = make_request("/api/v1/metrics/summary?period=today", {
        "Authorization": f"Bearer {token_user_1}"
    })
    assert status == 200, f"Esperado 200, recebido {status}: {body}"
    assert body["success"] is True
    assert "data" in body and "meta" in body
    assert body["data"]["currency"] == "BRL"
    assert "ad_spend" in body["data"]
    assert "updated_at" in body["data"]
    assert body["meta"]["account_id"] == "account_1"
    print("✔ Passou: Status 200 e payload estruturado retornado com sucesso.")

    # -------------------------------------------------------------
    # TESTE 2: Autenticação com X-API-Key
    # -------------------------------------------------------------
    print("\n[TESTE 2] Autenticação via Header alternativo 'X-API-Key'...")
    status, body = make_request("/api/v1/metrics/summary?period=today", {
        "X-API-Key": token_user_1
    })
    assert status == 200, f"Esperado 200, recebido {status}: {body}"
    assert body["success"] is True
    print("✔ Passou: Header X-API-Key aceito e validado.")

    # -------------------------------------------------------------
    # TESTE 3: Autenticação Ausente (Sem Token)
    # -------------------------------------------------------------
    print("\n[TESTE 3] Requisição sem token (Autenticação Ausente)...")
    status, body = make_request("/api/v1/metrics/summary?period=today")
    assert status == 401, f"Esperado 401, recebido {status}: {body}"
    assert body["success"] is False
    assert body["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 4: Token Inválido
    # -------------------------------------------------------------
    print("\n[TESTE 4] Requisição com token inexistente / inválido...")
    status, body = make_request("/api/v1/metrics/summary?period=today", {
        "Authorization": "Bearer lst_live_token_que_nao_existe_123"
    })
    assert status == 401, f"Esperado 401, recebido {status}: {body}"
    assert body["success"] is False
    assert body["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 5: Token Revogado / Integração Desativada
    # -------------------------------------------------------------
    print("\n[TESTE 5] Requisição com token revogado (active = 0)...")
    status, body = make_request("/api/v1/metrics/summary?period=today", {
        "Authorization": f"Bearer {token_revoked}"
    })
    assert status == 401, f"Esperado 401, recebido {status}: {body}"
    assert body["success"] is False
    assert body["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 6: Isolamento entre Contas (User 1 vs User 2)
    # -------------------------------------------------------------
    print("\n[TESTE 6] Verificação de Isolamento entre Contas...")
    _, body_u1 = make_request("/api/v1/metrics/summary?period=all", {
        "Authorization": f"Bearer {token_user_1}"
    })
    _, body_u2 = make_request("/api/v1/metrics/summary?period=all", {
        "Authorization": f"Bearer {token_user_2}"
    })
    assert body_u1["meta"]["account_id"] == "account_1"
    assert body_u2["meta"]["account_id"] == "account_2"
    # User 1 possui dados reais, User 2 possui 0 pedidos
    assert body_u1["data"]["gross_revenue"] > 0
    assert body_u2["data"]["gross_revenue"] == 0.0
    print(f"✔ Passou: Conta 1 (Faturamento: R$ {body_u1['data']['gross_revenue']}) e Conta 2 (Faturamento: R$ {body_u2['data']['gross_revenue']}) estão estritamente isoladas.")

    # -------------------------------------------------------------
    # TESTE 7: Comparação de Indicadores com o Dashboard
    # -------------------------------------------------------------
    print("\n[TESTE 7] Comparação exata de valores: API LockStudio vs Dashboard...")
    # Chamada LockStudio
    _, ls_all = make_request("/api/v1/metrics/summary?period=all", {
        "Authorization": f"Bearer {token_user_1}"
    })
    # Chamada Dashboard
    _, dash_all = make_request("/api/dashboard?period=all", {
        "Authorization": f"Bearer {token_user_1}"
    })

    dash_kpis = dash_all["kpis"]
    ls_data = ls_all["data"]

    print(f"   Dashboard Gross: {dash_kpis['faturamento']} | LockStudio Gross: {ls_data['gross_revenue']}")
    print(f"   Dashboard Net:   {dash_kpis['faturamentoLiquido']} | LockStudio Net:   {ls_data['net_revenue']}")
    print(f"   Dashboard Profit:{dash_kpis['lucroReal']} | LockStudio Profit:{ls_data['profit']}")
    print(f"   Dashboard ROI:   {dash_kpis['roi']}% | LockStudio ROI:   {ls_data['roi']}%")
    print(f"   Dashboard Sales: {dash_kpis['vendasAprovadas']} | LockStudio Sales: {ls_data['sales_count']}")

    assert ls_data["gross_revenue"] == dash_kpis["faturamento"]
    assert ls_data["net_revenue"] == dash_kpis["faturamentoLiquido"]
    assert ls_data["profit"] == dash_kpis["lucroReal"]
    assert ls_data["roi"] == dash_kpis["roi"]
    assert ls_data["sales_count"] == dash_kpis["vendasAprovadas"]
    print("✔ Passou: 100% de paridade matemática exata entre Dashboard e API LockStudio!")

    # -------------------------------------------------------------
    # TESTE 8: Filtros de Período Suportados
    # -------------------------------------------------------------
    print("\n[TESTE 8] Validação de múltiplos períodos...")
    periods = ["today", "yesterday", "last_7_days", "last_30_days", "month", "all"]
    for p in periods:
        s, b = make_request(f"/api/v1/metrics/summary?period={p}", {
            "Authorization": f"Bearer {token_user_1}"
        })
        assert s == 200, f"Falha no período {p}: {b}"
        assert b["meta"]["period"] == p
        assert "date_range" in b["meta"]
        print(f"   Período '{p}': OK ({b['meta']['date_range']['start']} até {b['meta']['date_range']['end']})")
    print("✔ Passou: Todos os filtros de período responderam corretamente.")

    # -------------------------------------------------------------
    # TESTE 9: Telemetria de Requisições Atualizada
    # -------------------------------------------------------------
    print("\n[TESTE 9] Verificação de Telemetria (contador de requisições e IP)...")
    c = get_db()
    telemetry = c.execute("SELECT last_accessed_at, last_ip, request_count FROM lockstudio_integrations WHERE token = ?", (token_user_1,)).fetchone()
    c.close()
    assert telemetry["request_count"] > 0, "Contador de requisições deveria ser maior que 0"
    assert telemetry["last_accessed_at"] is not None
    assert telemetry["last_ip"] == "127.0.0.1"
    print(f"✔ Passou: Telemetria registrada com sucesso: {telemetry['request_count']} requisições, último IP: {telemetry['last_ip']}.")

    # -------------------------------------------------------------
    # TESTE 10: Endpoints de Gestão da Integração (Toggle, Token, Revoke)
    # -------------------------------------------------------------
    print("\n[TESTE 10] Testando endpoints de gestão (/api/integrations/lockstudio)...")
    session_token = "trackpro_lucas_permanent_token_2025"

    # GET status
    s, b = make_request("/api/integrations/lockstudio", {
        "Authorization": f"Bearer {session_token}"
    })
    assert s == 200
    assert b["integration"]["configured"] is True
    assert b["integration"]["active"] is True

    # POST toggle (desativar)
    req_toggle = urllib.request.Request(f"{base_url}/api/integrations/lockstudio/toggle",
        data=json.dumps({"active": False}).encode('utf-8'),
        headers={"Authorization": f"Bearer {session_token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_toggle) as resp:
        res_t = json.loads(resp.read().decode('utf-8'))
        assert res_t["success"] is True
        assert res_t["active"] is False

    # Verifica que agora a API rejeita chamadas feitas pelo LockStudio com o token
    s_rej, b_rej = make_request("/api/v1/metrics/summary?period=today", {
        "Authorization": f"Bearer {token_user_1}"
    })
    assert s_rej == 401, f"Esperado 401 após toggle off, recebido {s_rej}"

    # POST toggle (reativar pelo painel)
    req_toggle_on = urllib.request.Request(f"{base_url}/api/integrations/lockstudio/toggle",
        data=json.dumps({"active": True}).encode('utf-8'),
        headers={"Authorization": f"Bearer {session_token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_toggle_on) as resp:
        res_ton = json.loads(resp.read().decode('utf-8'))
        assert res_ton["success"] is True
        assert res_ton["active"] is True

    # Verifica que agora a API aceita chamadas do LockStudio novamente
    s_ok, _ = make_request("/api/v1/metrics/summary?period=today", {
        "Authorization": f"Bearer {token_user_1}"
    })
    assert s_ok == 200, f"Esperado 200 após toggle on, recebido {s_ok}"
    print("✔ Passou: Gerenciamento de ciclo de vida do token (ativar/pausar) funcionando perfeitamente.")

    httpd.shutdown()
    print("\n" + "=" * 60)
    print("TODOS OS 10 TESTES PASSARAM COM 100% DE SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

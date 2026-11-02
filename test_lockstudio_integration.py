"""
Testes de Integracao Automatizados da API de Metricas do LightLock / LockStudio.
Valida autenticacao Bearer/X-API-Key, cache em memoria de 60s, isolamento multi-tenant,
fuso horario de Brasilia (UTC-3), e o formato JSON exato requerido.
"""

import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer

# Adiciona o diretorio raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import TrackProHandler, get_db, init_db, invalidate_lightlock_cache

def run_tests():
    print("=" * 60)
    print("INICIANDO SUITE DE TESTES DA API LIGHTLOCK / LOCKSTUDIO")
    print("=" * 60)

    # 1. Inicia o banco de dados
    init_db()
    invalidate_lightlock_cache()

    # 2. Configura servidor de teste em porta livre
    test_port = 8991
    server_address = ('127.0.0.1', test_port)
    httpd = HTTPServer(server_address, TrackProHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{test_port}"
    print(f"Servidor de teste rodando em {base_url}")

    # 3. Garante tokens de teste no banco
    conn = get_db()
    cursor = conn.cursor()

    token_user_1 = "lst_live_test_token_user_1_lightlock"
    token_user_2 = "lst_live_test_token_user_2_another"
    token_revoked = "lst_live_test_token_revoked_account"

    cursor.execute("DELETE FROM lockstudio_integrations WHERE user_id IN (1, 2, 3) OR token IN (?, ?, ?)",
                   (token_user_1, token_user_2, token_revoked))

    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active, created_at, request_count)
        VALUES (1, ?, 1, datetime('now'), 0)
    """, (token_user_1,))

    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active, created_at, request_count)
        VALUES (2, ?, 1, datetime('now'), 0)
    """, (token_user_2,))

    cursor.execute("""
        INSERT INTO lockstudio_integrations (user_id, token, active, created_at, request_count)
        VALUES (3, ?, 0, datetime('now'), 0)
    """, (token_revoked,))

    conn.commit()
    conn.close()

    def make_request(path, headers=None):
        url = f"{base_url}{path}"
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as response:
                status = response.status
                body = json.loads(response.read().decode('utf-8'))
                return status, body
        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read().decode('utf-8'))
            return status, body

    # -------------------------------------------------------------
    # TESTE 1: Formato Exato do JSON no endpoint /api/v1/metrics/summary
    # -------------------------------------------------------------
    print("\n[TESTE 1] Validacao do formato exato requerido pelo LightLock...")
    t0 = time.time()
    status, body = make_request("/api/v1/metrics/summary", {
        "Authorization": f"Bearer {token_user_1}"
    })
    elapsed = time.time() - t0

    assert status == 200, f"Esperado 200, recebido {status}: {body}"
    assert elapsed < 2.0, f"Tempo de resposta excedeu 2s: {elapsed:.3f}s"

    # Verifica os 7 campos exatos
    required_fields = [
        "roi", "faturamento_bruto", "faturamento_liquido",
        "investimento", "lucro", "quantidade_vendas", "updated_at"
    ]
    for field in required_fields:
        assert field in body, f"Campo obrigatorio ausente no JSON: {field}"

    assert isinstance(body["roi"], (int, float))
    assert isinstance(body["faturamento_bruto"], (int, float))
    assert isinstance(body["faturamento_liquido"], (int, float))
    assert isinstance(body["investimento"], (int, float))
    assert isinstance(body["lucro"], (int, float))
    assert isinstance(body["quantidade_vendas"], int)
    assert isinstance(body["updated_at"], str)
    assert body["updated_at"].endswith("-03:00"), f"Fuso de Brasilia invalido: {body['updated_at']}"

    print(f"✔ Passou: Formato exato retornado em {elapsed*1000:.2f}ms: {body}")

    # -------------------------------------------------------------
    # TESTE 2: Cache em Memoria com TTL de 60 segundos
    # -------------------------------------------------------------
    print("\n[TESTE 2] Validacao do Cache em memoria (TTL 60s)...")
    t1 = time.time()
    s_cache, b_cache = make_request("/api/v1/metrics/summary", {
        "Authorization": f"Bearer {token_user_1}"
    })
    cached_elapsed = time.time() - t1
    assert s_cache == 200
    assert b_cache["updated_at"] == body["updated_at"], "O timestamp deve ser identico no cache de 60s"
    assert cached_elapsed < 0.1, f"Cache hit deve ser instantaneo (<100ms), levou {cached_elapsed*1000:.2f}ms"
    print(f"✔ Passou: Cache hit respondido em {cached_elapsed*1000:.2f}ms.")

    # -------------------------------------------------------------
    # TESTE 3: Formato Envelope via ?format=envelope ou /api/v1/lockscreen/summary
    # -------------------------------------------------------------
    print("\n[TESTE 3] Validacao do Envelope completo para retrocompatibilidade...")
    status_env, body_env = make_request("/api/v1/metrics/summary?format=envelope", {
        "Authorization": f"Bearer {token_user_1}"
    })
    assert status_env == 200
    assert body_env["success"] is True
    assert "data" in body_env and "meta" in body_env
    assert body_env["data"]["faturamento_bruto"] == body["faturamento_bruto"]
    assert body_env["data"]["lucro"] == body["lucro"]
    print("✔ Passou: Envelope de compatibilidade retornado com sucesso.")

    # -------------------------------------------------------------
    # TESTE 4: Autenticacao via Header alternativo X-API-Key
    # -------------------------------------------------------------
    print("\n[TESTE 4] Autenticacao via Header alternativo 'X-API-Key'...")
    status, body_key = make_request("/api/v1/metrics/summary", {
        "X-API-Key": token_user_1
    })
    assert status == 200, f"Esperado 200, recebido {status}: {body_key}"
    assert "faturamento_bruto" in body_key
    print("✔ Passou: Header X-API-Key aceito e validado.")

    # -------------------------------------------------------------
    # TESTE 5: Autenticacao Ausente (Sem Token) -> HTTP 401
    # -------------------------------------------------------------
    print("\n[TESTE 5] Requisicao sem token (Autenticacao Ausente)...")
    status, body_err = make_request("/api/v1/metrics/summary")
    assert status == 401, f"Esperado 401, recebido {status}: {body_err}"
    assert body_err["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 6: Token Invalido -> HTTP 401
    # -------------------------------------------------------------
    print("\n[TESTE 6] Requisicao com token inexistente / invalido...")
    status, body_inv = make_request("/api/v1/metrics/summary", {
        "Authorization": "Bearer token_que_nao_existe_123"
    })
    assert status == 401, f"Esperado 401, recebido {status}: {body_inv}"
    assert body_inv["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 7: Token Revogado (active = 0) -> HTTP 401
    # -------------------------------------------------------------
    print("\n[TESTE 7] Requisicao com token revogado (active = 0)...")
    status, body_rev = make_request("/api/v1/metrics/summary", {
        "Authorization": f"Bearer {token_revoked}"
    })
    assert status == 401, f"Esperado 401, recebido {status}: {body_rev}"
    assert body_rev["error"] == "Token inválido"
    print("✔ Passou: Rejeitado com HTTP 401 e error 'Token inválido'.")

    # -------------------------------------------------------------
    # TESTE 8: Isolamento entre Contas (User 1 vs User 2)
    # -------------------------------------------------------------
    print("\n[TESTE 8] Verificacao de Isolamento entre Contas...")
    _, body_u1 = make_request("/api/v1/metrics/summary?period=all", {
        "Authorization": f"Bearer {token_user_1}"
    })
    _, body_u2 = make_request("/api/v1/metrics/summary?period=all", {
        "Authorization": f"Bearer {token_user_2}"
    })
    assert body_u1["faturamento_bruto"] >= 0
    assert body_u2["faturamento_bruto"] == 0.0
    print(f"✔ Passou: Conta 1 (Faturamento: R$ {body_u1['faturamento_bruto']}) e Conta 2 (Faturamento: R$ {body_u2['faturamento_bruto']}) estao estritamente isoladas.")

    # -------------------------------------------------------------
    # TESTE 9: Comparacao de Indicadores com o Dashboard
    # -------------------------------------------------------------
    print("\n[TESTE 9] Comparacao exata de valores: API LightLock vs Dashboard...")
    _, dash_all = make_request("/api/dashboard?period=all", {
        "Authorization": f"Bearer {token_user_1}"
    })
    dash_kpis = dash_all["kpis"]

    assert body_u1["faturamento_bruto"] == dash_kpis["faturamento"]
    assert body_u1["faturamento_liquido"] == dash_kpis["faturamentoLiquido"]
    assert body_u1["lucro"] == dash_kpis["lucroReal"]
    assert body_u1["roi"] == dash_kpis["roi"]
    assert body_u1["quantidade_vendas"] == dash_kpis["vendasAprovadas"]
    print("✔ Passou: 100% de paridade matematica exata entre Dashboard e API LightLock!")

    # -------------------------------------------------------------
    # TESTE 10: Telemetria de Requisicoes e Status
    # -------------------------------------------------------------
    print("\n[TESTE 10] Verificacao de Telemetria (contador de requisicoes e IP)...")
    c = get_db()
    telemetry = c.execute("SELECT last_accessed_at, last_ip, request_count FROM lockstudio_integrations WHERE token = ?", (token_user_1,)).fetchone()
    c.close()
    assert telemetry["request_count"] > 0
    assert telemetry["last_accessed_at"] is not None
    assert telemetry["last_ip"] == "127.0.0.1"
    print(f"✔ Passou: Telemetria registrada com sucesso: {telemetry['request_count']} requisicoes, IP: {telemetry['last_ip']}.")

    httpd.shutdown()
    print("\n" + "=" * 60)
    print("TODOS OS 10 TESTES PASSARAM COM 100% DE SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

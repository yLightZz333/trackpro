# Contrato Oficial da API — Integração TrackPro + LockStudio

Este documento define as especificações técnicas, contrato de dados e diretrizes de integração entre o sistema de rastreamento **TrackPro** e o aplicativo Android **LockStudio**, para exibição de indicadores financeiros na tela de bloqueio do smartphone (POCO M3 Pro 5G).

---

## 1. Visão Geral da Arquitetura

O **TrackPro** é a fonte da verdade para todas as métricas financeiras. Ele ingere vendas via webhooks nativos e postbacks (Pagar.me, Kiwify, Hotmart, Greenn, Cakto, Wiapy, Universal), sincroniza custos de anúncios (Meta Ads CAPI e Insights) e aplica taxas e impostos parametrizados pelo usuário.

```
┌─────────────────────────────────┐
│         Meta Ads / Gateways     │
└────────────────┬────────────────┘
                 │ (Webhooks & Insights)
                 ▼
┌─────────────────────────────────┐
│        TrackPro Backend         │ ◄─── SQLite (orders, campaigns, financial_settings)
│  (https://meutrackpro.onrender.com)
└────────────────┬────────────────┘
                 │ GET /api/v1/lockscreen/summary
                 │ Authorization: Bearer <TOKEN>
                 ▼
┌─────────────────────────────────┐
│     LockStudio (Android App)    │ ───► Widgets na Tela de Bloqueio
│        (POCO M3 Pro 5G)         │      (ROI, Lucro, Faturamento, Vendas)
└─────────────────────────────────┘
```

---

## 2. Endereço do Servidor & Segurança

* **Ambiente de Produção (HTTPS Obrigatório):**
  ```text
  https://meutrackpro.onrender.com
  ```
  *(Nunca utilize `localhost` ou `127.0.0.1` no celular físico, pois apontaria para o próprio dispositivo Android).*

* **Permissão de Acesso:** Estritamente **Read-Only** (somente leitura). O token do LockStudio não possui permissão para criar, alterar ou excluir nenhum dado, pedido ou configuração no rastreador.

---

## 3. Autenticação

Todas as chamadas à API exigem o token individual de integração gerado na interface do TrackPro (`Integrações → LockStudio`).

### Cabeçalhos Suportados (escolha um):

1. **Recomendado (Padrão OAuth2/Bearer):**
   ```http
   Authorization: Bearer lst_live_SEU_TOKEN_AQUI
   ```

2. **Alternativo (API Key direta):**
   ```http
   X-API-Key: lst_live_SEU_TOKEN_AQUI
   ```
   *ou*
   ```http
   x-api-token: lst_live_SEU_TOKEN_AQUI
   ```

3. **Fallback para widgets simples (Query param):**
   ```text
   ?token=lst_live_SEU_TOKEN_AQUI
   ```

---

## 4. Endpoint de Indicadores Financeiros

### `GET /api/v1/lockscreen/summary`

Retorna o resumo consolidado de indicadores para alimentar os widgets da tela de bloqueio.

### Parâmetros de Consulta (Query String)

| Parâmetro | Tipo | Padrão | Descrição | Valores Aceitos |
| :--- | :--- | :--- | :--- | :--- |
| `period` | string | `today` | Período de apuração dos dados | `today`, `yesterday`, `last_7_days`, `last_30_days`, `month`, `all`, `custom` |
| `start_date` | string | `null` | Data inicial (apenas se `period=custom`) | Formato `YYYY-MM-DD` (ex: `2026-11-01`) |
| `end_date` | string | `null` | Data final (apenas se `period=custom`) | Formato `YYYY-MM-DD` (ex: `2026-11-01`) |

*Fuso Horário Aplicado:* `America/Sao_Paulo` (UTC-03:00) em todos os cálculos.

---

## 5. Contrato de Resposta (JSON)

### Exemplo de Resposta de Sucesso (HTTP 200 OK)

```json
{
  "success": true,
  "data": {
    "roi": 145.2,
    "net_revenue": 1820.50,
    "gross_revenue": 2150.00,
    "investment": 740.00,
    "profit": 1080.50,
    "sales_count": 22,
    "roas": 2.91,
    "average_ticket": 97.73,
    "pending_sales_count": 8,
    "pending_revenue": 776.00
  },
  "meta": {
    "currency": "BRL",
    "timezone": "America/Sao_Paulo",
    "generated_at": "2026-11-01T23:15:00-03:00",
    "period": "today",
    "date_range": {
      "start": "2026-11-01",
      "end": "2026-11-01"
    },
    "account_id": "account_1"
  }
}
```

### Dicionário de Campos de `data`

| Campo | Tipo | Unidade | Descrição | Regra de Cálculo Oficial |
| :--- | :--- | :--- | :--- | :--- |
| `roi` | `float` | `%` | Retorno sobre o Investimento | `((profit / investment) * 100.0)` *(0.0 se sem investimento)* |
| `net_revenue` | `float` | `R$` | Faturamento Líquido Real | `Faturamento Bruto - Taxas Gateway - Impostos` |
| `gross_revenue`| `float` | `R$` | Faturamento Bruto Aprovado | Soma do valor de todos os pedidos com status `paid` no período |
| `investment` | `float` | `R$` | Gasto com Anúncios (Ads) | Total investido em campanhas de tráfego pago no período |
| `profit` | `float` | `R$` | Lucro Real da Operação | `Faturamento Líquido - Investimento - Custos de Produto` |
| `sales_count` | `integer`| un | Quantidade de Vendas | Total de pedidos únicos aprovados (`status = 'paid'`) |
| `roas` | `float` | ratio | Retorno sobre Gasto de Anúncios| `gross_revenue / investment` |
| `average_ticket`| `float`| `R$` | Ticket Médio por Venda | `gross_revenue / sales_count` |
| `pending_sales_count` | `integer` | un | Vendas Pendentes | Quantidade de PIX/Boletos aguardando pagamento |
| `pending_revenue` | `float` | `R$` | Valor Total Pendente | Soma em R$ dos pedidos com status `waiting_payment` |

---

## 6. Tratamento de Erros e Códigos HTTP

Todos os erros retornam um corpo JSON padronizado com o código de erro específico:

### 1. Token Ausente (HTTP 401 Unauthorized)
```json
{
  "success": false,
  "error": "Autenticação obrigatória. Envie seu token no cabeçalho 'Authorization: Bearer <TOKEN>' ou 'X-API-Key: <TOKEN>'.",
  "code": "UNAUTHORIZED"
}
```

### 2. Token Inválido (HTTP 401 Unauthorized)
```json
{
  "success": false,
  "error": "Token de autenticação inválido.",
  "code": "INVALID_TOKEN"
}
```

### 3. Token Revogado ou Integração Pausada (HTTP 403 Forbidden)
```json
{
  "success": false,
  "error": "A integração com o LockStudio está desativada ou este token foi revogado.",
  "code": "TOKEN_REVOKED"
}
```

---

## 7. Exemplos Práticos de Requisição

### cURL (Linux / macOS / PowerShell)
```bash
curl -X GET "https://meutrackpro.onrender.com/api/v1/lockscreen/summary?period=today" \
     -H "Authorization: Bearer lst_live_trackpro_default_token_2026" \
     -H "Accept: application/json"
```

### Kotlin (Android / LockStudio com OkHttp)
```kotlin
val client = OkHttpClient()

val request = Request.Builder()
    .url("https://meutrackpro.onrender.com/api/v1/lockscreen/summary?period=today")
    .addHeader("Authorization", "Bearer lst_live_trackpro_default_token_2026")
    .addHeader("Accept", "application/json")
    .build()

client.newCall(request).enqueue(object : Callback {
    override fun onFailure(call: Call, e: IOException) {
        // Tratar falha de rede ou timeout
    }

    override fun onResponse(call: Call, response: Response) {
        if (response.isSuccessful) {
            val jsonString = response.body?.string()
            // Atualizar os widgets na tela de bloqueio com os dados
        }
    }
})
```

---

## 8. Diretrizes de Consumo e Frequência para Android

1. **Intervalo Recomendado:** Entre **15 e 30 minutos** (via `WorkManager` do Android).
2. **Evitar Polling Agressivo:** Requisições a cada poucos segundos não trazem ganho visual e desgastam a bateria do POCO M3 Pro 5G.
3. **Cache Inteligente:** Se o dispositivo estiver offline ou em modo de economia de energia, o widget deve manter exibido o último dado recebido com indicador discreto da hora da última atualização (`generated_at`).

---

## 9. Gerenciamento do Token pelo Painel do TrackPro

Na aba **Integrações → LockStudio** do TrackPro:
* **Gerar Novo Token:** Invalida o token anterior e exibe a nova credencial completa uma única vez.
* **Pausar Integração:** Suspende temporariamente as requisições (retorna HTTP 403 sem apagar o token).
* **Revogar Token:** Cancela permanentemente a credencial para impedir acessos.
* **Telemetria:** O painel exibe data/hora da última requisição do celular, endereço IP de origem e contador acumulado de consultas.

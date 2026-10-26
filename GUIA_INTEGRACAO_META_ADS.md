# 🚀 Guia Oficial de Configuração — Meta Ads (Facebook) no TrackPro

Este guia passo a passo detalha a configuração do seu aplicativo no **Meta for Developers** para conectar contas de anúncio, sincronizar campanhas e importar métricas em tempo real no TrackPro.

---

## 📌 1. Visão Geral da Arquitetura e Permissões

O TrackPro utiliza o fluxo padrão de **OAuth 2.0 oficial da Meta** com troca de token de curta duração por um **Token de Longa Duração (60 dias)**.

* **Escopos solicitados**:
  * `ads_read` *(Central e obrigatório: leitura de contas de anúncio, campanhas, conjuntos, criativos e métricas/insights)*
  * `public_profile` *(Identificação do nome e ID do usuário autenticado)*
* **Atenção**: Não solicitamos `ads_management` neste fluxo para permitir que você utilize a integração de imediato no modo de desenvolvimento ou sem barreiras burocráticas de App Review restrito.

---

## 🛠️ 2. Passo a Passo no Meta for Developers

### Passo 2.1 — Criar o Aplicativo Meta
1. Acesse o painel de desenvolvedores: [developers.facebook.com/apps](https://developers.facebook.com/apps).
2. Clique no botão verde **"Criar aplicativo"** (Create App).
3. Selecione o tipo de aplicativo:
   * Escolha **"Outro"** (Other) ou **"Empresa / Negócios"** (Business).
   * Clique em **Avançar**.
4. Defina o nome de exibição do aplicativo (ex: `TrackPro Ads Manager`) e informe seu e-mail de contato comercial.
5. Selecione sua Conta Empresarial (Business Manager) se desejar e clique em **Criar aplicativo**.

---

### Passo 2.2 — Adicionar o Produto "Facebook Login para Empresas"
1. No painel do seu aplicativo, localize a seção **"Adicionar produtos ao seu app"**.
2. No card **"Facebook Login para Empresas"** (ou *Facebook Login for Business*), clique em **Configurar** (Set Up).
3. No menu lateral esquerdo, vá em **Facebook Login para Empresas → Configurações** (Settings).

---

### Passo 2.3 — Configurar URIs de Redirecionamento Válidas
Na página de configurações do Facebook Login, localize o campo:
**URIs de redirecionamento do OAuth válidos** (*Valid OAuth Redirect URIs*).

Adicione exatamente estas URLs:

```text
https://meutrackpro.onrender.com/api/integrations/meta/callback
https://trackpro-g781.onrender.com/api/integrations/meta/callback
https://meutrackpro.onrender.com/api/auth/facebook/callback
https://trackpro-g781.onrender.com/api/auth/facebook/callback
http://localhost:3000/api/integrations/meta/callback
http://localhost:3001/api/integrations/meta/callback
```

---

### Passo 2.4 — Copiar o App ID e App Secret
1. No menu lateral esquerdo, vá em **Configurações do aplicativo → Básico** (*App Settings → Basic*).
2. Localize:
   * **ID do Aplicativo** (*App ID*): copie este número.
   * **Chave Secreta do Aplicativo** (*App Secret*): clique em "Mostrar", digite sua senha e copie o código alfanumérico.

---

### Passo 2.5 — Modo de Desenvolvimento vs. Produção
Por padrão, todo aplicativo é criado em **Modo de Desenvolvimento** (*Development Mode*).
* **Para usar imediatamente**: você (administrador do app) e qualquer conta adicionada na aba **Funções do aplicativo → Funções** (*Roles*) podem fazer login e sincronizar campanhas instantaneamente sem passar por App Review da Meta!

---

## ⚡ 3. Ativar no Painel do TrackPro

1. Abra o seu painel TrackPro em produção: [https://meutrackpro.onrender.com/](https://meutrackpro.onrender.com/).
2. Acesse a aba **Contas** no menu lateral ou clique no botão **"Conectar conta Meta"**.
3. Se as credenciais ainda não estiverem configuradas, o modal oficial abrirá:
   * Cole seu **App ID**
   * Cole seu **App Secret**
   * Clique em **Salvar e Conectar com a Meta**.
4. Uma janela pop-up oficial do Facebook abrirá.
5. Selecione suas Contas de Anúncio, confirme as permissões (`ads_read`) e clique em **Concluir**.
6. A janela fechará automaticamente e todas as suas contas de anúncio aparecerão no TrackPro com suas respectivas moedas, fusos horários e campanhas sincronizadas!

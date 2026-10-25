# TrackPro — Rastreamento Server-Side & Meta Ads CAPI (Clone UTMify)

Plataforma de atribuição de tráfego pago para uso pessoal, com suporte nativo para **Greenn**, **Hotmart**, **Cakto**, **Kiwify**, **Wiapy** e envio automático de vendas para a **Meta Conversions API (CAPI)**.

## 🚀 Publicar na Vercel (1 Clique)

1. Suba este repositório para o seu GitHub:
   ```bash
   git init
   git add .
   git commit -m "feat: TrackPro Engine 2.0"
   git remote add origin https://github.com/SEU-USER/trackpro.git
   git push -u origin main
   ```
2. Acesse [vercel.com](https://vercel.com) e importe o repositório.
3. Clique em **Deploy**. A Vercel gerará o domínio público com HTTPS gratuito (ex: `https://trackpro-xyz.vercel.app`).

## 📱 Instalar no Celular como App (PWA)
- **iPhone (Safari)**: Abra o link, clique no ícone de Compartilhar e selecione **"Adicionar à Tela de Início"**.
- **Android (Chrome)**: Abra o link, clique no menu de 3 pontinhos e selecione **"Instalar Aplicativo"**.

## 🔗 Endpoints de Webhook
- **Universal**: `https://SEU-DOMINIO/api/webhook/orders`
- **Kiwify**: `https://SEU-DOMINIO/api/webhook/kiwify`
- **Hotmart**: `https://SEU-DOMINIO/api/webhook/hotmart`
- **Greenn**: `https://SEU-DOMINIO/api/webhook/greenn`
- **Cakto**: `https://SEU-DOMINIO/api/webhook/cakto`
- **Wiapy**: `https://SEU-DOMINIO/api/webhook/wiapy`

## 🌐 Pixel para Landing Page (Link Forwarder)
Insira no `<head>` da sua página:
```html
<script src="https://SEU-DOMINIO/tracking/pixel.js?token=a8b3c4d5-e6f7-4a1b-9c8d-123456789abc"></script>
```
O script captura UTMs e injeta automaticamente em todos os botões de compra para Kiwify, Hotmart, Greenn, Cakto e Wiapy.
"# trackpro" 

# Discord Filter Bot 🛡️

Bot de moderação para Discord que filtra mensagens automaticamente com base em:

- 🚫 Palavras/expressões proibidas (lista configurável)
- 🔗 Links não autorizados e convites de outros servidores Discord
- 📢 Excesso de menções (@everyone, @role, @user em massa)
- 🔠 Excesso de CAIXA ALTA
- ⚡ Spam (mensagens repetidas em curto intervalo de tempo)

Quando uma mensagem viola uma regra, o bot:
1. Apaga a mensagem
2. Avisa o autor no canal (aviso some sozinho após alguns segundos)
3. Registra a ocorrência em um canal de logs (`#mod-logs`)
4. Aplica **timeout automático** após X advertências acumuladas

---

## 📁 Estrutura do projeto

```
discord-filter-bot/
├── bot.py            # Código principal do bot
├── config.json        # Regras de filtragem (edite conforme necessário)
├── requirements.txt   # Dependências Python
├── .env.example        # Modelo de variáveis de ambiente
├── .gitignore
└── README.md
```

---

## 🚀 Passo 1 — Criar o bot no Discord Developer Portal

1. Acesse https://discord.com/developers/applications
2. Clique em **New Application**, dê um nome e crie.
3. No menu lateral, vá em **Bot** → **Add Bot**.
4. Em **Privileged Gateway Intents**, ative:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
5. Clique em **Reset Token** e copie o token gerado (você vai usar no `.env`).
6. Vá em **OAuth2 → URL Generator**:
   - Em **Scopes**, marque `bot`.
   - Em **Bot Permissions**, marque: `Manage Messages`, `Moderate Members` (timeout), `Send Messages`, `Read Message History`, `View Channels`.
   - Copie o link gerado e abra no navegador para convidar o bot ao seu servidor.

---

## 💻 Passo 2 — Rodar localmente

```bash
# Clone o repositório
git clone https://github.com/SEU-USUARIO/discord-filter-bot.git
cd discord-filter-bot

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Configure o token
cp .env.example .env
# Edite o .env e cole seu token do Discord
```

Edite `config.json` para ajustar palavras proibidas, domínios bloqueados, limites de spam etc.

No seu servidor Discord, crie um canal de texto chamado **`mod-logs`** (ou ajuste o nome em `config.json` → `log_channel_name`).

Execute o bot:

```bash
python bot.py
```

---

## ⚙️ Comandos disponíveis (requerem permissão de moderação)

| Comando | Descrição |
|---|---|
| `!filtro-status` | Mostra as regras de filtragem ativas |
| `!reload-config` | Recarrega o `config.json` sem reiniciar o bot (admin) |
| `!limpar-avisos @usuário` | Zera as advertências de um usuário |

---

## 📤 Passo 3 — Subir para o GitHub

```bash
git init
git add .
git commit -m "Bot de filtragem de mensagens para Discord"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/discord-filter-bot.git
git push -u origin main
```

> ⚠️ O `.env` está no `.gitignore` e **não** será enviado ao GitHub — nunca compartilhe seu token publicamente. Se ele vazar, gere um novo em **Bot → Reset Token**.

---

## ☁️ Hospedagem (24/7)

Para o bot ficar online continuamente, hospede em um serviço como:
- [Railway](https://railway.app)
- [Render](https://render.com)
- Uma VPS (com `screen`, `tmux` ou `systemd` + `pm2`)

Em qualquer um deles, configure a variável de ambiente `DISCORD_TOKEN` no painel do serviço (em vez do arquivo `.env`) e defina o comando de start como `python bot.py`.

---

## 🛠️ Personalização

Todas as regras ficam em `config.json` — não é necessário mexer no código para:
- Adicionar/remover palavras e domínios proibidos
- Ajustar limites de menções, CAPS LOCK e spam
- Definir cargos isentos do filtro (`exempt_roles`)
- Mudar quantas advertências geram timeout, e por quanto tempo

## 📄 Licença

MIT — use, modifique e distribua livremente.

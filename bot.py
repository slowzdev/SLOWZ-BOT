"""
Discord Filter Bot
-------------------
Bot de moderação que filtra mensagens no servidor com base em:
- Palavras/expressões proibidas
- Links não autorizados (convites de outros servidores, domínios bloqueados)
- Spam (mensagens repetidas / excesso de menções / excesso de maiúsculas)

Autor: você :)
Licença: MIT
"""

import os
import re
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("filter-bot")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config(CONFIG_PATH)

BANNED_WORDS = [w.lower() for w in config.get("banned_words", [])]
BANNED_DOMAINS = [d.lower() for d in config.get("banned_domains", [])]
BLOCK_DISCORD_INVITES = config.get("block_discord_invites", True)
MAX_MENTIONS = config.get("max_mentions", 5)
MAX_CAPS_PERCENT = config.get("max_caps_percent", 70)
MIN_LENGTH_FOR_CAPS_CHECK = config.get("min_length_for_caps_check", 10)
SPAM_MESSAGE_LIMIT = config.get("spam_message_limit", 5)
SPAM_TIME_WINDOW = config.get("spam_time_window_seconds", 7)
LOG_CHANNEL_NAME = config.get("log_channel_name", "mod-logs")
EXEMPT_ROLES = [r.lower() for r in config.get("exempt_roles", [])]
WARN_LIMIT_BEFORE_TIMEOUT = config.get("warn_limit_before_timeout", 3)
TIMEOUT_MINUTES = config.get("timeout_minutes", 10)
DELETE_NOTICE_SECONDS = config.get("delete_notice_seconds", 6)

INVITE_REGEX = re.compile(
    r"(discord\.gg|discord(app)?\.com/invite)/[a-zA-Z0-9-]+", re.IGNORECASE
)
URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.get("command_prefix", "!"), intents=intents)

# Estado em memória para detecção de spam e advertências
user_message_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
user_warnings: dict[int, int] = defaultdict(int)


# ---------------------------------------------------------------------------
# Funções auxiliares de filtragem
# ---------------------------------------------------------------------------

def is_exempt(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    role_names = [r.name.lower() for r in member.roles]
    return any(role in role_names for role in EXEMPT_ROLES)


def contains_banned_word(content: str) -> str | None:
    lowered = content.lower()
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, lowered):
            return word
    return None


def contains_banned_link(content: str) -> str | None:
    if BLOCK_DISCORD_INVITES and INVITE_REGEX.search(content):
        return "convite de servidor Discord"

    for url in URL_REGEX.findall(content):
        for domain in BANNED_DOMAINS:
            if domain in url.lower():
                return domain
    return None


def has_excess_mentions(message: discord.Message) -> bool:
    total = len(message.mentions) + len(message.role_mentions)
    return total > MAX_MENTIONS


def has_excess_caps(content: str) -> bool:
    letters = [c for c in content if c.isalpha()]
    if len(letters) < MIN_LENGTH_FOR_CAPS_CHECK:
        return False
    caps = sum(1 for c in letters if c.isupper())
    return (caps / len(letters)) * 100 >= MAX_CAPS_PERCENT


def is_spamming(user_id: int) -> bool:
    now = datetime.utcnow()
    history = user_message_history[user_id]
    history.append(now)
    window_start = now - timedelta(seconds=SPAM_TIME_WINDOW)
    recent = [t for t in history if t >= window_start]
    return len(recent) >= SPAM_MESSAGE_LIMIT


async def get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)


async def log_action(guild: discord.Guild, embed: discord.Embed):
    channel = await get_log_channel(guild)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Sem permissão para enviar no canal de logs.")


async def handle_violation(message: discord.Message, reason: str):
    """Apaga a mensagem, avisa o autor e registra a ocorrência."""
    try:
        await message.delete()
    except discord.NotFound:
        pass
    except discord.Forbidden:
        logger.warning("Sem permissão para apagar mensagens em %s", message.channel)
        return

    user_warnings[message.author.id] += 1
    warn_count = user_warnings[message.author.id]

    try:
        notice = await message.channel.send(
            f"⚠️ {message.author.mention}, sua mensagem foi removida. Motivo: **{reason}**. "
            f"Advertência {warn_count}/{WARN_LIMIT_BEFORE_TIMEOUT}."
        )
        await notice.delete(delay=DELETE_NOTICE_SECONDS)
    except discord.Forbidden:
        pass

    embed = discord.Embed(
        title="Mensagem filtrada",
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Autor", value=f"{message.author} ({message.author.id})", inline=False)
    embed.add_field(name="Canal", value=message.channel.mention, inline=False)
    embed.add_field(name="Motivo", value=reason, inline=False)
    embed.add_field(name="Conteúdo original", value=message.content[:1000] or "(vazio)", inline=False)
    await log_action(message.guild, embed)

    if warn_count >= WARN_LIMIT_BEFORE_TIMEOUT and isinstance(message.author, discord.Member):
        try:
            until = discord.utils.utcnow() + timedelta(minutes=TIMEOUT_MINUTES)
            await message.author.timeout(until, reason="Excesso de advertências do filtro automático")
            user_warnings[message.author.id] = 0
            timeout_embed = discord.Embed(
                title="Usuário silenciado (timeout)",
                description=f"{message.author.mention} recebeu timeout de {TIMEOUT_MINUTES} minutos por acumular {WARN_LIMIT_BEFORE_TIMEOUT} advertências.",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow(),
            )
            await log_action(message.guild, timeout_embed)
        except discord.Forbidden:
            logger.warning("Sem permissão para aplicar timeout em %s", message.author)


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)
    logger.info("Servidores: %s", [g.name for g in bot.guilds])


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if isinstance(message.author, discord.Member) and is_exempt(message.author):
        await bot.process_commands(message)
        return

    content = message.content

    reason = contains_banned_word(content)
    if reason:
        await handle_violation(message, f"palavra proibida (`{reason}`)")
        return

    reason = contains_banned_link(content)
    if reason:
        await handle_violation(message, f"link não autorizado ({reason})")
        return

    if has_excess_mentions(message):
        await handle_violation(message, f"excesso de menções (máx: {MAX_MENTIONS})")
        return

    if has_excess_caps(content):
        await handle_violation(message, "excesso de letras maiúsculas (CAPS LOCK)")
        return

    if is_spamming(message.author.id):
        await handle_violation(message, "spam (mensagens muito rápidas)")
        return

    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Comandos de administração
# ---------------------------------------------------------------------------

@bot.command(name="filtro-status")
@commands.has_permissions(manage_messages=True)
async def filtro_status(ctx: commands.Context):
    embed = discord.Embed(title="Status do filtro", color=discord.Color.blurple())
    embed.add_field(name="Palavras banidas", value=str(len(BANNED_WORDS)))
    embed.add_field(name="Domínios banidos", value=str(len(BANNED_DOMAINS)))
    embed.add_field(name="Bloqueia convites Discord", value=str(BLOCK_DISCORD_INVITES))
    embed.add_field(name="Máx. menções", value=str(MAX_MENTIONS))
    embed.add_field(name="Máx. % maiúsculas", value=str(MAX_CAPS_PERCENT))
    embed.add_field(name="Limite de spam", value=f"{SPAM_MESSAGE_LIMIT} msgs / {SPAM_TIME_WINDOW}s")
    await ctx.send(embed=embed)


@bot.command(name="reload-config")
@commands.has_permissions(administrator=True)
async def reload_config(ctx: commands.Context):
    global BANNED_WORDS, BANNED_DOMAINS, config
    config = load_config(CONFIG_PATH)
    BANNED_WORDS = [w.lower() for w in config.get("banned_words", [])]
    BANNED_DOMAINS = [d.lower() for d in config.get("banned_domains", [])]
    await ctx.send("✅ Configuração recarregada com sucesso.")


@bot.command(name="limpar-avisos")
@commands.has_permissions(manage_messages=True)
async def limpar_avisos(ctx: commands.Context, member: discord.Member):
    user_warnings[member.id] = 0
    await ctx.send(f"✅ Advertências de {member.mention} foram zeradas.")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "Defina a variável de ambiente DISCORD_TOKEN (use um arquivo .env, veja .env.example)."
        )
    bot.run(TOKEN)

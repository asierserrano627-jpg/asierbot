import os
import re
import json
import asyncio
import datetime
import unicodedata

import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

# ---------- Configuración ----------
TOKEN = os.getenv("DISCORD_TOKEN")
NOMBRE_BOT = "AsierBot"
AVISOS_MAX = 3                                        # infracciones antes del silencio
MUTE_HORAS = 10
CANAL_LOGS = int(os.getenv("CANAL_LOGS_ID", "0"))     # ID del canal de logs (0 = desactivado)
CANALES_IGNORADOS = set()                             # IDs de canales donde no se filtra
ARCHIVO_AVISOS = "avisos.json"
ARCHIVO_PALABRAS = "palabrotas.txt"
COLOR = discord.Color.blurple()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- Normalización y detección ----------
# Sustituciones tipo leetspeak: "p4ta" -> "pata", "sh1t" -> "shit"
LEET = str.maketrans({"4": "a", "@": "a", "3": "e", "1": "i", "!": "i",
                      "0": "o", "5": "s", "$": "s", "7": "t"})


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes, sin leetspeak y sin letras repetidas: 'Pütáaa' -> 'puta'."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.translate(LEET)
    return re.sub(r"(.)\1+", r"\1", texto)


def es_cjk(texto: str) -> bool:
    return re.search(r"[一-鿿]", texto) is not None


def cargar_palabras():
    palabras, frases, cjk = set(), set(), set()
    if not os.path.exists(ARCHIVO_PALABRAS):
        print(f"Aviso: no existe {ARCHIVO_PALABRAS}")
        return palabras, frases, cjk
    with open(ARCHIVO_PALABRAS, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            p = normalizar(linea)
            if es_cjk(p):
                cjk.add(p)           # el chino no tiene espacios: se busca como subcadena
            elif " " in p:
                frases.add(p)
            else:
                palabras.add(p)
    return palabras, frases, cjk


PALABRAS, FRASES, CJK = cargar_palabras()


def contiene_palabrota(texto: str) -> bool:
    norm = normalizar(texto)
    if any(p in norm for p in CJK):
        return True
    tokens = re.findall(r"\w+", norm)
    if any(t in PALABRAS for t in tokens):
        return True
    texto_pad = f" {' '.join(tokens)} "
    return any(f" {frase} " in texto_pad for frase in FRASES)


async def es_palabrota_traducida(texto: str) -> bool:
    """Traduce el mensaje (chino u otro idioma) al español y vuelve a comprobarlo."""
    try:
        traduccion = await asyncio.to_thread(
            GoogleTranslator(source="auto", target="es").translate, texto
        )
        return contiene_palabrota(traduccion or "")
    except Exception as e:
        print(f"Error traduciendo: {e}")
        return False


# ---------- Avisos ----------
def cargar_avisos():
    if os.path.exists(ARCHIVO_AVISOS):
        with open(ARCHIVO_AVISOS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_avisos(datos):
    with open(ARCHIVO_AVISOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)


def clave_aviso(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


async def registrar(guild: discord.Guild, embed: discord.Embed):
    if not CANAL_LOGS:
        return
    canal = guild.get_channel(CANAL_LOGS)
    if canal:
        await canal.send(embed=embed)


# ---------- Eventos ----------
@bot.event
async def on_ready():
    print(f"{NOMBRE_BOT} conectado como {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Vigilando el chat | !ayuda"))


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    exento = (message.author.guild_permissions.manage_messages
              or message.channel.id in CANALES_IGNORADOS)

    if not exento:
        infraccion = contiene_palabrota(message.content)
        if not infraccion and es_cjk(message.content):
            infraccion = await es_palabrota_traducida(message.content)

        if infraccion:
            await manejar_infraccion(message)
            return   # mensaje borrado: no procesamos comandos

    await bot.process_commands(message)


async def manejar_infraccion(message: discord.Message):
    try:
        await message.delete()
    except discord.HTTPException:
        pass

    avisos = cargar_avisos()
    clave = clave_aviso(message.guild.id, message.author.id)
    avisos[clave] = avisos.get(clave, 0) + 1
    n = avisos[clave]

    if n >= AVISOS_MAX:
        try:
            await message.author.timeout(
                datetime.timedelta(hours=MUTE_HORAS),
                reason=f"{NOMBRE_BOT}: lenguaje inapropiado ({AVISOS_MAX} avisos)",
            )
            texto = (f"🔇 {message.author.mention} ha sido silenciado "
                     f"{MUTE_HORAS} horas por lenguaje inapropiado.")
            accion = f"Silenciado {MUTE_HORAS} h"
            color = discord.Color.red()
            avisos[clave] = 0
        except discord.Forbidden:
            texto = "No tengo permisos para silenciar a este usuario."
            accion = "Error de permisos"
            color = discord.Color.dark_grey()
    else:
        texto = (f"⚠️ {message.author.mention}, tu mensaje ha sido eliminado. "
                 f"Aviso {n}/{AVISOS_MAX}.")
        accion = f"Aviso {n}/{AVISOS_MAX}"
        color = discord.Color.orange()

    guardar_avisos(avisos)
    await message.channel.send(texto, delete_after=10)

    embed = discord.Embed(title="Infracción detectada", color=color)
    embed.add_field(name="Usuario", value=f"{message.author} ({message.author.id})", inline=False)
    embed.add_field(name="Canal", value=message.channel.mention, inline=True)
    embed.add_field(name="Acción", value=accion, inline=True)
    embed.add_field(name="Mensaje", value=message.content[:300] or "(sin texto)", inline=False)
    embed.set_footer(text=NOMBRE_BOT)
    await registrar(message.guild, embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("No tienes permisos para usar ese comando.", delete_after=8)
    elif isinstance(error, (commands.MemberNotFound, commands.BadArgument,
                            commands.MissingRequiredArgument)):
        await ctx.send("Uso incorrecto. Escribe `!ayuda` para ver los comandos.", delete_after=8)
    else:
        print(f"Error en comando: {error}")


# ---------- Comandos ----------
@bot.command(name="ayuda")
async def ayuda(ctx):
    embed = discord.Embed(
        title=f"{NOMBRE_BOT} — comandos",
        description=(
            "**!ayuda** — muestra este mensaje\n"
            "**!avisos @usuario** — ver avisos de un usuario *(moderadores)*\n"
            "**!perdonar @usuario** — reiniciar los avisos de un usuario *(moderadores)*\n"
            "**!recargar** — volver a leer `palabrotas.txt` sin reiniciar *(moderadores)*"
        ),
        color=COLOR,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"{NOMBRE_BOT} · {AVISOS_MAX} avisos = {MUTE_HORAS} h de silencio")
    await ctx.send(embed=embed)


@bot.command(name="avisos")
@commands.has_permissions(manage_messages=True)
async def avisos_cmd(ctx, miembro: discord.Member):
    n = cargar_avisos().get(clave_aviso(ctx.guild.id, miembro.id), 0)
    await ctx.send(f"{miembro.mention} tiene {n}/{AVISOS_MAX} avisos.")


@bot.command(name="perdonar")
@commands.has_permissions(manage_messages=True)
async def perdonar(ctx, miembro: discord.Member):
    avisos = cargar_avisos()
    avisos.pop(clave_aviso(ctx.guild.id, miembro.id), None)
    guardar_avisos(avisos)
    await ctx.send(f"✅ Avisos de {miembro.mention} reiniciados.")


@bot.command(name="recargar")
@commands.has_permissions(manage_messages=True)
async def recargar(ctx):
    global PALABRAS, FRASES, CJK
    PALABRAS, FRASES, CJK = cargar_palabras()
    total = len(PALABRAS) + len(FRASES) + len(CJK)
    await ctx.send(f"📚 Lista recargada: {total} entradas.")


# ---------- Arranque ----------
if not TOKEN:
    raise SystemExit("Falta la variable de entorno DISCORD_TOKEN")

bot.run(TOKEN)

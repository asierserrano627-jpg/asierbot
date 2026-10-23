# AsierBot

Bot de Discord con filtro de palabrotas. Borra el mensaje, avisa al usuario y, a la 3.ª infracción, lo silencia 10 horas.

## Archivos

- `bot.py`: código del bot.
- `palabrotas.txt`: lista de palabras prohibidas (una por línea).
- `asierbot_logo.png`: avatar del bot.

## Instalación

1. Instala las dependencias:
   ```
   pip install -U discord.py deep-translator
   ```
2. Crea la aplicación en el [Discord Developer Portal](https://discord.com/developers/applications), ponle el nombre **AsierBot** y sube `asierbot_logo.png` como avatar (pestaña *General Information*).
3. En *Bot*, activa las intenciones **Message Content Intent** y **Server Members Intent**.
4. Invita al bot a tu servidor con los permisos *Gestionar mensajes* y *Moderar miembros*. El rol del bot debe estar **por encima** de los roles que quieras silenciar.
5. Configura las variables de entorno:
   - `DISCORD_TOKEN`: el token del bot (nunca lo pegues en el código).
   - `CANAL_LOGS_ID` (opcional): ID del canal donde se registran las infracciones.
6. Ejecuta `python bot.py`.

En Replit, los dos valores van en la pestaña *Secrets*.

## Comandos

| Comando | Quién lo usa | Qué hace |
|---|---|---|
| `!ayuda` | Todos | Muestra los comandos |
| `!avisos @usuario` | Moderadores | Muestra los avisos de un usuario |
| `!perdonar @usuario` | Moderadores | Reinicia los avisos de un usuario |
| `!recargar` | Moderadores | Relee `palabrotas.txt` sin reiniciar el bot |

## Cómo funciona

- Detecta palabras completas, frases y variantes (`p4ta`, `puuuta`, mayúsculas o tildes).
- Si el mensaje contiene chino, lo traduce al español y comprueba la traducción.
- Los moderadores (quienes tienen *Gestionar mensajes*) no son filtrados.
- Los avisos se guardan en `avisos.json`, así que sobreviven a reinicios.
- Cada infracción se registra en el canal de logs si está configurado.

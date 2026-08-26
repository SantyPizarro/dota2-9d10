import io
import time
import asyncio
import logging
from typing import Optional, Tuple, Callable

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    DISCORD_CHANNEL_ID,
    DISCORD_USER_ID,
    ACCEPT_TIMEOUT,
    DOTA2_WINDOW_TITLE,
)
from src.clicker import accept_match, find_dota_window

logger = logging.getLogger("dota2-9d10.bot")


class AcceptMatchView(discord.ui.View):
    """Interactive Discord UI View with Accept and Decline buttons."""

    def __init__(
        self,
        coords: Optional[Tuple[int, int]] = None,
        timeout: float = ACCEPT_TIMEOUT,
        on_action_done: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(timeout=timeout)
        self.coords = coords
        self.on_action_done = on_action_done
        self.processed = False

    @discord.ui.button(label="ACEPTAR PARTIDA", style=discord.ButtonStyle.success, emoji="🎮")
    async def accept_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.processed:
            await interaction.response.send_message("⚠️ Esta alerta ya fue procesada.", ephemeral=True)
            return

        self.processed = True
        for child in self.children:
            child.disabled = True

        button.label = "✅ ¡Aceptando...!"
        button.style = discord.ButtonStyle.primary

        # Execute click on the PC
        success, message = accept_match(self.coords)

        # Notify callback if provided (e.g. to set auto-pause)
        if self.on_action_done:
            self.on_action_done("accepted")

        # Update Discord message
        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        if success:
            embed.color = discord.Color.green()
            embed.title = "✅ ¡PARTIDA ACEPTADA!"
            embed.description = (
                f"{message}\n\n"
                f"🏃 **¡Corre a tu laptop para la fase de picks / selección de héroe!**"
            )
        else:
            embed.color = discord.Color.orange()
            embed.title = "⚠️ Advertencia al Aceptar"
            embed.description = f"Se intentó aceptar pero ocurrió un detalle:\n{message}"

        button.label = "✅ Aceptada"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Ignorar / No Aceptar", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.processed:
            await interaction.response.send_message("⚠️ Esta alerta ya fue procesada.", ephemeral=True)
            return

        self.processed = True
        for child in self.children:
            child.disabled = True

        button.label = "❌ Ignorada"
        if self.on_action_done:
            self.on_action_done("ignored")

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.red()
        embed.title = "❌ Partida Ignorada"
        embed.description = "No se ejecutó ninguna acción en tu laptop."

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if not self.processed:
            self.processed = True
            for child in self.children:
                child.disabled = True
            if self.on_action_done:
                self.on_action_done("timeout")


class DotaBot(commands.Bot):
    """Dota 2 Remote Accept Discord Bot Client."""

    def __init__(self, detector_instance, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, *args, **kwargs)

        self.detector = detector_instance
        self.is_monitoring = True
        self.paused_until: Optional[float] = None
        self.last_match_time: Optional[float] = None

    async def setup_hook(self):
        # Register Slash Commands
        await self.register_slash_commands()
        try:
            synced = await self.tree.sync()
            logger.info(f"Comandos Slash sincronizados: {len(synced)} comandos.")
        except Exception as e:
            logger.warning(f"No se pudieron sincronizar comandos slash globales: {e}")

    async def on_ready(self):
        logger.info(f"Bot conectado como {self.user} (ID: {self.user.id})")
        activity = discord.Activity(type=discord.ActivityType.watching, name="Dota 2 Matchmaking ⚔️")
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def send_match_alert(
        self,
        coords: Optional[Tuple[int, int]],
        preview_bytes: Optional[bytes] = None,
        is_test: bool = False,
    ):
        """Sends the interactive match found alert to the configured channel."""
        if not DISCORD_CHANNEL_ID:
            logger.error("No se ha configurado DISCORD_CHANNEL_ID en .env")
            return

        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.fetch_channel(DISCORD_CHANNEL_ID)
            except Exception as e:
                logger.error(f"No se pudo obtener el canal con ID {DISCORD_CHANNEL_ID}: {e}")
                return

        mention = f"<@{DISCORD_USER_ID}> " if DISCORD_USER_ID else "@here "

        embed = discord.Embed(
            title="🔔 ¡PARTIDA ENCONTRADA EN DOTA 2!" if not is_test else "🧪 ALERTA DE PRUEBA (TEST)",
            description=(
                f"{mention}\n"
                f"Se detectó la ventana de **Aceptar Partida** en tu laptop.\n"
                f"Presiona el botón verde abajo para **Aceptar**."
            ),
            color=discord.Color.gold() if is_test else discord.Color.green(),
        )
        embed.set_footer(text=f"dota2-9d10 • Tienes {int(ACCEPT_TIMEOUT)}s para responder")

        files = []
        if preview_bytes:
            file_preview = discord.File(io.BytesIO(preview_bytes), filename="match_preview.jpg")
            embed.set_image(url="attachment://match_preview.jpg")
            files.append(file_preview)

        def on_action(action_type: str):
            logger.info(f"Acción de alerta de partida: {action_type}")
            if action_type == "accepted":
                self.last_match_time = time.time()

        view = AcceptMatchView(coords=coords, timeout=ACCEPT_TIMEOUT, on_action_done=on_action)
        await channel.send(content=mention, embed=embed, files=files, view=view)

    async def register_slash_commands(self):
        @self.tree.command(name="status", description="Muestra el estado actual del monitor de Dota 2.")
        async def cmd_status(interaction: discord.Interaction):
            now = time.time()
            if self.paused_until and self.paused_until > now:
                remaining_min = int((self.paused_until - now) / 60)
                status_text = f"⏸️ **Pausado** (restan ~{remaining_min} minutos)"
            elif self.is_monitoring:
                status_text = "🟢 **Activo y vigilando partidas**"
            else:
                status_text = "🔴 **Desactivado manualmente**"

            hwnd = find_dota_window(DOTA2_WINDOW_TITLE)
            game_status = f"🎮 Detectado (HWND: {hwnd})" if hwnd else "⚠️ No detectado (¿juego cerrado o minimizado?)"

            embed = discord.Embed(title="📊 Estado del Monitor Dota 2", color=discord.Color.blue())
            embed.add_field(name="Vigilancia", value=status_text, inline=False)
            embed.add_field(name="Proceso Dota 2", value=game_status, inline=False)
            embed.add_field(
                name="Canal de Alertas",
                value=f"<#{DISCORD_CHANNEL_ID}>" if DISCORD_CHANNEL_ID else "No configurado",
                inline=True,
            )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="test", description="Envía una alerta de prueba interactiva a Discord.")
        async def cmd_test(interaction: discord.Interaction):
            await interaction.response.send_message("🚀 Enviando alerta de prueba...", ephemeral=True)
            preview_bytes = self.detector.capture_full_screen_preview()
            await self.send_match_alert(coords=None, preview_bytes=preview_bytes, is_test=True)

        @self.tree.command(name="pause", description="Pausa temporalmente la vigilancia (ej. mientras juegas).")
        @app_commands.describe(minutos="Minutos para pausar (por defecto 25)")
        async def cmd_pause(interaction: discord.Interaction, minutos: int = 25):
            self.paused_until = time.time() + (minutos * 60)
            await interaction.response.send_message(f"⏸️ Vigilancia pausada durante **{minutos} minutos**.")

        @self.tree.command(name="resume", description="Reanuda la vigilancia de partidas inmediatamente.")
        async def cmd_resume(interaction: discord.Interaction):
            self.paused_until = None
            self.is_monitoring = True
            await interaction.response.send_message("🟢 Vigilancia **reanudada**. Esperando partidas.")

        @self.tree.command(name="screen", description="Captura la pantalla actual de la laptop y la envía.")
        async def cmd_screen(interaction: discord.Interaction):
            await interaction.response.defer()
            preview = self.detector.capture_full_screen_preview()
            file = discord.File(io.BytesIO(preview), filename="screen.jpg")
            embed = discord.Embed(title="🖥️ Captura Actual de Pantalla", color=discord.Color.dark_grey())
            embed.set_image(url="attachment://screen.jpg")
            await interaction.followup.send(embed=embed, file=file)

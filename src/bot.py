import io
import time
import asyncio
import logging
from typing import Optional, Tuple, Callable, Set

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    DISCORD_CHANNEL_ID,
    DISCORD_USER_ID,
    ALLOWED_USER_IDS,
    ACCEPT_TIMEOUT,
    DOTA2_WINDOW_TITLE,
)
from src.clicker import accept_match, find_dota_window

logger = logging.getLogger("dota2-9d10.bot")


class AcceptMatchView(discord.ui.View):
    """Interactive Discord UI View with Accept and Decline buttons and role/user security."""

    def __init__(
        self,
        coords: Optional[Tuple[int, int]] = None,
        allowed_user_ids: Optional[Set[int]] = None,
        timeout: float = ACCEPT_TIMEOUT,
        on_action_done: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(timeout=timeout)
        self.coords = coords
        self.allowed_user_ids = allowed_user_ids or set()
        self.on_action_done = on_action_done
        self.processed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check: Only authorized Discord user IDs can interact with the buttons."""
        if self.allowed_user_ids and interaction.user.id not in self.allowed_user_ids:
            logger.warning(
                f"Intento de interacción no autorizado por {interaction.user} (ID: {interaction.user.id})"
            )
            await interaction.response.send_message(
                "⛔ **NO TOQUES,** wachin.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="ACEPTAR PARTIDA", style=discord.ButtonStyle.success, emoji="😼")
    async def accept_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.processed:
            await interaction.response.send_message("⚠️ Esta alerta ya fue procesada.", ephemeral=True)
            return

        self.processed = True
        for child in self.children:
            child.disabled = True

        button.label = "✅ ¡Aceptada!"
        button.style = discord.ButtonStyle.primary

        # Execute single click on PC
        success, message = accept_match(self.coords)

        if self.on_action_done:
            self.on_action_done("accepted")

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        if success:
            embed.color = discord.Color.green()
            embed.title = "✅ ¡PARTIDA ACEPTADA!"
            embed.description = (
                f"{message}\n\n"
                f"👤 *Aceptada por:* <@{interaction.user.id}>\n"
                f"🏃 **Corre wachin**"
            )
        else:
            embed.color = discord.Color.orange()
            embed.title = "⚠️ Advertencia al Aceptar"
            embed.description = f"Se intentó aceptar pero ocurrió un detalle:\n{message}"

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Ignorar", style=discord.ButtonStyle.danger, emoji="❌")
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
        embed.description = f"👤 *Ignorada por:* <@{interaction.user.id}>"

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if not self.processed:
            self.processed = True
            for child in self.children:
                child.disabled = True
            if self.on_action_done:
                self.on_action_done("timeout")


class DotaBot(commands.Bot):
    """Dota 2 Remote Accept Discord Bot Client with unified message tracking."""

    def __init__(self, detector_instance, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, *args, **kwargs)

        self.detector = detector_instance
        self.is_monitoring = True
        self.paused_until: Optional[float] = None
        self.last_match_time: Optional[float] = None

        # Unified message lifecycle
        self.active_status_message: Optional[discord.Message] = None
        self.current_state: str = "IDLE"
        self.search_start_time: Optional[float] = None

    async def setup_hook(self):
        await self.register_slash_commands()
        self.register_prefix_commands()
        try:
            synced = await self.tree.sync()
            logger.info(f"Comandos Slash globales registrados: {len(synced)} comandos.")
        except Exception as e:
            logger.warning(f"No se pudieron sincronizar comandos slash globales: {e}")

    async def on_ready(self):
        logger.info(f"Bot conectado como {self.user} (ID: {self.user.id})")
        if ALLOWED_USER_IDS:
            logger.info(f"Usuarios autorizados (Whitelist): {ALLOWED_USER_IDS}")
        else:
            logger.info("Whitelist vacía: cualquier usuario en el canal podrá interactuar.")

        # Sync immediately to each connected server for INSTANT slash command display
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced_guild = await self.tree.sync(guild=guild)
                logger.info(
                    f"Comandos Slash sincronizados instantáneamente con '{guild.name}' ({len(synced_guild)} comandos)."
                )
            except Exception as e:
                logger.warning(f"No se pudieron sincronizar comandos instantáneos en '{guild.name}': {e}")

        activity = discord.Activity(type=discord.ActivityType.watching, name="dotaaaaaaaaaaaaa")
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def get_notification_channel(self) -> Optional[discord.TextChannel]:
        """Fetches the configured alert channel."""
        if not DISCORD_CHANNEL_ID:
            logger.error("No se ha configurado DISCORD_CHANNEL_ID en .env")
            return None

        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.fetch_channel(DISCORD_CHANNEL_ID)
            except Exception as e:
                logger.error(f"No se pudo obtener el canal con ID {DISCORD_CHANNEL_ID}: {e}")
                return None
        return channel

    def build_status_embed(self) -> discord.Embed:
        """Helper to create the status embed."""
        now = time.time()
        if self.paused_until and self.paused_until > now:
            remaining_min = int((self.paused_until - now) / 60)
            status_text = f"⏸️ **Pausado** (restan ~{remaining_min} minutos)"
        elif self.is_monitoring:
            status_text = f"🟢 **Activo** (Estado actual: `{self.current_state}`)"
        else:
            status_text = "🔴 **Desactivado manualmente**"

        hwnd = find_dota_window(DOTA2_WINDOW_TITLE)
        game_status = f"🎮 Detectado (HWND: {hwnd})" if hwnd else "⚠️ No detectado (¿juego cerrado o minimizado?)"

        embed = discord.Embed(title="📊 Estado:", color=discord.Color.blue())
        embed.add_field(name="Vigilancia", value=status_text, inline=False)
        embed.add_field(name="Proceso Dota 2", value=game_status, inline=False)
        embed.add_field(
            name="Canal de Alertas",
            value=f"<#{DISCORD_CHANNEL_ID}>" if DISCORD_CHANNEL_ID else "No configurado",
            inline=True,
        )
        embed.add_field(
            name="Usuarios Autorizados",
            value=", ".join(f"<@{u}>" for u in ALLOWED_USER_IDS) if ALLOWED_USER_IDS else "Todos los usuarios",
            inline=True,
        )
        return embed

    async def set_state(
        self,
        new_state: str,
        coords: Optional[Tuple[int, int]] = None,
        preview_bytes: Optional[bytes] = None,
        is_test: bool = False,
    ):
        """
        Updates the bot state and manages the single lifecycle Discord message.
        Prevents channel spam by editing the active status message dynamically.
        """
        channel = await self.get_notification_channel()
        if not channel:
            return

        mention = f"<@{DISCORD_USER_ID}> " if DISCORD_USER_ID else "@here "
        files = []
        view = None
        embed = discord.Embed()

        if new_state == "SEARCHING":
            if self.current_state != "SEARCHING":
                self.search_start_time = time.time()

            start_ts = int(self.search_start_time) if self.search_start_time else int(time.time())
            embed.title = "🔍 Buscando Partida..."
            embed.description = f"buscandoooo...  <t:{start_ts}:R>"
            embed.color = discord.Color.blue()
            embed.set_footer(text="dota2-9d10")

        elif new_state == "MATCH_READY":
            embed.title = "🔔 ¡PARTIDA ENCONTRADA!!!!!!!!!!!!!!!!!!!!" if not is_test else "🧪 ALERTA DE PRUEBA (TEST)"
            embed.description = f"{mention}!!!! \nPresiona el botón verde abajo para **Aceptar**."
            embed.color = discord.Color.gold() if is_test else discord.Color.green()
            embed.set_footer(text=f"dota2-9d10 • Tenes {int(ACCEPT_TIMEOUT)}s para responder")

            if preview_bytes:
                file_preview = discord.File(io.BytesIO(preview_bytes), filename="match_preview.jpg")
                embed.set_image(url="attachment://match_preview.jpg")
                files.append(file_preview)

            def on_action(action_type: str):
                logger.info(f"Acción sobre partida: {action_type}")
                if action_type == "accepted":
                    self.last_match_time = time.time()

            view = AcceptMatchView(
                coords=coords,
                allowed_user_ids=ALLOWED_USER_IDS,
                timeout=ACCEPT_TIMEOUT,
                on_action_done=on_action,
            )

        elif new_state == "DODGE":
            embed.title = "⚠️ Otro jugador no aceptó"
            embed.description = "La partida anterior se canceló porque alguien no aceptó.\n\n🔄 **Seguimos en la cola**"
            embed.color = discord.Color.orange()
            embed.set_footer(text="dota2-9d10")

        elif new_state == "IN_GAME":
            embed.title = " ¡Partida Iniciada!"
            embed.description = "tamoooooooo"
            embed.color = discord.Color.purple()
            embed.set_footer(text="dota2-9d10 • Partida en curso")

        elif new_state == "IDLE":
            embed.title = "Búsqueda Detenida / En Espera"
            embed.description = "No se detecta búsqueda activa de partida."
            embed.color = discord.Color.light_grey()
            embed.set_footer(text="dota2-9d10 • Esperando inicio de cola")

        self.current_state = new_state

        # Update existing message or send a new one
        try:
            if self.active_status_message and not is_test:
                if not files:
                    await self.active_status_message.edit(embed=embed, view=view)
                else:
                    await self.active_status_message.edit(embed=embed, view=view, attachments=files)
            else:
                msg = await channel.send(
                    content=mention if new_state == "MATCH_READY" else None,
                    embed=embed,
                    files=files,
                    view=view,
                )
                if not is_test:
                    self.active_status_message = msg

            if new_state in ("IN_GAME", "IDLE"):
                self.active_status_message = None

        except Exception as e:
            logger.warning(f"No se pudo editar el mensaje de estado, enviando uno nuevo: {e}")
            try:
                msg = await channel.send(
                    content=mention if new_state == "MATCH_READY" else None,
                    embed=embed,
                    files=files,
                    view=view,
                )
                if not is_test:
                    self.active_status_message = msg
            except Exception as send_err:
                logger.error(f"Error crítico enviando mensaje a Discord: {send_err}")

    def register_prefix_commands(self):
        """Registers text fallback commands: !test, !status, !pause, !resume, !screen."""

        @self.command(name="test")
        async def cmd_p_test(ctx):
            await ctx.send("Enviando alerta de prueba...")
            preview_bytes = self.detector.capture_full_screen_preview()
            await self.set_state("MATCH_READY", coords=None, preview_bytes=preview_bytes, is_test=True)

        @self.command(name="status")
        async def cmd_p_status(ctx):
            embed = self.build_status_embed()
            await ctx.send(embed=embed)

        @self.command(name="pause")
        async def cmd_p_pause(ctx, minutos: int = 25):
            self.paused_until = time.time() + (minutos * 60)
            await ctx.send(f"⏸️ Bot pausado por **{minutos} minutos**.")

        @self.command(name="resume")
        async def cmd_p_resume(ctx):
            self.paused_until = None
            self.is_monitoring = True
            await ctx.send("🟢 bot? **ON**. Esperando partidas.")

        @self.command(name="screen")
        async def cmd_p_screen(ctx):
            preview = self.detector.capture_full_screen_preview()
            if preview:
                file = discord.File(io.BytesIO(preview), filename="screen.jpg")
                embed = discord.Embed(title="🖥️ Captura Actual de Pantalla", color=discord.Color.dark_grey())
                embed.set_image(url="attachment://screen.jpg")
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send("⚠️ No se pudo capturar la pantalla")

    async def register_slash_commands(self):
        """Registers Slash Commands (/status, /test, /pause, /resume, /screen)."""

        @self.tree.command(name="status", description="Muestra el estado actual del botsito.")
        async def cmd_status(interaction: discord.Interaction):
            embed = self.build_status_embed()
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="test", description="Envía una alerta de prueba.")
        async def cmd_test(interaction: discord.Interaction):
            await interaction.response.send_message("Enviando alerta de prueba...", ephemeral=True)
            preview_bytes = self.detector.capture_full_screen_preview()
            await self.set_state("MATCH_READY", coords=None, preview_bytes=preview_bytes, is_test=True)

        @self.tree.command(name="pause", description="Pausar el bot (ej. mientras juegas).")
        @app_commands.describe(minutos="Minutos para pausar (por defecto 25)")
        async def cmd_pause(interaction: discord.Interaction, minutos: int = 25):
            self.paused_until = time.time() + (minutos * 60)
            await interaction.response.send_message(f"⏸️ Bot pausado por **{minutos} minutos**.")

        @self.tree.command(name="resume", description="Reanuda el bot")
        async def cmd_resume(interaction: discord.Interaction):
            self.paused_until = None
            self.is_monitoring = True
            await interaction.response.send_message("🟢 bot? **ON**. Esperando partidas.")

        @self.tree.command(name="screen", description="Captura de pantalla (si).")
        async def cmd_screen(interaction: discord.Interaction):
            await interaction.response.defer()
            preview = self.detector.capture_full_screen_preview()
            if preview:
                file = discord.File(io.BytesIO(preview), filename="screen.jpg")
                embed = discord.Embed(title="🖥️ Captura Actual de Pantalla", color=discord.Color.dark_grey())
                embed.set_image(url="attachment://screen.jpg")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send("⚠️ No se pudo capturar la pantalla")

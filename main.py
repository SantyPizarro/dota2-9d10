import sys
import time
import asyncio
import logging
import argparse
from pathlib import Path

from config import (
    DISCORD_BOT_TOKEN,
    DISCORD_CHANNEL_ID,
    CHECK_INTERVAL,
    AUTO_PAUSE_MINUTES,
    validate_config,
)
from src.detector import MatchDetector
from src.bot import DotaBot
from src.clicker import accept_match, prevent_screen_sleep, restore_screen_sleep

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dota2-9d10")


async def monitor_loop(bot: DotaBot, detector: MatchDetector):
    """Background task that checks the screen periodically for Dota 2 match ready prompt."""
    logger.info(f"Iniciando ciclo de vigilancia (chequeo cada {CHECK_INTERVAL}s)...")
    await bot.wait_until_ready()

    prevent_screen_sleep()

    in_match_alert = False
    last_alert_time = 0.0

    while not bot.is_closed():
        try:
            now = time.time()

            # Check if monitoring is paused
            if bot.paused_until and bot.paused_until > now:
                await asyncio.sleep(5.0)
                continue

            # Check if we are within the alert cooldown window (~45s)
            if in_match_alert and (now - last_alert_time < 45.0):
                await asyncio.sleep(2.0)
                continue
            else:
                in_match_alert = False

            # Run visual check in a thread executor to avoid blocking the asyncio event loop
            is_ready, coords, preview_bytes = await asyncio.to_thread(detector.check_match_ready)

            if is_ready:
                logger.info("⚔️ ¡PARTIDA DETECTADA EN PANTALLA! Enviando alerta a Discord...")
                in_match_alert = True
                last_alert_time = now

                await bot.send_match_alert(coords=coords, preview_bytes=preview_bytes)

                # If auto-pause is enabled, schedule pause after match window
                if AUTO_PAUSE_MINUTES > 0:
                    bot.paused_until = now + (AUTO_PAUSE_MINUTES * 60)
                    logger.info(f"Vigilancia auto-pausada por {AUTO_PAUSE_MINUTES} minutos tras detectar la partida.")

            await asyncio.sleep(CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Ciclo de vigilancia cancelado.")
            break
        except Exception as e:
            logger.error(f"Excepción en monitor_loop: {e}", exc_info=True)
            await asyncio.sleep(5.0)


def parse_args():
    parser = argparse.ArgumentParser(description="dota2-9d10: Remote Dota 2 Match Accepter via Discord")
    parser.add_argument("--test-click", action="store_true", help="Simula un clic en el centro de la pantalla y sale.")
    parser.add_argument("--check-screen", action="store_true", help="Realiza un chequeo visual único y guarda captura en temp/.")
    parser.add_argument("--debug", action="store_true", help="Habilita logs detallados de depuración.")
    return parser.parse_args()


async def main_async():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Modo de depuración (DEBUG) activado.")

    detector = MatchDetector()

    if args.test_click:
        logger.info("Ejecutando prueba de clic de simulación...")
        success, msg = accept_match()
        logger.info(f"Resultado: {msg}")
        return

    if args.check_screen:
        logger.info("Chequeando pantalla actual...")
        is_ready, coords, _ = detector.check_match_ready(debug_save=True)
        if is_ready:
            logger.info(f"✅ ¡Partida lista detectada en {coords}! Ver temp/match_detected_debug.jpg")
        else:
            logger.info("ℹ️ No se detectó botón de aceptar. Ver captura en temp/no_match_debug.jpg")
        return

    # Validate environment variables before connecting
    valid, message = validate_config()
    if not valid:
        logger.error("=" * 60)
        logger.error(f"❌ ERROR DE CONFIGURACIÓN: {message}")
        logger.error("Por favor crea o edita el archivo .env basándote en .env.example")
        logger.error("=" * 60)
        sys.exit(1)

    # Initialize Bot and background task
    bot = DotaBot(detector_instance=detector)

    try:
        async with bot:
            # Launch background screen monitor
            asyncio.create_task(monitor_loop(bot, detector))
            # Start Discord connection
            await bot.start(DISCORD_BOT_TOKEN)
    finally:
        restore_screen_sleep()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Deteniendo dota2-9d10 por el usuario. ¡Hasta la próxima!")
    finally:
        restore_screen_sleep()


if __name__ == "__main__":
    main()

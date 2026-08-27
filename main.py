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
    """
    Background state machine that checks Dota 2 matchmaking states:
    - IDLE -> SEARCHING (Queue started)
    - SEARCHING -> MATCH_READY (Match found!)
    - MATCH_READY -> DODGE (9/10 / declined by another player -> back to queue)
    - MATCH_READY -> IN_GAME (All 10 loaded -> hero selection)
    """
    logger.info(f"Iniciando ciclo de vigilancia de estados (chequeo cada {CHECK_INTERVAL}s)...")
    await bot.wait_until_ready()

    prevent_screen_sleep()

    state = "IDLE"
    not_searching_counter = 0
    match_ready_active = False

    while not bot.is_closed():
        try:
            now = time.time()

            # Check if paused (e.g. during an ongoing match)
            if bot.paused_until and bot.paused_until > now:
                await asyncio.sleep(5.0)
                continue

            # 1. Check if Match Ready Dialog is visible
            is_ready, coords, preview_bytes = await asyncio.to_thread(detector.check_match_ready)

            if is_ready:
                if not match_ready_active:
                    logger.info("⚔️ ¡PARTIDA ENCONTRADA! Notificando en Discord...")
                    match_ready_active = True
                    state = "MATCH_READY"
                    await bot.set_state("MATCH_READY", coords=coords, preview_bytes=preview_bytes)

                # While match is ready, wait slightly and continue
                await asyncio.sleep(2.0)
                continue

            # If match ready was active and is no longer visible:
            if match_ready_active and not is_ready:
                match_ready_active = False
                logger.info("Ventana de Aceptar partida cerrada. Determinando resultado (Dodge vs En Juego)...")
                # Wait 6 seconds for game transition or queue rebound
                await asyncio.sleep(6.0)

                # Check if we bounced back to searching (DODGE / 9 of 10)
                is_searching_now = await asyncio.to_thread(detector.check_is_searching)
                if is_searching_now:
                    logger.info("⚠️ Dodge detectado: La partida se canceló y regresó a la cola de búsqueda.")
                    state = "SEARCHING"
                    await bot.set_state("DODGE")
                    await asyncio.sleep(3.0)
                    await bot.set_state("SEARCHING")
                    continue
                else:
                    logger.info("🎮 Partida iniciada con éxito. Entrando en modo IN_GAME.")
                    state = "IN_GAME"
                    await bot.set_state("IN_GAME")
                    if AUTO_PAUSE_MINUTES > 0:
                        bot.paused_until = time.time() + (AUTO_PAUSE_MINUTES * 60)
                        logger.info(f"Vigilancia auto-pausada por {AUTO_PAUSE_MINUTES} minutos mientras juegas.")
                    continue

            # 2. Check if searching for a match in bottom-right corner
            is_searching = await asyncio.to_thread(detector.check_is_searching)

            if is_searching:
                not_searching_counter = 0
                if state != "SEARCHING":
                    logger.info("🔍 Inicio de búsqueda de partida detectado.")
                    state = "SEARCHING"
                    await bot.set_state("SEARCHING")
            else:
                if state == "SEARCHING":
                    not_searching_counter += 1
                    # Debounce 3 consecutive checks (~6 seconds) before marking IDLE
                    if not_searching_counter >= 3:
                        logger.info("⏹️ Búsqueda de partida cancelada o finalizada.")
                        state = "IDLE"
                        await bot.set_state("IDLE")
                        not_searching_counter = 0

            await asyncio.sleep(CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Ciclo de vigilancia cancelado.")
            break
        except Exception as e:
            logger.error(f"Excepción en monitor_loop: {e}", exc_info=True)
            await asyncio.sleep(5.0)


def parse_args():
    parser = argparse.ArgumentParser(description="dota2-9d10: Remote Dota 2 Match Accepter via Discord")
    parser.add_argument("--test-click", action="store_true", help="Simula un clic único en el centro de la pantalla y sale.")
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
        logger.info("Ejecutando prueba de clic único de simulación...")
        success, msg = accept_match()
        logger.info(f"Resultado: {msg}")
        return

    if args.check_screen:
        logger.info("Chequeando pantalla actual...")
        is_ready, coords, _ = detector.check_match_ready(debug_save=True)
        is_searching = detector.check_is_searching()
        logger.info(f"Estado de búsqueda en cola: {'Buscando partida' if is_searching else 'No buscando'}")
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
            asyncio.create_task(monitor_loop(bot, detector))
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

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
    DOTA2_WINDOW_TITLE,
    validate_config,
)
from src.detector import MatchDetector
from src.bot import DotaBot
from src.clicker import accept_match, find_dota_window, prevent_screen_sleep, restore_screen_sleep

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dota2-9d10")


async def monitor_loop(bot: DotaBot, detector: MatchDetector):
    """
    Background state machine that monitors Dota 2 matchmaking.
    Guaranteed to run ONLY when Dota 2 is open:
    - IDLE -> SEARCHING (Queue started in Dota 2)
    - SEARCHING -> MATCH_READY (Match found!)
    - MATCH_READY -> DODGE (9/10 / another player declined -> back to queue)
    - MATCH_READY -> IN_GAME (Only if accepted by user and game started)
    """
    logger.info(f"Iniciando ciclo de vigilancia de estados (chequeo cada {CHECK_INTERVAL}s)...")
    await bot.wait_until_ready()

    prevent_screen_sleep()

    state = "IDLE"
    not_searching_counter = 0
    match_ready_active = False
    user_accepted_this_match = False
    dota_logged_offline = False

    while not bot.is_closed():
        try:
            now = time.time()

            # Check if monitoring is paused (e.g. while in game)
            if bot.paused_until and bot.paused_until > now:
                await asyncio.sleep(5.0)
                continue

            # Invariant: Dota 2 MUST be open to perform any detection
            hwnd = find_dota_window(DOTA2_WINDOW_TITLE)
            if not hwnd:
                if not dota_logged_offline:
                    logger.debug("Dota 2 no está abierto. Monitor en espera...")
                    dota_logged_offline = True

                if state != "IDLE":
                    logger.info("Dota 2 se ha cerrado o minimizado. Estado -> IDLE.")
                    state = "IDLE"
                    await bot.set_state("IDLE")

                match_ready_active = False
                user_accepted_this_match = False
                await asyncio.sleep(3.0)
                continue
            else:
                dota_logged_offline = False

            # 1. Check if Match Ready Dialog is visible in Dota 2
            is_ready, coords, preview_bytes = await asyncio.to_thread(detector.check_match_ready)

            if is_ready:
                if not match_ready_active:
                    logger.info("⚔️ ¡PARTIDA ENCONTRADA EN DOTA 2! Notificando en Discord...")
                    match_ready_active = True
                    user_accepted_this_match = False
                    state = "MATCH_READY"

                    # Callback when user presses Accept
                    def on_user_accepted(action: str):
                        nonlocal user_accepted_this_match
                        if action == "accepted":
                            user_accepted_this_match = True

                    await bot.set_state("MATCH_READY", coords=coords, preview_bytes=preview_bytes)

                await asyncio.sleep(2.0)
                continue

            # 2. If match ready was active and just closed:
            if match_ready_active and not is_ready:
                match_ready_active = False
                logger.info("Cartel de Aceptar cerrado en Dota 2. Verificando resultado...")
                await asyncio.sleep(6.0)

                # Re-verify Dota 2 window
                if not find_dota_window(DOTA2_WINDOW_TITLE):
                    state = "IDLE"
                    await bot.set_state("IDLE")
                    continue

                # Check if we bounced back to searching (DODGE / 9 of 10)
                is_searching_now = await asyncio.to_thread(detector.check_is_searching)
                if is_searching_now:
                    logger.info("⚠️ Dodge detectado: La partida se canceló y regresó a la cola de búsqueda.")
                    state = "SEARCHING"
                    await bot.set_state("DODGE")
                    await asyncio.sleep(3.0)
                    await bot.set_state("SEARCHING")
                    continue
                elif user_accepted_this_match:
                    logger.info("🎮 Partida iniciada con éxito por el usuario. Entrando en modo IN_GAME.")
                    state = "IN_GAME"
                    await bot.set_state("IN_GAME")
                    user_accepted_this_match = False
                    if AUTO_PAUSE_MINUTES > 0:
                        bot.paused_until = time.time() + (AUTO_PAUSE_MINUTES * 60)
                        logger.info(f"Vigilancia auto-pausada por {AUTO_PAUSE_MINUTES} minutos mientras juegas.")
                    continue
                else:
                    logger.info("Partida no aceptada o cancelada. Estado -> IDLE.")
                    state = "IDLE"
                    await bot.set_state("IDLE")
                    continue

            # 3. Check if searching for a match in bottom-right corner of Dota 2
            is_searching = await asyncio.to_thread(detector.check_is_searching)

            if is_searching:
                not_searching_counter = 0
                if state != "SEARCHING":
                    logger.info("🔍 Inicio de búsqueda de partida detectado en Dota 2.")
                    state = "SEARCHING"
                    await bot.set_state("SEARCHING")
            else:
                if state == "SEARCHING":
                    not_searching_counter += 1
                    # Debounce 3 consecutive checks (~6 seconds) before marking IDLE
                    if not_searching_counter >= 3:
                        logger.info("⏹️ Búsqueda de partida cancelada o finalizada en Dota 2.")
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
        hwnd = find_dota_window(DOTA2_WINDOW_TITLE)
        logger.info(f"Ventana de Dota 2 encontrada: {'SÍ (HWND: ' + str(hwnd) + ')' if hwnd else 'NO'}")
        is_ready, coords, _ = detector.check_match_ready(debug_save=True)
        is_searching = detector.check_is_searching()
        logger.info(f"Estado de búsqueda en cola: {'Buscando partida' if is_searching else 'No buscando'}")
        if is_ready:
            logger.info(f"✅ ¡Partida lista detectada en {coords}! Ver temp/match_detected_debug.jpg")
        else:
            logger.info("ℹ️ No se detectó botón de aceptar.")
        return

    # Validate environment variables before connecting
    valid, message = validate_config()
    if not valid:
        logger.error("=" * 60)
        logger.error(f"❌ ERROR DE CONFIGURACIÓN: {message}")
        logger.error("Por favor crea o edita el archivo .env basándote en .env.example")
        logger.error("=" * 60)
        sys.exit(1)

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

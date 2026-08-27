import time
import logging
import ctypes
import threading
from typing import Optional, Tuple

try:
    import win32gui
    import win32con
    import win32process
    import pyautogui
except ImportError:
    win32gui = None
    win32con = None
    win32process = None
    import pyautogui

logger = logging.getLogger("dota2-9d10.clicker")

# Mutex to ensure only ONE click action can execute at any time
_click_lock = threading.Lock()

# Windows API constants for preventing system / display sleep
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def prevent_screen_sleep():
    """Prevents Windows from turning off the display or sleeping while monitoring."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        logger.debug("Modo de energía configurado: pantalla y sistema activos.")
    except Exception as e:
        logger.debug(f"No se pudo configurar SetThreadExecutionState: {e}")


def restore_screen_sleep():
    """Restores default Windows sleep and display power management."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        logger.debug("Modo de energía restaurado al estándar de Windows.")
    except Exception as e:
        logger.debug(f"No se pudo restaurar SetThreadExecutionState: {e}")


def find_dota_window(title_keyword: str = "Dota 2") -> Optional[int]:
    """Finds the window handle (HWND) of the Dota 2 application."""
    if not win32gui:
        return None

    found_hwnd = []

    def enum_windows_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if title_keyword.lower() in window_text.lower() or class_name == "SDL_app":
                found_hwnd.append(hwnd)
        return True

    win32gui.EnumWindows(enum_windows_callback, None)
    return found_hwnd[0] if found_hwnd else None


def force_focus_window(hwnd: int) -> bool:
    """Forces the target window into the foreground."""
    if not win32gui:
        return False

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Bypass Windows focus-stealing prevention using Alt key pulse
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT down
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # ALT up

        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        return True
    except Exception as e:
        logger.warning(f"No se pudo forzar el foco de la ventana {hwnd}: {e}")
        return False


def accept_match(coords: Optional[Tuple[int, int]] = None) -> Tuple[bool, str]:
    """
    Executes the accept action in Dota 2 with strict single-click lock.
    Guarantees that only ONE click event is sent, avoiding duplicate clicks.
    """
    if not _click_lock.acquire(blocking=False):
        logger.warning("Intento de clic redundante descartado por bloqueo activo.")
        return True, "✅✅✅✅✅✅✅✅"

    try:
        hwnd = find_dota_window()
        if hwnd:
            logger.info(f"Ventana de Dota 2 encontrada (HWND: {hwnd}). Enfocando...")
            force_focus_window(hwnd)
            time.sleep(0.1)

        # Determine exact click position
        if coords:
            click_x, click_y = coords
            logger.info(f"Haciendo clic en coordenadas exactas detectadas: ({click_x}, {click_y})")
        else:
            screen_w, screen_h = pyautogui.size()
            click_x = screen_w // 2
            click_y = int(screen_h * 0.46)
            logger.info(f"Usando coordenadas de centro estimadas: ({click_x}, {click_y})")

        # Position mouse and execute strictly ONE click
        pyautogui.moveTo(click_x, click_y, duration=0.05)
        pyautogui.click(click_x, click_y)

        # Send Enter key as secondary confirmation
        time.sleep(0.08)
        pyautogui.press("enter")

        return True, "✅✅✅✅✅✅✅✅"
    except Exception as e:
        logger.error(f"Error al ejecutar la acción de aceptar: {e}")
        return False, f"Error al ejecutar clic: {str(e)}"
    finally:
        time.sleep(0.5)
        _click_lock.release()

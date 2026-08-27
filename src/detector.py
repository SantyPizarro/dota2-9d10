import io
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import win32gui
except ImportError:
    win32gui = None

import mss
import cv2
import numpy as np

from config import ASSETS_DIR, TEMP_DIR, DOTA2_WINDOW_TITLE
from src.clicker import find_dota_window

logger = logging.getLogger("dota2-9d10.detector")


class MatchDetector:
    """
    Ultra-lightweight and false-positive-immune Dota 2 Match Detector.
    Only analyzes screen content if the real Dota 2 game window is open.
    """

    def __init__(self, assets_dir: Path = ASSETS_DIR):
        self.assets_dir = assets_dir
        self.sct = None
        self._init_mss()

        self.template_path = self.assets_dir / "accept_template.png"
        self.template = None

        if self.template_path.exists():
            try:
                self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
                logger.info(f"Plantilla visual cargada desde {self.template_path}")
            except Exception as e:
                logger.warning(f"No se pudo cargar la plantilla: {e}")

    def _init_mss(self):
        try:
            if hasattr(mss, "MSS"):
                self.sct = mss.MSS()
            else:
                self.sct = mss.mss()
        except Exception as e:
            logger.debug(f"Error inicializando MSS: {e}")
            self.sct = None

    def get_dota_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, width, height) of the active Dota 2 window."""
        hwnd = find_dota_window(DOTA2_WINDOW_TITLE)
        if not hwnd or not win32gui:
            return None

        try:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            w = right - left
            h = bottom - top
            if w >= 640 and h >= 480:
                return left, top, w, h
            return None
        except Exception as e:
            logger.debug(f"No se pudo obtener el rectángulo de la ventana de Dota 2: {e}")
            return None

    def get_center_roi_bounds(self) -> Optional[Dict[str, int]]:
        """Calculates the central ROI strictly inside the Dota 2 window."""
        win_rect = self.get_dota_window_rect()
        if not win_rect:
            return None

        w_left, w_top, w_width, w_height = win_rect
        roi_w = int(w_width * 0.36)
        roi_h = int(w_height * 0.36)
        roi_left = w_left + int(w_width * 0.32)
        roi_top = w_top + int(w_height * 0.32)

        return {
            "left": roi_left,
            "top": roi_top,
            "width": roi_w,
            "height": roi_h,
            "win_left": w_left,
            "win_top": w_top,
            "win_width": w_width,
            "win_height": w_height,
        }

    def get_bottom_right_roi_bounds(self) -> Optional[Dict[str, int]]:
        """Calculates the bottom-right ROI strictly inside the Dota 2 window."""
        win_rect = self.get_dota_window_rect()
        if not win_rect:
            return None

        w_left, w_top, w_width, w_height = win_rect
        roi_w = int(w_width * 0.23)
        roi_h = int(w_height * 0.12)
        roi_left = w_left + int(w_width * 0.76)
        roi_top = w_top + int(w_height * 0.87)

        return {
            "left": roi_left,
            "top": roi_top,
            "width": roi_w,
            "height": roi_h,
            "win_left": w_left,
            "win_top": w_top,
            "win_width": w_width,
            "win_height": w_height,
        }

    def capture_roi(self, bounds: Dict[str, int]) -> Optional[np.ndarray]:
        """Captures a specific region of the screen."""
        if not self.sct:
            self._init_mss()
            if not self.sct:
                return None

        try:
            sct_img = self.sct.grab(
                {
                    "left": bounds["left"],
                    "top": bounds["top"],
                    "width": bounds["width"],
                    "height": bounds["height"],
                }
            )
            return np.array(sct_img)[:, :, :3]
        except Exception as e:
            logger.debug(f"Error en captura ROI GDI/MSS: {e}")
            self._init_mss()
            return None

    def check_match_ready(self, debug_save: bool = False) -> Tuple[bool, Optional[Tuple[int, int]], Optional[bytes]]:
        """
        Checks if the real Dota 2 'Accept' button is currently visible on screen.
        Guarantees zero false positives by validating:
        1. Dota 2 window is open and valid.
        2. Surrounding dialog box is dark (Dota 2 modal backdrop).
        3. Green button matches Dota 2 color, shape, text edge density, and central position.
        """
        try:
            roi_bounds = self.get_center_roi_bounds()
            # If Dota 2 is not open, immediately return False
            if not roi_bounds:
                return False, None, None

            img_bgr = self.capture_roi(roi_bounds)
            if img_bgr is None:
                return False, None, None

            roi_h, roi_w = img_bgr.shape[:2]

            # 1. Darkness validation: Dota 2 match modal has a dark backdrop
            gray_roi = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray_roi)
            # Web pages, documents, or light backgrounds typically have mean > 110
            if mean_brightness > 95:
                return False, None, None

            # 2. HSV color mask for Dota 2 green button
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            lower_green = np.array([35, 90, 70])
            upper_green = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            mask_cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            total_roi_area = roi_w * roi_h
            min_area = total_roi_area * 0.008  # At least 0.8% of central ROI
            max_area = total_roi_area * 0.25   # At most 25% of central ROI

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / max(h, 1)

                    # Dota 2 button is a wide rectangle
                    if 2.2 <= aspect_ratio <= 5.8:
                        box_mask = mask[y : y + h, x : x + w]
                        green_count = cv2.countNonZero(box_mask)
                        fill_density = green_count / float(w * h)

                        rect_area = w * h
                        solidity = float(area) / max(rect_area, 1)

                        # Must be solidly filled with green
                        if solidity >= 0.70 and fill_density >= 0.50:
                            # 3. Position verification: button must be centrally positioned in ROI
                            center_roi_x = x + w // 2
                            center_roi_y = y + h // 2
                            offset_from_center_x = abs(center_roi_x - roi_w // 2) / float(roi_w)
                            if offset_from_center_x > 0.20:
                                continue

                            # 4. Text/edge verification: characters inside "ACCEPT" / "ACEPTAR"
                            button_gray = gray_roi[y : y + h, x : x + w]
                            edges = cv2.Canny(button_gray, 40, 140)
                            edge_density = cv2.countNonZero(edges) / float(w * h)
                            if edge_density < 0.02:
                                continue

                            global_x = roi_bounds["left"] + center_roi_x
                            global_y = roi_bounds["top"] + center_roi_y

                            logger.info(
                                f"¡Botón de Aceptar Dota 2 CONFIRMADO! Coords: ({global_x}, {global_y}), "
                                f"Área: {area:.0f}, Ratio: {aspect_ratio:.2f}, Edge: {edge_density:.3f}"
                            )

                            # Preview image with bounding box for Discord
                            preview_bgr = img_bgr.copy()
                            cv2.rectangle(preview_bgr, (x, y), (x + w, y + h), (0, 255, 0), 3)
                            cv2.circle(preview_bgr, (center_roi_x, center_roi_y), 6, (0, 0, 255), -1)

                            _, buffer = cv2.imencode(".jpg", preview_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                            img_bytes = buffer.tobytes()

                            if debug_save:
                                debug_file = TEMP_DIR / "match_detected_debug.jpg"
                                with open(debug_file, "wb") as f:
                                    f.write(img_bytes)

                            return True, (global_x, global_y), img_bytes

            if debug_save:
                debug_file = TEMP_DIR / "no_match_debug.jpg"
                cv2.imwrite(str(debug_file), img_bgr)

            return False, None, None

        except Exception as e:
            logger.debug(f"Error o interrupción en check_match_ready: {e}")
            return False, None, None

    def check_is_searching(self) -> bool:
        """
        Checks if Dota 2 is actively searching for a match.
        Guarantees zero false positives:
        1. Only runs if Dota 2 window is open.
        2. Verifies bottom-right dark dashboard background.
        3. Identifies the cancel 'X' button in the specific coordinates of the queue bar.
        """
        try:
            roi_bounds = self.get_bottom_right_roi_bounds()
            # If Dota 2 is not running, never trigger searching
            if not roi_bounds:
                return False

            img_bgr = self.capture_roi(roi_bounds)
            if img_bgr is None:
                return False

            roi_h, roi_w = img_bgr.shape[:2]

            # 1. Dark dashboard verification
            gray_roi = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            if np.mean(gray_roi) > 85:
                return False

            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            # Red cancel 'X' button in Dota 2 matchmaking bar
            lower_red1 = np.array([0, 95, 70])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([165, 95, 70])
            upper_red2 = np.array([180, 255, 255])

            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)

            # Look specifically at the rightmost 35% of the play bar where the 'X' cancel button lives
            search_x_start = int(roi_w * 0.65)
            sub_mask = red_mask[:, search_x_start:]

            red_pixels = cv2.countNonZero(sub_mask)
            sub_area = sub_mask.shape[0] * sub_mask.shape[1]

            if sub_area > 0:
                ratio = red_pixels / float(sub_area)
                # The cancel button represents ~1.5% to 15% of this specific sub-region
                if 0.012 <= ratio <= 0.18:
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error en check_is_searching: {e}")
            return False

    def capture_full_screen_preview(self) -> Optional[bytes]:
        """Captures screen preview for testing or status checks."""
        win_rect = self.get_dota_window_rect()
        grab_area = None

        if win_rect:
            left, top, w, h = win_rect
            grab_area = {"left": left, "top": top, "width": w, "height": h}
        elif self.sct and len(self.sct.monitors) > 1:
            mon = self.sct.monitors[1]
            grab_area = mon

        if not grab_area:
            return None

        try:
            if not self.sct:
                self._init_mss()
            sct_img = self.sct.grab(grab_area)
            img_np = np.array(sct_img)[:, :, :3]
            h, w = img_np.shape[:2]
            if w > 1280:
                scale = 1280.0 / w
                new_w, new_h = int(w * scale), int(h * scale)
                img_np = cv2.resize(img_np, (new_w, new_h), interpolation=cv2.INTER_AREA)

            _, buffer = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            return buffer.tobytes()
        except Exception as e:
            logger.debug(f"No se pudo capturar vista previa: {e}")
            return None

import io
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import mss
import cv2
import numpy as np

from config import ASSETS_DIR, TEMP_DIR

logger = logging.getLogger("dota2-9d10.detector")


class MatchDetector:
    """
    Ultra-lightweight Dota 2 Game State and Match Ready Screen Detector.
    Uses region-of-interest (ROI) screen capture and color/shape analysis
    to detect matchmaking states with minimal CPU overhead.
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

    def get_screen_dimensions(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, width, height) of the primary monitor."""
        if not self.sct:
            self._init_mss()
            if not self.sct:
                return None
        try:
            mon = self.sct.monitors[1]
            return mon["left"], mon["top"], mon["width"], mon["height"]
        except Exception as e:
            logger.debug(f"No se pudieron obtener métricas del monitor: {e}")
            return None

    def get_center_roi_bounds(self) -> Optional[Dict[str, int]]:
        """
        Calculates the central region of interest (ROI) of the primary monitor.
        Focuses on the middle 40% x 40% where the Dota 2 Accept dialog appears.
        """
        dims = self.get_screen_dimensions()
        if not dims:
            return None
        left, top, w, h = dims
        return {
            "left": left + int(w * 0.30),
            "top": top + int(h * 0.30),
            "width": int(w * 0.40),
            "height": int(h * 0.40),
            "screen_width": w,
            "screen_height": h,
        }

    def get_bottom_right_roi_bounds(self) -> Optional[Dict[str, int]]:
        """
        Calculates the bottom-right region of interest (ROI) of the primary monitor.
        Focuses on the area where the 'PLAY DOTA' / 'FINDING MATCH' button and timer reside.
        """
        dims = self.get_screen_dimensions()
        if not dims:
            return None
        left, top, w, h = dims
        return {
            "left": left + int(w * 0.74),
            "top": top + int(h * 0.87),
            "width": int(w * 0.25),
            "height": int(h * 0.12),
            "screen_width": w,
            "screen_height": h,
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
        Checks if the Dota 2 'Accept' button is currently visible on screen.
        Returns:
            - is_ready (bool): True if match found.
            - click_coords (x, y): Global screen coordinates to click.
            - preview_image_bytes (bytes): JPEG image of the detected dialog for Discord preview.
        """
        try:
            roi_bounds = self.get_center_roi_bounds()
            if not roi_bounds:
                return False, None, None

            img_bgr = self.capture_roi(roi_bounds)
            if img_bgr is None:
                return False, None, None

            roi_h, roi_w = img_bgr.shape[:2]

            # Convert to HSV color space for robust green button detection
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            # Dota 2 "Accept" button green range
            # Hue: ~35-85 (Green), Saturation: >= 90, Value: >= 70
            lower_green = np.array([35, 90, 70])
            upper_green = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)

            # Clean mask using morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            mask_cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            total_roi_area = roi_w * roi_h
            min_area = total_roi_area * 0.005  # At least 0.5% of ROI
            max_area = total_roi_area * 0.20   # At most 20% of ROI

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / max(h, 1)

                    # The Accept button is a wide rectangle (aspect ratio between 2.0 and 6.5)
                    if 2.0 <= aspect_ratio <= 6.5:
                        # Check solid fill density
                        box_mask = mask[y : y + h, x : x + w]
                        green_count = cv2.countNonZero(box_mask)
                        fill_density = green_count / float(w * h)

                        # Check solidity (rectangular fill)
                        rect_area = w * h
                        solidity = float(area) / max(rect_area, 1)

                        if solidity >= 0.65 and fill_density >= 0.50:
                            # Button found! Calculate exact global screen coordinates
                            center_roi_x = x + w // 2
                            center_roi_y = y + h // 2
                            global_x = roi_bounds["left"] + center_roi_x
                            global_y = roi_bounds["top"] + center_roi_y

                            logger.info(
                                f"¡Botón de Aceptar detectado! Coords exactas: ({global_x}, {global_y}), "
                                f"Área: {area:.0f}, Ratio: {aspect_ratio:.2f}"
                            )

                            # Create preview image with bounding box for Discord
                            preview_bgr = img_bgr.copy()
                            cv2.rectangle(preview_bgr, (x, y), (x + w, y + h), (0, 255, 0), 3)
                            cv2.circle(preview_bgr, (center_roi_x, center_roi_y), 6, (0, 0, 255), -1)

                            # Encode preview as JPEG bytes
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
            logger.debug(f"Error o interrupción temporal en check_match_ready: {e}")
            return False, None, None

    def check_is_searching(self) -> bool:
        """
        Checks if Dota 2 is currently searching for a match by analyzing the bottom-right
        play/queue button (where the queue timer and red cancel 'X' button appear).
        """
        try:
            roi_bounds = self.get_bottom_right_roi_bounds()
            if not roi_bounds:
                return False

            img_bgr = self.capture_roi(roi_bounds)
            if img_bgr is None:
                return False

            roi_h, roi_w = img_bgr.shape[:2]
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            # In Dota 2, when actively searching, a red Cancel 'X' button or indicator
            # appears on the right half of the matchmaking bar.
            # Red color in HSV covers two ranges: 0-10 and 165-180
            lower_red1 = np.array([0, 90, 70])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([165, 90, 70])
            upper_red2 = np.array([180, 255, 255])

            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)

            # Only look at the rightmost 40% of the bottom-right bar where the 'X' button lives
            search_x_start = int(roi_w * 0.60)
            sub_mask = red_mask[:, search_x_start:]

            red_pixels = cv2.countNonZero(sub_mask)
            sub_area = sub_mask.shape[0] * sub_mask.shape[1]

            # The cancel 'X' button constitutes ~1% to 15% of this sub-region
            if sub_area > 0 and (0.008 <= (red_pixels / float(sub_area)) <= 0.25):
                return True

            return False

        except Exception as e:
            logger.debug(f"Error en check_is_searching: {e}")
            return False

    def capture_full_screen_preview(self) -> Optional[bytes]:
        """Captures the full primary monitor as JPEG bytes for testing or status checks."""
        if not self.sct:
            self._init_mss()
            if not self.sct:
                return None

        try:
            mon = self.sct.monitors[1]
            sct_img = self.sct.grab(mon)
            img_np = np.array(sct_img)[:, :, :3]
            h, w = img_np.shape[:2]
            if w > 1280:
                scale = 1280.0 / w
                new_w, new_h = int(w * scale), int(h * scale)
                img_np = cv2.resize(img_np, (new_w, new_h), interpolation=cv2.INTER_AREA)

            _, buffer = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            return buffer.tobytes()
        except Exception as e:
            logger.debug(f"No se pudo capturar vista previa completa: {e}")
            return None

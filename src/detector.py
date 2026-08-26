import io
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import mss
import cv2
import numpy as np
from PIL import Image

from config import ASSETS_DIR, TEMP_DIR

logger = logging.getLogger("dota2-9d10.detector")


class MatchDetector:
    """
    Ultra-lightweight Dota 2 Match Ready Screen Detector.
    Uses region-of-interest (ROI) screen capture and color/shape analysis
    to detect the 'Accept' button with minimal CPU overhead.
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

    def get_screen_roi_bounds(self) -> Optional[Dict[str, int]]:
        """
        Calculates the central region of interest (ROI) of the primary monitor.
        Focuses on the middle 40% x 40% where the Dota 2 Accept dialog appears.
        """
        if not self.sct:
            self._init_mss()
            if not self.sct:
                return None

        try:
            mon = self.sct.monitors[1]
            w = mon["width"]
            h = mon["height"]

            roi_w = int(w * 0.40)
            roi_h = int(h * 0.40)
            roi_left = mon["left"] + int(w * 0.30)
            roi_top = mon["top"] + int(h * 0.30)

            return {
                "left": roi_left,
                "top": roi_top,
                "width": roi_w,
                "height": roi_h,
                "screen_width": w,
                "screen_height": h,
            }
        except Exception as e:
            logger.debug(f"No se pudieron obtener métricas del monitor: {e}")
            return None

    def capture_roi(self) -> Tuple[Optional[np.ndarray], Optional[Dict[str, int]]]:
        """Captures only the central ROI of the screen using mss."""
        roi_bounds = self.get_screen_roi_bounds()
        if not roi_bounds:
            return None, None

        try:
            sct_img = self.sct.grab(
                {
                    "left": roi_bounds["left"],
                    "top": roi_bounds["top"],
                    "width": roi_bounds["width"],
                    "height": roi_bounds["height"],
                }
            )
            # Convert BGRA to BGR numpy array
            img_np = np.array(sct_img)[:, :, :3]
            return img_np, roi_bounds
        except Exception as e:
            logger.debug(f"Error en captura GDI/MSS (pantalla apagada o bloqueada): {e}")
            # Recreate mss instance for next attempt
            self._init_mss()
            return None, None

    def check_match_ready(self, debug_save: bool = False) -> Tuple[bool, Optional[Tuple[int, int]], Optional[bytes]]:
        """
        Checks if the Dota 2 'Accept' button is currently visible on screen.
        Returns:
            - is_ready (bool): True if match found.
            - click_coords (x, y): Global screen coordinates to click.
            - preview_image_bytes (bytes): JPEG image of the detected dialog for Discord preview.
        """
        try:
            img_bgr, roi = self.capture_roi()
            if img_bgr is None or roi is None:
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
                        # Check solid fill density (ensure the button is solidly filled with green)
                        box_mask = mask[y : y + h, x : x + w]
                        green_count = cv2.countNonZero(box_mask)
                        fill_density = green_count / float(w * h)

                        # Check solidity (rectangular fill)
                        rect_area = w * h
                        solidity = float(area) / max(rect_area, 1)

                        if solidity >= 0.65 and fill_density >= 0.50:
                            # Button found! Calculate global screen coordinates
                            center_roi_x = x + w // 2
                            center_roi_y = y + h // 2
                            global_x = roi["left"] + center_roi_x
                            global_y = roi["top"] + center_roi_y

                            logger.info(
                                f"¡Botón de Aceptar detectado! Área: {area:.0f}, Ratio: {aspect_ratio:.2f}, "
                                f"Densidad: {fill_density:.2f}, Coords: ({global_x}, {global_y})"
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
            logger.debug(f"Error o interrupción temporal en la detección visual: {e}")
            return False, None, None

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
            # Resize to max 1280px width for fast Discord upload
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

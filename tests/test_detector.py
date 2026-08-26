import cv2
import numpy as np
import pytest
from pathlib import Path
from src.detector import MatchDetector


def create_mock_dota_match_screen(width=1920, height=1080, has_button=True, button_color=(40, 190, 50)):
    """Generates a synthetic image simulating the Dota 2 dashboard and match found modal."""
    # Dark Dota 2 theme background (dark blue/black)
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (20, 20, 25)

    if has_button:
        # Draw central modal dialog box
        modal_w, modal_h = int(width * 0.35), int(height * 0.30)
        modal_x = (width - modal_w) // 2
        modal_y = (height - modal_h) // 2
        cv2.rectangle(img, (modal_x, modal_y), (modal_x + modal_w, modal_y + modal_h), (35, 35, 45), -1)
        cv2.rectangle(img, (modal_x, modal_y), (modal_x + modal_w, modal_y + modal_h), (80, 80, 100), 2)

        # Draw ACCEPT button
        btn_w = int(modal_w * 0.60)
        btn_h = int(modal_h * 0.25)
        btn_x = modal_x + (modal_w - btn_w) // 2
        btn_y = modal_y + int(modal_h * 0.50)

        # Border color matches button shade
        border_color = tuple(min(255, c + 30) for c in button_color)

        # Button fill (BGR format)
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), button_color, -1)
        # Button border
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), border_color, 2)

    return img


def test_detector_positive_1080p(monkeypatch):
    """Verifies that the detector correctly identifies the green accept button on 1080p."""
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=True)

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    roi_bounds = {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    }

    monkeypatch.setattr(detector, "capture_roi", lambda: (mock_roi, roi_bounds))

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is True
    assert coords is not None
    # Coords should be near the center of the 1920x1080 screen (960, ~540)
    assert 900 <= coords[0] <= 1020
    assert 480 <= coords[1] <= 600
    assert preview_bytes is not None
    assert len(preview_bytes) > 0


def test_detector_negative_empty_screen(monkeypatch):
    """Verifies that an empty screen does not trigger a false positive."""
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=False)

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    roi_bounds = {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    }

    monkeypatch.setattr(detector, "capture_roi", lambda: (mock_roi, roi_bounds))

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is False
    assert coords is None
    assert preview_bytes is None


def test_detector_negative_wrong_color_button(monkeypatch):
    """Verifies that a red or blue button in the center does not trigger false positive."""
    detector = MatchDetector()
    # Blue button (BGR: 220, 50, 30)
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=True, button_color=(220, 50, 30))

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    roi_bounds = {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    }

    monkeypatch.setattr(detector, "capture_roi", lambda: (mock_roi, roi_bounds))

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is False
    assert coords is None
    assert preview_bytes is None


def test_detector_720p_resolution(monkeypatch):
    """Verifies detection on 1280x720 (common low-spec laptop resolution)."""
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1280, 720, has_button=True)

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    roi_bounds = {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    }

    monkeypatch.setattr(detector, "capture_roi", lambda: (mock_roi, roi_bounds))

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is True
    assert coords is not None
    assert 600 <= coords[0] <= 680
    assert 320 <= coords[1] <= 420

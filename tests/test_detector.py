import cv2
import numpy as np
import pytest
from pathlib import Path
from src.detector import MatchDetector


def create_mock_dota_match_screen(width=1920, height=1080, has_button=True, button_color=(40, 190, 50)):
    """Generates a synthetic image simulating the Dota 2 dashboard and match found modal."""
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

        border_color = tuple(min(255, c + 30) for c in button_color)
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), button_color, -1)
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), border_color, 2)

    return img


def create_mock_bottom_right_roi(width=480, height=130, is_searching=True):
    """Generates a synthetic bottom-right ROI image simulating normal vs searching state."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (30, 30, 35)

    if is_searching:
        # Red cancel button 'X' on right side (BGR: red is (20, 30, 200))
        btn_x = int(width * 0.80)
        btn_y = int(height * 0.20)
        btn_w = int(width * 0.15)
        btn_h = int(height * 0.60)
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), (25, 30, 210), -1)
    else:
        # Normal play button (solid green bar on bottom)
        cv2.rectangle(img, (10, 10), (width - 10, height - 10), (30, 120, 40), -1)

    return img


def test_detector_positive_1080p(monkeypatch):
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=True)

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    monkeypatch.setattr(detector, "get_center_roi_bounds", lambda: {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    })
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is True
    assert coords is not None
    assert 900 <= coords[0] <= 1020
    assert 480 <= coords[1] <= 600
    assert preview_bytes is not None


def test_detector_negative_empty_screen(monkeypatch):
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=False)

    h, w = mock_screen.shape[:2]
    roi_top, roi_left = int(h * 0.30), int(w * 0.30)
    roi_h, roi_w = int(h * 0.40), int(w * 0.40)
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    monkeypatch.setattr(detector, "get_center_roi_bounds", lambda: {
        "left": roi_left,
        "top": roi_top,
        "width": roi_w,
        "height": roi_h,
        "screen_width": w,
        "screen_height": h,
    })
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is False
    assert coords is None
    assert preview_bytes is None


def test_detector_check_is_searching_positive(monkeypatch):
    detector = MatchDetector()
    mock_roi = create_mock_bottom_right_roi(480, 130, is_searching=True)

    monkeypatch.setattr(detector, "get_bottom_right_roi_bounds", lambda: {
        "left": 1400, "top": 900, "width": 480, "height": 130, "screen_width": 1920, "screen_height": 1080
    })
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    assert detector.check_is_searching() is True


def test_detector_check_is_searching_negative(monkeypatch):
    detector = MatchDetector()
    mock_roi = create_mock_bottom_right_roi(480, 130, is_searching=False)

    monkeypatch.setattr(detector, "get_bottom_right_roi_bounds", lambda: {
        "left": 1400, "top": 900, "width": 480, "height": 130, "screen_width": 1920, "screen_height": 1080
    })
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    assert detector.check_is_searching() is False

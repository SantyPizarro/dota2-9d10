import cv2
import numpy as np
import pytest
from pathlib import Path
from src.detector import MatchDetector


def create_mock_dota_match_screen(width=1920, height=1080, has_button=True, button_color=(40, 190, 50), is_bright=False):
    """Generates a synthetic image simulating the Dota 2 dashboard and match found modal."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Dark Dota 2 theme background or bright web page
    img[:] = (240, 240, 240) if is_bright else (20, 20, 25)

    if has_button:
        modal_w, modal_h = int(width * 0.35), int(height * 0.30)
        modal_x = (width - modal_w) // 2
        modal_y = (height - modal_h) // 2

        if not is_bright:
            # Dark modal dialog box in Dota 2
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

        # Add text edges inside button
        cv2.putText(
            img,
            "ACCEPT",
            (btn_x + int(btn_w * 0.15), btn_y + int(btn_h * 0.70)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

    return img


def create_mock_bottom_right_roi(width=440, height=120, is_searching=True):
    """Generates a synthetic bottom-right ROI image simulating normal vs searching state."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (25, 25, 30)

    if is_searching:
        # Red cancel button 'X' on right side (BGR: red is (20, 30, 200))
        btn_x = int(width * 0.82)
        btn_y = int(height * 0.25)
        btn_w = int(width * 0.12)
        btn_h = int(height * 0.50)
        cv2.rectangle(img, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), (25, 30, 210), -1)
    else:
        # Normal play button
        cv2.rectangle(img, (10, 10), (width - 10, height - 10), (30, 120, 40), -1)

    return img


def test_detector_dota_not_running(monkeypatch):
    """When Dota 2 window is not found, detector returns False immediately without scanning."""
    detector = MatchDetector()
    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: None)

    is_ready, coords, preview = detector.check_match_ready()
    assert is_ready is False
    assert coords is None

    is_searching = detector.check_is_searching()
    assert is_searching is False


def test_detector_positive_1080p(monkeypatch):
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=True)

    h, w = mock_screen.shape[:2]
    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: (0, 0, w, h))

    bounds = detector.get_center_roi_bounds()
    roi_top, roi_left = bounds["top"], bounds["left"]
    roi_h, roi_w = bounds["height"], bounds["width"]
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    monkeypatch.setattr(detector, "capture_roi", lambda b: mock_roi)

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is True
    assert coords is not None
    assert 900 <= coords[0] <= 1020
    assert 480 <= coords[1] <= 600
    assert preview_bytes is not None


def test_detector_negative_bright_background(monkeypatch):
    """A green element on a bright web page / editor MUST be rejected."""
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=True, is_bright=True)

    h, w = mock_screen.shape[:2]
    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: (0, 0, w, h))

    bounds = detector.get_center_roi_bounds()
    roi_top, roi_left = bounds["top"], bounds["left"]
    roi_h, roi_w = bounds["height"], bounds["width"]
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    monkeypatch.setattr(detector, "capture_roi", lambda b: mock_roi)

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is False
    assert coords is None


def test_detector_negative_empty_screen(monkeypatch):
    detector = MatchDetector()
    mock_screen = create_mock_dota_match_screen(1920, 1080, has_button=False)

    h, w = mock_screen.shape[:2]
    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: (0, 0, w, h))

    bounds = detector.get_center_roi_bounds()
    roi_top, roi_left = bounds["top"], bounds["left"]
    roi_h, roi_w = bounds["height"], bounds["width"]
    mock_roi = mock_screen[roi_top : roi_top + roi_h, roi_left : roi_left + roi_w]

    monkeypatch.setattr(detector, "capture_roi", lambda b: mock_roi)

    is_ready, coords, preview_bytes = detector.check_match_ready()

    assert is_ready is False
    assert coords is None
    assert preview_bytes is None


def test_detector_check_is_searching_positive(monkeypatch):
    detector = MatchDetector()
    mock_roi = create_mock_bottom_right_roi(440, 120, is_searching=True)

    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    assert detector.check_is_searching() is True


def test_detector_check_is_searching_negative(monkeypatch):
    detector = MatchDetector()
    mock_roi = create_mock_bottom_right_roi(440, 120, is_searching=False)

    monkeypatch.setattr(detector, "get_dota_window_rect", lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(detector, "capture_roi", lambda bounds: mock_roi)

    assert detector.check_is_searching() is False

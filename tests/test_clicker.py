from unittest.mock import patch, MagicMock
from src.clicker import accept_match


def test_accept_match_single_click():
    with patch("pyautogui.moveTo") as mock_move, \
         patch("pyautogui.click") as mock_click, \
         patch("pyautogui.press") as mock_press, \
         patch("src.clicker.find_dota_window", return_value=None):

        success, msg = accept_match(coords=(800, 450))

        assert success is True
        assert "800, 450" in msg
        mock_move.assert_called_once_with(800, 450, duration=0.05)
        # Verify strictly ONE click was made
        mock_click.assert_called_once_with(800, 450)
        mock_press.assert_called_once_with("enter")

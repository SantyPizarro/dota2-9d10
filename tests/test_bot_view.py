import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from src.bot import AcceptMatchView


def test_accept_match_view_accept_callback():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        view = AcceptMatchView(coords=(960, 540), timeout=10.0, on_action_done=mock_on_action)

        interaction = AsyncMock(spec=discord.Interaction)
        mock_message = MagicMock(spec=discord.Message)
        mock_message.embeds = [discord.Embed(title="Initial")]
        interaction.message = mock_message
        interaction.response = AsyncMock()

        with patch("src.bot.accept_match", return_value=(True, "Click simulated")):
            button = view.children[0]
            await button.callback(interaction)

        assert view.processed is True
        assert "accepted" in action_log
        interaction.response.edit_message.assert_awaited_once()

    asyncio.run(run())


def test_accept_match_view_decline_callback():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        view = AcceptMatchView(coords=(960, 540), timeout=10.0, on_action_done=mock_on_action)

        interaction = AsyncMock(spec=discord.Interaction)
        mock_message = MagicMock(spec=discord.Message)
        mock_message.embeds = [discord.Embed(title="Initial")]
        interaction.message = mock_message
        interaction.response = AsyncMock()

        with patch("src.bot.accept_match") as mock_accept:
            button = view.children[1]
            await button.callback(interaction)
            mock_accept.assert_not_called()

        assert view.processed is True
        assert "ignored" in action_log
        interaction.response.edit_message.assert_awaited_once()

    asyncio.run(run())


def test_accept_match_view_timeout():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        view = AcceptMatchView(coords=(960, 540), timeout=0.1, on_action_done=mock_on_action)

        await view.on_timeout()
        assert view.processed is True
        assert "timeout" in action_log
        for child in view.children:
            assert child.disabled is True

    asyncio.run(run())

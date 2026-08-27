import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from src.bot import AcceptMatchView


def test_accept_match_view_authorized_user():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        allowed_ids = {111222333, 444555666}
        view = AcceptMatchView(
            coords=(960, 540),
            allowed_user_ids=allowed_ids,
            timeout=10.0,
            on_action_done=mock_on_action,
        )

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 111222333  # Authorized!
        mock_message = MagicMock(spec=discord.Message)
        mock_message.embeds = [discord.Embed(title="Initial")]
        interaction.message = mock_message
        interaction.response = AsyncMock()

        # Check security filter
        is_allowed = await view.interaction_check(interaction)
        assert is_allowed is True

        with patch("src.bot.accept_match", return_value=(True, "✅✅✅✅✅✅✅✅")) as mock_click:
            button = view.children[0]
            await button.callback(interaction)
            mock_click.assert_called_once()

        assert view.processed is True
        assert "accepted" in action_log
        interaction.response.edit_message.assert_awaited_once()

    asyncio.run(run())


def test_accept_match_view_unauthorized_user_blocked():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        allowed_ids = {111222333}
        view = AcceptMatchView(
            coords=(960, 540),
            allowed_user_ids=allowed_ids,
            timeout=10.0,
            on_action_done=mock_on_action,
        )

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 999888777  # Unauthorized stranger!
        mock_message = MagicMock(spec=discord.Message)
        mock_message.embeds = [discord.Embed(title="Initial")]
        interaction.message = mock_message
        interaction.response = AsyncMock()

        # Check security filter
        is_allowed = await view.interaction_check(interaction)
        assert is_allowed is False

        # Verify custom ephemeral rejection message was sent
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "no toques" in args[0].lower() or "wachin" in args[0].lower()
        assert kwargs.get("ephemeral") is True

        # Ensure action was NOT processed
        assert view.processed is False
        assert len(action_log) == 0

    asyncio.run(run())


def test_accept_match_view_decline_callback():
    async def run():
        action_log = []

        def mock_on_action(action):
            action_log.append(action)

        view = AcceptMatchView(coords=(960, 540), timeout=10.0, on_action_done=mock_on_action)

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 123
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

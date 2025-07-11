from argparse import Namespace
from unittest.mock import Mock, patch

import pytest
from dasbus.error import DBusError

from command_line_assistant.client import main
from command_line_assistant.commands.base import BaseCLICommand
from command_line_assistant.constants import VERSION


class MockCommand(BaseCLICommand):
    def run(self):  # type: ignore
        return True


@pytest.mark.parametrize(
    ("argv", "stdin"),
    (
        (
            ["c", "chat", "test", "query"],
            None,
        ),
        (["c"], "test from stdin"),
        (["c", "what is this?"], "error in line 1"),
    ),
)
def test_initialize_with_query_command(argv, stdin):
    """Test initialize with query command"""
    mock_command = Mock(return_value=MockCommand(Namespace()))

    with (
        patch("sys.argv", argv),
        patch("command_line_assistant.commands.chat.register_subcommand"),
        patch("command_line_assistant.commands.history.register_subcommand"),
        patch("command_line_assistant.client.read_stdin", lambda: stdin),
        patch("argparse.ArgumentParser.parse_args") as mock_parse,
    ):
        mock_parse.return_value.func = mock_command
        result = main()

        assert result == 1
        mock_command.assert_called_once()


def test_initialize_with_history_command():
    """Test initialize with history command"""
    mock_command = Mock(return_value=MockCommand(Namespace()))

    with (
        patch("sys.argv", ["c", "history", "--clear"]),
        patch("command_line_assistant.commands.chat.register_subcommand"),
        patch("command_line_assistant.commands.history.register_subcommand"),
        patch("command_line_assistant.client.read_stdin", lambda: None),
        patch("argparse.ArgumentParser.parse_args") as mock_parse,
    ):
        mock_parse.return_value.func = mock_command
        result = main()

        assert result == 1
        mock_command.assert_called_once()


def test_initialize_with_shell_command():
    """Test initialize with shell command"""
    mock_command = Mock(return_value=MockCommand(Namespace()))

    with (
        patch("sys.argv", ["c", "shell", "--enable-integration"]),
        patch("command_line_assistant.commands.chat.register_subcommand"),
        patch("command_line_assistant.commands.history.register_subcommand"),
        patch("command_line_assistant.commands.shell.register_subcommand"),
        patch("command_line_assistant.client.read_stdin", lambda: None),
        patch("argparse.ArgumentParser.parse_args") as mock_parse,
    ):
        mock_parse.return_value.func = mock_command
        result = main()

        assert result == 1
        mock_command.assert_called_once()


def test_initialize_with_version(capsys):
    """Test initialize with --version flag"""
    with (
        patch("sys.argv", ["c", "--version"]),
        patch("command_line_assistant.client.read_stdin", lambda: None),
    ):
        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert VERSION in captured.out


def test_initialize_with_help(capsys):
    """Test initialize with --help flag"""
    with (
        patch("sys.argv", ["c", "--help"]),
        patch("command_line_assistant.client.read_stdin", lambda: None),
    ):
        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "usage:" in captured.out


def test_initialize_bad_stdin(capsys):
    with patch("command_line_assistant.client.read_stdin") as mock_stdin:
        mock_stdin.side_effect = ValueError("Binary input are not supported.")
        main()

    captured = capsys.readouterr()
    assert "\x1b[31m🙁 Binary input are not supported.\x1b[0m\n" in captured.err


def test_initialize_keyboard_interrupt(capsys):
    with patch("command_line_assistant.client.read_stdin") as mock_stdin:
        mock_stdin.side_effect = KeyboardInterrupt("Interrupted")
        main()

    captured = capsys.readouterr()
    assert "\x1b[31m🙁 Keyboard interrupt detected. Exiting...\x1b[0m\n" in captured.err


@pytest.mark.parametrize(
    ("argv"),
    [
        (["c"]),  # Default to chat
        (["c", "chat"]),
        (["c", "shell"]),
    ],
)
def test_initialize_command_selection(argv, capsys):
    """Test command selection logic"""

    with (
        patch("sys.argv", argv),
        patch("command_line_assistant.client.read_stdin", lambda: None),
    ):
        result = main()

    captured = capsys.readouterr()
    assert "usage: c" in captured.out
    assert result == 64


@pytest.mark.parametrize(
    ("exception", "expected"),
    (
        (DBusError, "Name is not active"),
        (RuntimeError, "Oops! Something went wrong while processing your request."),
    ),
)
def test_exception_initialization_error(exception, expected, capsys):
    with patch("command_line_assistant.client.read_stdin") as mock_stdin:
        mock_stdin.side_effect = exception(expected)
        main()

    captured = capsys.readouterr()
    assert expected in captured.err

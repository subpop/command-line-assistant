"""Module to handle the shell command."""

import logging
from argparse import Namespace
from enum import auto
from pathlib import Path
from typing import ClassVar, Union

from command_line_assistant.commands.base import (
    BaseCLICommand,
    BaseOperation,
    CommandOperationFactory,
    CommandOperationType,
)
from command_line_assistant.exceptions import ShellCommandException
from command_line_assistant.integrations import (
    BASH_INTERACTIVE,
)
from command_line_assistant.terminal.reader import (
    TERMINAL_CAPTURE_FILE,
    start_capturing,
)
from command_line_assistant.utils.cli import (
    SubParsersAction,
    create_subparser,
)
from command_line_assistant.utils.files import NamedFileLock, create_folder, write_file

#: The path to bashrc.d folder
BASH_RC_D_PATH: Path = Path("~/.bashrc.d").expanduser()

#: The complete path to the integration file.
INTERACTIVE_MODE_INTEGRATION_FILE: Path = Path(BASH_RC_D_PATH, "cla-interactive.bashrc")

#: The complete path to the persistent terminal capture mode.
PERSISTENT_TERMINAL_CAPTURE_FILE: Path = Path(
    BASH_RC_D_PATH, "cla-persistent-capture.bashrc"
)

#: File to track all the CLA environment variable exports.
ESSENTIAL_EXPORTS_FILE: Path = Path(BASH_RC_D_PATH, "cla-exports.bashrc")

logger = logging.getLogger(__name__)


class ShellOperationType(CommandOperationType):
    """Enum to control the operations for the command"""

    ENABLE_INTERACTIVE = auto()
    DISABLE_INTERACTIVE = auto()
    ENABLE_CAPTURE = auto()


class ShellOperationFactory(CommandOperationFactory):
    """Factory for creating shell operations with decorator-based registration"""

    # Mapping of CLI arguments to operation types
    _arg_to_operation: ClassVar[dict[str, CommandOperationType]] = {
        "enable_interactive": ShellOperationType.ENABLE_INTERACTIVE,
        "disable_interactive": ShellOperationType.DISABLE_INTERACTIVE,
        "enable_capture": ShellOperationType.ENABLE_CAPTURE,
    }


# Base class for shell operations with common functionality
class BaseShellOperation(BaseOperation):
    """Base shell operation common to all operations."""

    def _initialize_bash_folder(self) -> None:
        """Internal function to initialize the bash folder"""
        # Always ensure essential exports are in place
        create_folder(BASH_RC_D_PATH)

    def _write_bash_functions(self, file: Path, contents: Union[bytes, str]) -> None:
        """Internal funtion to write the bash function to the desired location

        Arguments:
            file (Path): The path object with the correct location
            contents (Union[bytes, str]): The contents to be written in the file.
        """
        self._initialize_bash_folder()
        if file.exists():
            logger.info("File already exists at %s.", file)
            self.write_warning_line(
                f"The integration is already present and enabled at {file}! "
                "Restart your terminal or source ~/.bashrc in case it's not working."
            )
            return

        # Make an educated guess whether or not the user's bash environment is
        # configured to load files from the bashrc.d folder. If not, print a
        # warning with a suggested solution.
        has_snippet = False
        rc_files = [
            Path(rc).expanduser()
            for rc in ["~/.bashrc", "~/.bash_profile", "~/.profile"]
        ]
        for rc_file in rc_files:
            try:
                if ".bashrc.d" in rc_file.read_text():
                    has_snippet = True
            except FileNotFoundError:
                continue

        if not has_snippet:
            self.write_warning_line(
                "In order to use shell integration, ensure your ~/.bashrc file loads files from ~/.bashrc.d. See /etc/skel/.bashrc for an example."
            )

        write_file(contents, file)
        self.write_line(
            f"Integration successfully added at {file}. "
            "In order to use it, please restart your terminal or source ~/.bashrc"
        )

    def _remove_bash_functions(self, file: Path) -> None:
        """Internal function to remove a bash integration

        Arguments:
            file (Path): The path object with the correct location
        """
        if not file.exists():
            logger.debug("Couldn't find integration file at '%s'", str(file))
            self.write_warning_line(
                "It seems that the integration is not enabled. Skipping operation."
            )
            return

        try:
            file.unlink()
            self.write_line("Integration disabled successfully.")
        except (FileExistsError, FileNotFoundError) as e:
            logger.warning(
                "Got an exception '%s'. Either file is missing or something removed just before this operation",
                str(e),
            )


# Register operations using the decorator
@ShellOperationFactory.register(ShellOperationType.ENABLE_INTERACTIVE)
class EnableInteractiveMode(BaseShellOperation):
    """Class to hold the enable interactive mode operation"""

    def execute(self) -> None:
        """Default method to execute the operation"""
        self._write_bash_functions(INTERACTIVE_MODE_INTEGRATION_FILE, BASH_INTERACTIVE)


@ShellOperationFactory.register(ShellOperationType.DISABLE_INTERACTIVE)
class DisableInteractiveMode(BaseShellOperation):
    """Class to hold the disable interactive mode operation"""

    def execute(self) -> None:
        """Default method to execute the operation"""
        self._remove_bash_functions(INTERACTIVE_MODE_INTEGRATION_FILE)


@ShellOperationFactory.register(ShellOperationType.ENABLE_CAPTURE)
class EnableTerminalCapture(BaseShellOperation):
    """Class to hold the enable terminal capture operation"""

    def execute(self) -> None:
        """Default method to execute the operation"""
        file_lock = NamedFileLock(name="terminal")

        if file_lock.is_locked:
            raise ShellCommandException(
                f"Detected a terminal capture session running with pid '{file_lock.pid}'."
                " In order to start a new terminal capture session, you must stop the previous one."
            )

        with file_lock:
            self.write_line(
                "Starting terminal reader. Press Ctrl + D to stop the capturing."
            )
            self.write_line(
                f"Terminal capture log is being written to {TERMINAL_CAPTURE_FILE}"
            )
            self._initialize_bash_folder()
            start_capturing()


class ShellCommand(BaseCLICommand):
    """Class that represents the history command."""

    def run(self) -> int:
        """Main entrypoint for the command to run.

        Returns:
            int: Return the status code for the operation
        """
        operation_factory = ShellOperationFactory()
        try:
            # Get and execute the appropriate operation
            operation = operation_factory.create_operation(self._args, self._context)
            if operation:
                operation.execute()

            return 0
        except ShellCommandException as e:
            logger.info("Failed to execute shell command: %s", str(e))
            self.write_error_line(str(e))
            return e.code


def register_subcommand(parser: SubParsersAction):
    """
    Register this command to argparse so it's available for the root parser.

    Arguments:
        parser (SubParsersAction): Root parser to register command-specific arguments
    """
    shell_parser = create_subparser(parser, "shell", "Manage shell integrations")

    terminal_capture_group = shell_parser.add_argument_group("Terminal Capture Options")
    terminal_capture_group.add_argument(
        "--enable-capture",
        action="store_true",
        help="Enable terminal capture for the current terminal session.",
    )

    interactive_mode = shell_parser.add_argument_group("Interactive Mode Options")
    interactive_mode.add_argument(
        "--enable-interactive",
        action="store_true",
        help=(
            "Enable the shell integration for interactive mode on the system. "
            "Currently, only BASH is supported. After the interactive was "
            "sourced, hit Ctrl + G in your terminal to enable interactive mode."
        ),
    )
    interactive_mode.add_argument(
        "--disable-interactive",
        action="store_true",
        help="Disable the shell integration for interactive mode on the system.",
    )

    shell_parser.set_defaults(func=_command_factory)


def _command_factory(args: Namespace) -> ShellCommand:
    """Internal command factory to create the command class

    Arguments:
        args (Namespace): The arguments processed with argparse.

    Returns:
        ShellCommand: Return an instance of class
    """
    return ShellCommand(args)

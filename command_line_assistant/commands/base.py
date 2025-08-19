"""Base module to hold classes and definitions for commands"""

import logging
import sys
from abc import ABC, abstractmethod
from argparse import Namespace
from enum import Enum
from functools import wraps
from typing import ClassVar, Optional, Protocol, Type

from command_line_assistant.dbus.constants import (
    CHAT_IDENTIFIER,
    HISTORY_IDENTIFIER,
    USER_IDENTIFIER,
)
from command_line_assistant.dbus.interfaces.chat import ChatInterface
from command_line_assistant.dbus.interfaces.history import HistoryInterface
from command_line_assistant.dbus.interfaces.user import UserInterface
from command_line_assistant.rendering.colors import Color, colorize
from command_line_assistant.rendering.formatting import wrap
from command_line_assistant.rendering.streaming import MarkdownStreamer
from command_line_assistant.utils.cli import CommandContext

logger = logging.getLogger(__name__)


class BaseCLICommand(ABC):
    """Absctract class to define a CLI Command."""

    def __init__(self, args: Namespace) -> None:
        """Constructor for the base class."""
        self._args = args
        self._context: CommandContext = CommandContext()
        self._stdout_stream = MarkdownStreamer(stream=sys.stdout)
        self._stderr_stream = MarkdownStreamer(stream=sys.stderr)

        super().__init__()

    @abstractmethod
    def run(self) -> int:
        """Entrypoint method for all CLI commands."""

    def write_error_line(self, text: str) -> None:
        """
        Write error text to the terminal.
        """
        self._stderr_stream.add_line_chunk(
            wrap(colorize(f"⛔️ {text}", Color.BRIGHT_RED))
        )


class CommandOperation(Protocol):
    """Protocol that all shell operations must implement"""

    def execute(self) -> None:
        """Execute the shell operation"""


class CommandOperationType(Enum):
    """Base enum to serve as definition for other commands"""


class BaseOperation:
    """Base operation that all commands can inherit

    Note:
        This class contains all the basic attriutes that all commands operation
        can use, even though, some of them might not need the attributes here.

    Attributes:
        args (Namespace): The arguments parsed from argparse
        context (CommandContext): Contextual data read before arguments are parsed.

        chat_proxy (ChatInterface): The proxy for the chat object
        history_proxy (HistoryInterface): The proxy for the history object
        user_proxy (UserInterface): The proxy for the user object
    """

    def __init__(
        self,
        args: Namespace,
        context: CommandContext,
        chat_proxy: ChatInterface,
        history_proxy: HistoryInterface,
        user_proxy: UserInterface,
    ) -> None:
        """Constructor of the class.

        Arguments:
            args (Namespace): The arguments from CLI
            context (CommandContext): Context for the commands
            chat_proxy (ChatInterface): The proxy object for dbus chat
            history_proxy (HistoryInterface): The proxy object for dbus history
            user_proxy (HistoryInterface): The proxy object for dbus user
        """
        self.args = args
        self.context = context
        self.chat_proxy = chat_proxy
        self.history_proxy = history_proxy
        self.user_proxy = user_proxy
        self._stdout_stream = MarkdownStreamer(stream=sys.stdout)
        self._stderr_stream = MarkdownStreamer(stream=sys.stderr)

    def write_info_line(self, text: str) -> None:
        """
        Write info text to the terminal.

        Arguments:
            text (str): The text to write.
        """
        self._stdout_stream.add_line_chunk(
            wrap(colorize(f"ℹ️ {text}", Color.BRIGHT_YELLOW))
        )

    def write_warning_line(self, text: str) -> None:
        """
        Write warning text to the terminal.
        """
        self._stdout_stream.add_line_chunk(
            wrap(colorize(f"⚠️ {text}", Color.BRIGHT_YELLOW))
        )

    def write_error_line(self, text: str) -> None:
        """
        Write error text to the terminal.
        """
        self._stderr_stream.add_line_chunk(
            wrap(colorize(f"⛔️ {text}", Color.BRIGHT_RED))
        )

    def write_line(self, text: str) -> None:
        """
        Write text to the terminal.

        Arguments:
            text (str): The text to write.
        """
        self._stdout_stream.add_line_chunk(text)

    def write_line_raw(self, text: str) -> None:
        """
        Write text to the terminal without any formatting.
        """
        self._stdout_stream.write_raw(text)


class CommandOperationFactory:
    """Factory for creating shell operations with decorator-based registration.

    Attributes:
        _operations (ClassVar[dict[CommandOperationType, Type[CommandOperation]]]): Dictionary of operations from a command.
        _arg_to_operation (ClassVar[dict[str, CommandOperationType]]): Mapping of argument from CLI to a specific operation.
    """

    # Class-level storage for registered operations
    _operations: ClassVar[dict[CommandOperationType, Type[CommandOperation]]] = {}

    # Mapping of CLI arguments to operation types
    _arg_to_operation: ClassVar[dict[str, CommandOperationType]] = {}

    @classmethod
    def register(cls, operation_type: CommandOperationType):
        """Decorator to register a shell operation class

        Arguments:
            operation_type (CommandOperationType): The mapping of operation type to register the class.

        Returns:
            FunctionType: local function used as decorator
        """

        def decorator(operation_class: Type[CommandOperation]):
            """The actual decorator that will process the operation class.

            Arguments:
                operation_class (Type[CommandOperation]): The class being decorated

            Returns:
                FunctionType: wrapped internal function to decorate the class.
            """
            # Validate that the operation implements the required interface
            if not hasattr(operation_class, "execute"):
                raise ValueError(
                    f"Operation class {operation_class.__name__} must implement 'execute' method"
                )

            # Prevent duplicate registrations
            if operation_type in cls._operations:
                raise ValueError(
                    f"Operation type {operation_type} is already registered to {cls._operations[operation_type].__name__}"
                )

            cls._operations[operation_type] = operation_class

            @wraps(operation_class)
            def wrapped_class(*args, **kwargs):
                """Wrapped class function to return the operation class."""
                return operation_class(*args, **kwargs)

            logger.debug(
                "Registered operation %s for type %s",
                operation_class.__name__,
                operation_type,
            )
            return wrapped_class

        return decorator

    def create_operation(
        self,
        args: Namespace,
        context: CommandContext,
    ) -> Optional[CommandOperation]:
        """Create an operation instance based on command line arguments

        Arguments:
            args (Namespace): The arguments parsed from the cli
            context (CommandContext): The contextual data read before we parse arguments

        Returns:
            Optional[CommandOperation]: The operation created.
        """
        # Find the first matching argument that is True
        operation_type = next(
            (
                op_type
                for arg_name, op_type in self._arg_to_operation.items()
                if getattr(args, arg_name, False)
            ),
            None,
        )
        if not operation_type:
            return None

        operation_class = self._operations.get(operation_type)
        if operation_class is None:
            logger.warning("No operation registered for type %s", operation_type)
            return None

        # Type Ignoring the parameters as they do exist in the baes class.
        return operation_class(
            args=args,  # type: ignore
            context=context,  # type: ignore
            chat_proxy=CHAT_IDENTIFIER.get_proxy(),  # type: ignore
            user_proxy=USER_IDENTIFIER.get_proxy(),  # type: ignore
            history_proxy=HISTORY_IDENTIFIER.get_proxy(),  # type: ignore
        )

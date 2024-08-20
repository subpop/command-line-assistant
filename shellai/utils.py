import os

def pprint(message: str, color: str) -> None:
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "reset": "\033[0m",  # Reset color to default
    }
    if os.getenv("NO_COLOR") is not None:
        print(message)
    else:
        print(colors[color] + message + colors["reset"])

def dbg_print(message: str, color: str) -> None:
    if os.getenv("DEBUG") is not None:
        pprint(message, color)


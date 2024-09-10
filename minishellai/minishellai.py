import json
import requests
import os
import sys
import logging

SHELLAI_CAPTURED_FILE = "minishellai_captured"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)


def get_payload(query:str) -> dict:
     # Payload "msg" has to have the following structure. It is important that
    # roles of "user" and "assistant" are alternating. Role of "user" is always
    # first.
    # {"role": "user", "content": "tell me about selinux one sentence"},
    # {"role": "assistant", "content": "selinux is really cool."},
    # {"role": "user", "content": "how do I enable selinux?"},
    # TODO: Implement history loading to payload
    payload = {
        "msg": [
            {"role": "user", "content": query},
        ],
        "metadata": {}
    }
    return payload

def start_script_session() -> None:
    """
    Starts a 'script' session and writes the PID to a file, but leaves control of the terminal to the user.
    """
    # Prepare the script command
    script_command = ["script", "-f", SHELLAI_CAPTURED_FILE]

    # Start the script session and leave control to the terminal
    os.system(' '.join(script_command))

    # Remove the SHELLAI_CAPTURED_FILE after the script session ends
    if os.path.exists(SHELLAI_CAPTURED_FILE):
        logging.info(f"Removing {SHELLAI_CAPTURED_FILE}")
        os.remove(SHELLAI_CAPTURED_FILE)


def handle_query(query: str) -> None:
    logging.info("Waiting for response from AI...")
    payload = get_payload(query)

    response = requests.post(
        "http://0.0.0.0:8082/api/v1/query/", # TODO: move to config
        headers = {"Content-Type": "application/json"},
        data = json.dumps(payload),
        timeout = 30 # waiting for more than 30 seconds does not make sense
    )

    if response.status_code == 200:
        completion = response.json()
        data = completion.get("data", None)
        answer = data
    else:
        print(f"Failed to get response from AI: {response.status_code}", file=sys.stderr)
        exit(1)
    print(answer)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print(f"Usage: {sys.argv[0]} <'init'|query-like-string>", file=sys.stderr)
        exit(1)

    if args[0] != 'init' and not os.path.exists(SHELLAI_CAPTURED_FILE):
        # TODO config option, ignore script if specifically set to false
        print(f"Please call `{sys.argv[0]} init` first to initialize script session.", file=sys.stderr)
        exit(1)

    if args[0] == 'init':
        start_script_session()
    else:
        logging.info(f"Query: {''.join(args)}")
        handle_query(''.join(args))


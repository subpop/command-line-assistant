import json
import requests
import argparse
import os
import sys

SHELLAI_CAPTURED_FILE = "minishellai_captured"


def get_payload(args):
     # Payload "msg" has to have the following structure. It is important that
    # roles of "user" and "assistant" are alternating. Role of "user" is always
    # first.
    # {"role": "user", "content": "tell me about selinux one sentence"},
    # {"role": "assistant", "content": "selinux is really cool."},
    # {"role": "user", "content": "how do I enable selinux?"},
    # TODO: Implement history loading to payload
    payload = {
        "msg": [
            {"role": "user", "content": args.query},
        ],
        "metadata": {}
    }
    return payload

def start_script_session(append=False, timing_file=None, command=None):
    """
    Starts a 'script' session and writes the PID to a file, but leaves control of the terminal to the user.

    :param log_file: The file where the session log will be saved.
    :param append: If True, the log will be appended to the existing file.
    :param timing_file: Timing information will be saved in this file if specified.
    :param command: If specified, only this command will be logged.
    """
    # Prepare the script command
    script_command = ["script", "-f", SHELLAI_CAPTURED_FILE]

    # Append to the log if requested
    if append:
        script_command.append("-a")

    # Add the timing file option if provided
    if timing_file:
        script_command += ["-t", timing_file]

    # Add the command to run if provided
    if command:
        script_command += ["-c", command]

    # Start the script session and leave control to the terminal
    os.system(' '.join(script_command))


def handle_query(args):
    if not args.init and not os.path.exists(SHELLAI_CAPTURED_FILE):
        print(f"You have to run {sys.argv[0]} with --init flag first.")
        exit(1)

    if args.init:
        start_script_session()
        exit(0)

    if args.read:
        print("Not implemented yet")
        exit(1)

    payload = get_payload(args)

    response = requests.post(
        "http://0.0.0.0:8082/api/v1/query/", # TODO: move to config
        headers = {"Content-Type": "application/json"},
        data = json.dumps(payload),
        timeout = 30 # waiting for more than 30 seconds does not make sense
    )

    answer = None
    if response.status_code == 200:
        completion = response.json()
        data = completion.get("data", None)
        answer = data
    print(answer)
    return answer

def handle_read():
    with open(SHELLAI_CAPTURED_FILE, "r") as f:
        lines = f.readlines()
    # TODO: parse file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minishell AI")
    # Either init or query has to be provided
    mg = parser.add_mutually_exclusive_group(
        required=True
    )
    mg.add_argument("--query", "-q", help="Query to be sent to the AI")
    mg.add_argument("--init", help="Initialize the script session", action="store_true")
    mg.add_argument("--read", help="Read the captured session", action="store_true")

    args = parser.parse_args()

    if args.query or args.init:
        handle_query(args)
    elif args.read:
        handle_read()


import json
import logging
import os
import select
import sys

import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)


def read_stdin():
    # Check if there's input available on stdin
    if select.select([sys.stdin], [], [], 0.0)[0]:
        # If there is input, read it
        input_data = sys.stdin.read().strip()
        return input_data
    # If no input, return None or handle as you prefer
    return None

def read_yaml_config(config_file: str) -> dict:
    if not os.path.exists(config_file):
        print(f"Config file {config_file} does not exist (use env 'SHELLAI_CONFIG' to change destination).", file=sys.stderr)
        return {}
    with open(config_file, 'r') as f:
        logging.info(f"Reading config file {config_file}")
        return yaml.safe_load(f)

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


def start_script_session(shellai_tmp_file) -> None:
    """
    Starts a 'script' session and writes the PID to a file, but leaves control of the terminal to the user.
    """
    # Prepare the script command
    script_command = ["script", "-f", shellai_tmp_file]

    # Start the script session and leave control to the terminal
    os.system(' '.join(script_command))

    # Remove the captured output after the script session ends
    if os.path.exists(shellai_tmp_file):
        logging.info(f"Removing {shellai_tmp_file}")
        os.remove(shellai_tmp_file)

def handle_caret(query: str, config:dict) -> str:
    """
    Replaces caret (^) with command output specified in config file.
    """
    if '^' not in query:
        return query

    output_capture_settings = config.get('output_capture_settings', {})
    captured_output_file = output_capture_settings.get('captured_output_file', '/tmp/minishellai_output.txt')

    if not os.path.exists(captured_output_file):
        logging.error(f"Output file {captured_output_file} does not exist, change location of file in config to use '^'.")
        exit(1)

    prompt_separator = output_capture_settings.get('prompt_separator', '$')
    with open(captured_output_file, 'r') as f:
        # NOTE: takes only last command + output from file
        output = f.read().split(prompt_separator)[-1].strip()
    query = query.replace('^', "")
    query = f"Context data: {output}\nQuestion: " + query
    return query


def handle_query(query: str, config: dict) -> None:
    query = handle_caret(query, config)
    # NOTE: Add more query handling here

    logging.info(f"Query:\n{query}")

    backend_service = config.get('backend_service', {})
    query_endpoint = backend_service.get('query_endpoint', 'http://0.0.0.0:8080/api/v1/query/')

    try:
        response = requests.post(
            query_endpoint,
            headers = {"Content-Type": "application/json"},
            data = json.dumps(get_payload(query)),
            timeout = 30 # waiting for more than 30 seconds does not make sense
        )
        logging.info("Waiting for response from AI...")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get response from AI: {e}")
        exit(1)

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
    query = None

    if input_data := read_stdin():
        logging.debug("stdin detected")
        query = input_data.strip()

    if not args and query is None:
        print(f"Usage: {sys.argv[0]} <'record'|query-like-string>", file=sys.stderr)
        exit(1)

    config_path = os.getenv('SHELLAI_CONFIG', 'config.yaml')
    config = read_yaml_config(config_path)
    if not config:
        logging.warning("Config file not found. Script will continue with default values.")

    output_capture_settings = config.get('output_capture_settings', {})
    enforce_script_session = output_capture_settings.get('enforce_script_session', False)
    captured_output_file = output_capture_settings.get('captured_output_file', '/tmp/minishellai_output.txt')

    if enforce_script_session and args and args[0] != 'record' and not os.path.exists(captured_output_file):
        print(f"Please call `{sys.argv[0]} record` first to initialize script session.", file=sys.stderr)
        exit(1)

    if args and args[0] == 'record':
        start_script_session(captured_output_file)
    else:
        arg_query = ''.join(args)
        if arg_query:
            if query is not None:
                query += '\n' + arg_query
            else:
                query = arg_query
        elif query is None:
            print(f"Usage: {sys.argv[0]} <'record'|query-like-string>", file=sys.stderr)
            exit(1)

        handle_query(query, config)


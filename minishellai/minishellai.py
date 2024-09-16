import argparse
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

def read_history(config: dict) -> dict:
    """
    Reads the history from a file and returns it as a list of dictionaries.
    """
    if not config.get('enabled', False):
        return []

    filepath = config.get('filepath', '/tmp/minishellai_history.json')
    if not filepath or not os.path.exists(filepath):
        logging.warning(f"History file {filepath} does not exist.")
        logging.warning("File will be created with first response.")
        return []

    max_size = config.get('max_size', 100)
    history = []
    try:
        with open(filepath, 'r') as f:
            history = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to read history file {filepath}: {e}")
        return []

    logging.info(f"Taking maximum of {max_size} entries from history.")
    return history[:max_size]

def write_history(config: dict, history: list, response: str) -> None:
    """
    Writes the history to a file.
    """
    if not config.get('enabled', False):
        return
    filepath = config.get('filepath', '/tmp/minishellai_history.json')
    if response:
        history.append({"role": "assistant", "content": response})
    try:
        with open(filepath, 'w') as f:
            json.dump(history, f)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to write history file {filepath}: {e}")

def get_payload(query:str, history: list) -> dict:
     # Payload "msg" has to have the following structure. It is important that
    # roles of "user" and "assistant" are alternating. Role of "user" is always
    # first.
    # {"role": "user", "content": "tell me about selinux one sentence"},
    # {"role": "assistant", "content": "selinux is really cool."},
    # {"role": "user", "content": "how do I enable selinux?"},
    payload = {
        "msg": [
            *history,
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
        history_conf = config.get('history', {})
        history = read_history(history_conf)
        payload = get_payload(query, history)
        logging.info("Waiting for response from AI...")
        response = requests.post(
            query_endpoint,
            headers = {"Content-Type": "application/json"},
            data = json.dumps(payload),
            timeout = 30 # waiting for more than 30 seconds does not make sense
        )
        response.raise_for_status()
        completion = response.json()
        response_data = completion.get("data", None)
        references = completion.get("references", None)
        references_str = '\n\nReferences:\n' +'\n'.join(references) if references else ""
        write_history(history_conf, payload.get('msg', []), response_data)
        print(response_data + references_str)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get response from AI: {e}")
        exit(1)

def get_args():
    parser = argparse.ArgumentParser(description="A script with multiple optional arguments and a required positional argument if no optional arguments are provided.")

    parser.add_argument('--history-clear', action='store_true', help="Clear the history.")
    parser.add_argument('--record', action='store_true', help="Initialize a script session (all other arguments will be ignored).")
    parser.add_argument('--config', default=os.getenv('SHELLAI_CONFIG', 'config.yaml'), help="Path to the config file.")

    # Positional argument, required only if no optional arguments are provided
    parser.add_argument('query_string', nargs='?', help="Query string to be processed.")


    args = parser.parse_args()
    optional_args = [
        args.history_clear,
        args.record,
    ]
    if not args.query_string and (input_data := read_stdin()):
        logging.debug("stdin detected")
        args.query_string = input_data.strip()

    if not any(optional_args) and not args.query_string:
        parser.error("Query string is required if no optional arguments are provided.")
    return parser, args


if __name__ == "__main__":
    parser, args = get_args()

    config = read_yaml_config(args.config)
    if not config:
        logging.warning("Config file not found. Script will continue with default values.")

    output_capture_conf = config.get('output_capture', {})
    enforce_script_session = output_capture_conf.get('enforce_script', False)
    output_file = output_capture_conf.get('output_file', '/tmp/minishellai_output.txt')

    if enforce_script_session and (not args.record or not os.path.exists(output_file)):
        parser.error(f"Please call `{sys.argv[0]} --record` first to initialize script session or create the output file.", file=sys.stderr)

    # NOTE: This needs more refinement, script session can't be combined with other arguments
    if args.record:
        start_script_session(output_file)
        exit(0)
    if args.history_clear:
        logging.info("Clearing history of conversation")
        write_history(config.get('history', {}), [], "")
    if args.query_string:
        handle_query(args.query_string, config)

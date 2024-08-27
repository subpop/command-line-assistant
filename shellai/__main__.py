import argparse
import os
import typing as t

from distro import name
from sys import stdin

from utils import dbg_print
from core import run


# TODO: move it all to config file and choose what is overridable by cmd args
def load_config() -> dict[str, t.Any]:
    # Model Configuration
    # https://platform.openai.com/docs/models/gpt-3-5


    # storing temporary files and configs in ~/.config/shellai
    home_dir: str = os.path.expanduser("~")
    config_dir: str= os.path.join(home_dir, ".config/shellai")
    os.makedirs(config_dir, exist_ok=True)

    conf_dict = {
        "MODEL": "gpt-3.5-turbo",
        "MODEL_INPUT_PRICE_PER_TOKEN": 0.0005 / 1000,  # Pricing: https://openai.com/pricing#language-models
        "MODEL_OUTPUT_PRICE_PER_TOKEN": 0.0015 / 1000,
        "TEMPERATURE": 0.0,  # 0.0 - 2.0: output randomness, https://platform.openai.com/docs/api-reference/completions/create
        "CONTEXT_WINDOW_MAX_ENTRIES": 10,  # set context window to max N entries
        "CONTEXT_WINDOW_MAX_TOKENS": 1000, # sets context window to max N tokens, can be changed with flag,
        "CODE_BLOCK_TAG": "~", # tag that will be used to wrap code blocks in the answer,
        "TOKEN_CODE_ONLY": "=", # tag to force code output only,
        "TOKEN_INLINE_EXECUTION": "==", # tag to force inline command execution,
        "TOKEN_SHELL_INTERACTION": "^", # tag to add last shell output to context,
        "SHELL_PROMPT_TAG": "$>", # tag to detect shell prompt,
        "CODE_BLOCKS_FILE": f"{config_dir}/code_blocks.json", # this is where we store detected code from last run,
        "CMD_CALL_OUTPUT_TMP_FILE": f"{config_dir}/code_blocks_output.tmp", # this is where we sneak in the output of execuded cmd for a while,
        "CONTEXT_FILE": f"{config_dir}/context.json", # this is where we store the chat history AKA what we will have for context,
        "SHELL_OUTPUT_FILE": f"{config_dir}/shellai_output_cleaned.tmp",
        "OS_NAME":  name(pretty=True),
        "STOCK_SYSTEM_ROLE": False,  # to know if we have to set our custom system role or not
        "NO_COLOR": bool(os.getenv("NO_COLOR")),
        "DEBUG": bool(os.getenv("DEBUG")),
    }
    return conf_dict

def overide_and_extend_config_from_args(
        conf_dict: dict, args: argparse.Namespace, unknown_args) -> None:
    conf_dict["DEBUG"] = args.debug
    if conf_dict["DEBUG"]:
        os.environ["DEBUG"] = "1"  # because of utils function

    if args.nocolor:
        conf_dict["NO_COLOR"] = True
        os.environ["NO_COLOR"] = "1" # because of utils function

    conf_dict["STOCK_SYSTEM_ROLE"] = True

    if args.maxcontext:
       conf_dict["CONTEXT_WINDOW_MAX_TOKENS"] = 16000
    if args.clearcontext:
        if os.path.exists(conf_dict["CONTEXT_FILE"]):
            os.remove(conf_dict["CONTEXT_FILE"])
    if args.systemrole:
        conf_dict["DEFAULT_SYSTEM_ROLE"] = args.systemrole.read()
    if args.nosystemrole:
        conf_dict["DEFAULT_SYSTEM_ROLE"] = ""
    if args.gpt4:
        conf_dict["MODEL"] = "gpt-4o"
        # Pricing: https://openai.com/pricing#language-models
        conf_dict["MODEL_INPUT_PRICE_PER_TOKEN"] = 0.005 / 1000
        conf_dict["MODEL_OUTPUT_PRICE_PER_TOKEN"] = 0.015 / 1000

    # we just take whole stdin if there is any since it will be used for pipe chaining
    input_stdin: str = ""
    if not stdin.isatty():
        for line in stdin:
            input_stdin += line
    conf_dict["INPUT_STDIN"] = input_stdin
    dbg_print(f"[input_stdin]: {input_stdin}", color="green")

    # we want to add to the input_argv only non-flag tokens
    input_argv: str = " ".join(unknown_args)
    conf_dict["INPUT_ARGV"] = input_argv
    dbg_print(f"[input_argv]: {input_argv}", color="green")

    # we want to exit on empty input otherwise we create empty api call down the line
    if len(input_stdin.strip()) == 0 and len(input_argv.strip()) == 0:
        print("No input provided. Exiting.")
        exit(0)


def main() -> None:
    conf_dict = load_config()

    parser = argparse.ArgumentParser(description="ShellAI: AI assistant for Linux shell")
    parser.add_argument("--debug", action="store_true", help="Show debug output")
    parser.add_argument("--stockrole", action="store_true", help="Uses stock system role")
    parser.add_argument(
        "--maxcontext", action="store_true",
        help=f"Uses max context window. Default is {conf_dict['CONTEXT_WINDOW_MAX_TOKENS']} tokens."
    )
    parser.add_argument("--clearcontext", action="store_true", help="Clears context window")

    group = parser.add_mutually_exclusive_group(
        required=False,
    )
    group.add_argument("--systemrole", type=argparse.FileType("r"), help="Specify system role from a file")
    group.add_argument("--nosystemrole", action="store_true", help="Forces no system role")
    parser.add_argument("--nocolor", action="store_true", help="Standard output without color")
    parser.add_argument("--gpt4", action="store_true", help="Uses GPT-4 model instead of GPT-3")
    parser.add_argument("--openai-base-url", type=str, help="OpenAI base URL for API calls. This can be locally hosted OpenAI API.")
    parser.add_argument("--api-key", type=str, help="OpenAI API key. Overrides OPENAI_API_KEY env variable.")

    # NOTE: be careful, this means that if user creates typo in flags, it will be treated as input
    args, unknown_args = parser.parse_known_args()
    overide_and_extend_config_from_args(conf_dict, args, unknown_args)

    # Print debug infor about used args
    dbg_print(f"[args]: {args}", color="green")

    run(conf_dict)

if __name__ == "__main__":
    main()

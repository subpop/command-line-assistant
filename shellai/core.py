import os
import requests
from json import load, dump, dumps
import sys

from subprocess import call
from typing import Optional, Any

from tiktoken import encoding_for_model

from utils import pprint, dbg_print
from sys_roles import DEFAULT_SYSTEM_ROLE, CODE_ONLY_SYSTEM_ROLE

def ask(config: dict[str, Any]) -> str:
    """ this is how context (and it's history) is looking as the user asks questions and gets answers
    system role
    user question 1
    assistance answer 1

    user question 1
    assistance answer 1
    system role    <-- we are moving system role before the latest user question for consistency
    user question 2
    assistance answer 2
    """
    # the type of the context entry is "dict[str, str]", but mypy complained too much
    #  I told it to go off and so it is "Any" now
    input_context: list[Any] = []
    if len(config["INPUT_STDIN"]) > 0:
        input_context.append({"role": "user", "content": config["INPUT_STDIN"]})
    if len(config["INPUT_ARGV"]) > 0:
        input_context.append({"role": "user", "content": config["INPUT_ARGV"]})

    # when user wants to get default model baviour via STOCK_SYSTEM_ROLE flag
    # we just set content of the system role to empty string
    system_role_content: str = ""
    if config["STOCK_SYSTEM_ROLE"]:
        system_role_content = DEFAULT_SYSTEM_ROLE.format(
            OS_NAME=config["OS_NAME"], CODE_BLOCK_TAG=config["CODE_BLOCK_TAG"])

    system_role: list[Any] = [{"role": "system", "content": system_role_content}]

    # we will build this context as we go, depending on the current context state
    context: list[Any] = []

    context_file_path = config["CONTEXT_FILE"]

    if os.path.exists(context_file_path) and os.path.getsize(context_file_path) != 0:
        # we will build on top of the existing context
        with open(context_file_path, "rt") as context_fd_r:

            historic_context: list[Any] = load(context_fd_r)
            context = historic_context + input_context
    else:
        # we need to build context from scratch
        with open(context_file_path, "wt") as context_fd_w:
            context = system_role + input_context
            dump(context, context_fd_w)

    # are we counting total amount of tokens currently stored in context
    # to make sure we are not exceeding the API token limit and also to make sure
    # we are not spending too much money on the API calls
    encoding = encoding_for_model(config["MODEL"])
    total_context_tokens: int = 0
    for entry in context:
        total_context_tokens += len(encoding.encode(entry["content"]))
    dbg_print(f"[total context tokens]: {total_context_tokens}", color="green")

    # we are trimming number of entries in the context to stay below CONTEXT_WINDOW_MAX_ENTRIES
    while len(context) > config["CONTEXT_WINDOW_MAX_ENTRIES"]:
        entry: dict[str, str] = context.pop(0)
        dbg_print(f"[removing context entry from context]: {entry}", color="red")

    # we are repeatedly going over whole context and trimming biggest contenxt entries
    #  to keep total number of tokens in context under CONTEXT_WINDOW_MAX_TOKENS
    while total_context_tokens > config["CONTEXT_WINDOW_MAX_TOKENS"]:
        biggest_entry_tokens: int = 0
        biggest_entry_i: int = 0
        for i, entry in enumerate(context):
            if i == 0:
                continue # we dont want to touch the system_role entry
            entry_tokens: int = len(encoding.encode(entry["content"]))
            if entry_tokens > biggest_entry_tokens:
                biggest_entry_tokens = entry_tokens
                biggest_entry_i = i
        # we take the longest entry and trip the upper half from it,
        #  effectivelly halving it in size and keeping the latter part
        #  we do this because the huge output like `ps aux` would overflow
        #  G_CONTEXT_WINDOW_MAX_TOKENS the reason why we trim upper half is that
        #  we want to perserve the latest output of the command, which is at the end
        biggest_entry_length: int = len(context[biggest_entry_i]["content"])
        biggest_entry_first_half: str = context[biggest_entry_i]["content"][:int(biggest_entry_length/2)]
        num_tokens_to_delete: int = len(encoding.encode(biggest_entry_first_half))
        biggest_entry_second_half: str = context[biggest_entry_i]["content"][int(biggest_entry_length/2):]
        context[biggest_entry_i]["content"] = biggest_entry_second_half
        total_context_tokens -= num_tokens_to_delete
        dbg_print(f"[trimming tokens from context]: {num_tokens_to_delete}", color="red")


    # since we want to keep system role just before the question in our context
    #  we have to find where the system role entry in context currently is and delete it
    for item in context:
        if item["role"] == "system":
            context.remove(item)
            break

    # we want to catch if user ends argv with TOKEN_CODE_ONLY and/or TOKEN_INLINE_EXECUTION
    #  TOKEN_CODE_ONLY will be for code output only
    #  while TOKEN_INLINE_EXECUTION will get the code output immediately executed
    input_argv = config["INPUT_ARGV"]
    if len(input_argv) > 1 and input_argv[-1] == config["TOKEN_CODE_ONLY"]:
        system_role[0]["content"] = CODE_ONLY_SYSTEM_ROLE.format(
            OS_NAME=config["OS_NAME"], CODE_BLOCK_TAG=config["CODE_BLOCK_TAG"])

    # TODO: we should be stripping TOKEN_CODE_ONLY and TOKEN_INLINE_EXECUTION from input_argv

    # when user types TOKEN_SHELL_INTERACTION at the end of argv we will find
    #  last executed command and its stdout/stderr in SHELL_OUTPUT_FILE and
    #  append it to context, this ensures interactivity with shell
    if len(input_argv) > 0 and config["TOKEN_SHELL_INTERACTION"] == input_argv[-1]:
        with open(config["SHELL_OUTPUT_FILE"], "r") as shell_output_fd_r:
            lines = []
            for line in shell_output_fd_r.readlines():
                lines.append(line.strip())
            last_command: str = ""
            last_command_output: str = ""
            while len(lines) > 0:
                last_line = lines.pop()
                if config["SHELL_PROMPT_TAG"] in last_line:
                    last_command = last_line.split("$>")[1]
                    break
                else:
                    last_command_output = last_line + last_command_output

            if len(context) > 0:
                # we need to get out the prompt from input_argv out of the context
                #  because we want to put command and its output before it
                #  otherwise the LLM will not generate good answers
                argv_prompt = context.pop()
                context.append({"role": "user", "content": f"Command executed: {last_command}"})
                context.append({"role": "user", "content": f"Command output: {last_command_output}"})
                context.append(argv_prompt)


    # we are putting system role at the end of the context because it provides better results
    #  if the system role is at the beginning, we dont get consistent answers when the history is long
    context += system_role

    # Construct the payload for the POST request
    # TODO: will have to format the prompt correctly, this is for granite:
    # https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-ibm-chat.html?context=wx
    flattened_context = ""
    for entry in context:
        flattened_context += str(entry) + "\n"

    payload = {
        "msg": flattened_context,
        "metadata": {}
    }

    # Make the POST request
    response = requests.post(
        "http://0.0.0.0:8000/api/v1/query/", # TODO: move to config
        headers={"Content-Type": "application/json"},
        data=dumps(payload),
        timeout=30 # waiting for more than 30 seconds does not make sense
    )

    answer = None
    completion = None
    if response.status_code == 200:
        completion = response.json()
        print(f"completion: {completion}")
        data = completion.get("data", None)
        if data:
            answer: Optional[str] = data.get("response", None)
    else:
        answer: Optional[str] = None

    # TODO: Remove this debug print
    print(20*"-")
    print(f"context: {flattened_context}")
    print(20*"-")
    print(f"response: {response}")
    print(20*"-")
    print(f"answer: {answer}")

    if completion and 'usage' in completion:
        input_tokens: int = completion['usage'].get('prompt_tokens', 0)
        input_tokens_cost: float = input_tokens * config["MODEL_INPUT_PRICE_PER_TOKEN"]
        output_tokens: int = completion['usage'].get('completion_tokens', 0)
        output_tokens_cost: float = output_tokens * config["MODEL_OUTPUT_PRICE_PER_TOKEN"]
        total_tokens: int = input_tokens + output_tokens
        total_tokens_cost: float = input_tokens_cost + output_tokens_cost
        dbg_print(
            f"[input tokens]: {input_tokens},
            [cost]: {'${:.6f}'.format(input_tokens_cost)}", color="green")
        dbg_print(
            f"[output tokens]: {output_tokens},
            [cost]: {'${:.6f}'.format(output_tokens_cost)}", color="green")
        dbg_print(
            f"[total tokens]: {total_tokens},
            [cost]: {'${:.6f}'.format(total_tokens_cost)}", color="green")

    # the TOKEN_INLINE_EXECUTION at the end of argv means that we will go straight into code execution
    inplace_command_executed = False
    cmd_stdout: str = "" # these are outside of if block because we want to use it later to append output to context
    if len(input_argv) > 1 and f"{input_argv[-1]}{input_argv[-2]}" == config['TOKEN_INLINE_EXECUTION']:
        cmd_call(f"{answer} | tee {config['CMD_CALL_OUTPUT_TMP_FILE']}")


        if os.path.exists(config['CMD_CALL_OUTPUT_TMP_FILE']):
            # NOTE: not sure how to handle when the md_call_output_tmp_file
            # fails to be created with tee due to weird answer.
            # Report error? or just silently go by?
            with open(config['CMD_CALL_OUTPUT_TMP_FILE'], "rt") as tmp_file_fd_r:
                cmd_stdout = tmp_file_fd_r.read()
                os.remove(config['CMD_CALL_OUTPUT_TMP_FILE'])
        inplace_command_executed = True # we need to store this to know how to exit later

    # after getting the answer, we have to attach it to the context
    #  and save to perserve the overall context across runs
    with open(config['CONTEXT_FILE'], "w") as context_fd_w:
        if answer is None:
            answer = ""
        if inplace_command_executed is True:
            # we are doing this to make sure model holds in context the knowledge
            #  of the command was executed, otherwise it will just get confused
            #  when asked about it and say something like:
            #  "I cannot execute commands" or "I dont know how to execute commands"
            context.append({"role": "assistant", "content": f"Command executed: {answer}"})
        else:
            context.append({"role": "assistant", "content": answer})
        if len(cmd_stdout) > 0:
            context.append({"role": "assistant", "content": f"stdout: {cmd_stdout}"})
        dump(context, context_fd_w)

    for item in context:
        dbg_print(f"[context]: {item}", color="green")

    if inplace_command_executed is True:
        exit(0)
    return answer

def cmd_call(command: str) -> None:
    call(command, shell=True)

def extract_code(text: str, code_block_tag:str) -> list[str]:
    blocks: list[str] = []
    append: bool = False
    block: str = ""
    for line in text.split("\n"):
        if line.count(code_block_tag) == 2:
            # we have code in one line formatted like: {CODE_BLOCK_TAG} code {CODE_BLOCK_TAG}
            blocks.append(line.split(code_block_tag)[1])
            continue # to handle code formatted in multiple lines
        if line.count(code_block_tag) and append is False:
            append = True
            continue
        if line.count(code_block_tag) and append is True:
            append = False
            blocks.append(block)
            block = ""
        if append is True:
            block += line + "\n" # we need "\n" in case the code is formatted in multiple lines
    return blocks

def cmd_call_output_to_context(command: str, context_file_path, cmd_call_output_tmp_file: str) -> None:
    """ we want to also store output executed command to cmd_call_output_tmp_file
    the reason why we do this is so we can load the output and insert it into the context,
     """
    if os.path.exists(context_file_path) and os.path.getsize(context_file_path) != 0:
        context: list[Any] = []
        # since we executed shell command, we want to append the command output
        #  and command name to context to have continuity in context
        with open(context_file_path, "rt") as context_fd_r:
            context = load(context_fd_r)
            # prepending "Executing command:" seemed like a good idea to enhance context NOTE: "Executing command:" might be parametrized and optimized later
            context.append({"role": "user", "content": f"Executing command: {command}"})
        with open(cmd_call_output_tmp_file, "rt") as tmp_file_fd_r:
            # TODO: we should handle the case when cmd_call_output_tmp_file was not created by tee
            tmp_file_content: str = tmp_file_fd_r.read()
            # NOTE: we could clean up unecessary spaces from the output
            #        this would save us some tokens depending on how many spaces
            #        there are (some commands output a lot of spaces)
            if len(tmp_file_content) > 0:
                context.append({"role": "user", "content": f"{tmp_file_content}"})
            # we are done with cmd_call_output_tmp_file because we already executed
            #  command, so we can delete it
            # next command execution will create new cmd_call_output_tmp_file
            os.remove(cmd_call_output_tmp_file)
        with open(context_file_path, "wt") as context_fd_w:
            dump(context, context_fd_w)
        for item in context:
            dbg_print(f"[context]: {item}", color="green")

def run(client, config) -> None:
    # if there is any code to be executed we do it right now, so we can exit right after
    if os.path.exists(config["CODE_BLOCKS_FILE"]) and os.path.getsize(config["CODE_BLOCKS_FILE"]) != 0:
        with open(config["CODE_BLOCKS_FILE"], "rt") as code_blocks_fd_r:
            id_to_code_block_r: dict[str, str] = load(code_blocks_fd_r)
            if config["INPUT_ARGV"].strip() in id_to_code_block_r:
                # we are stiping the pesky "\n" here
                code_block_cmd: str = id_to_code_block_r[config["INPUT_ARGV"].strip()].strip()
                # why we are using pipe tee ?
                #  because I don't know how to make subprocess.popen() behave
                #  correctly with interactive shell commands like dnf, so we
                #  just call subprocess.call() which does not return cmd output,
                #  therefore we stash the output via tee to tmp file
                cmd_call(f"{code_block_cmd} | tee {config['CMD_CALL_OUTPUT_TMP_FILE']}")
                cmd_call_output_to_context(code_block_cmd, config['CONTEXT_FILE'], config['CMD_CALL_OUTPUT_TMP_FILE'])
                exit(0) # we dont want to continue after command execution

    # hand the inputs over to make api calls and get back completion, context
    #  mangement is handled inside ask()
    answer: str = ask(config)

    # detecting code in reply and storing into file for possible later execution
    code_blocks: list[str] = extract_code(answer, config["CODE_BLOCK_TAG"])
    if len(code_blocks) > 0:
        id_to_code_block_w: dict[int, str] = {}
        for block_id, block in enumerate(code_blocks):
            id_to_code_block_w[block_id] = block.strip("\n")
        with open(config["CODE_BLOCKS_FILE"], "w") as code_blocks_fd_w:
            dump(id_to_code_block_w, code_blocks_fd_w)

    # NOTE: potential to print out the answer in a nice way, color formatting, etc...
    for line in answer.split("\n"):
        pprint(line, color="green")

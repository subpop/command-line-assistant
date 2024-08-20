# READ FIRST

This tool uses OpenAI API to generate responses.
You need to have an OpenAI API key to use it which you can get from <https://openai.com> and get some API credits since OpenAI API is not free.
Also, this means that **everything you use this tool for will be sent to OpenAI servers! Be careful with sensitive information!**

## Installation

Install dependencies:

``` bash
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

Add your `OPENAI_API_KEY` to `~/.config/shellai/openai_api_key`:

``` bash
mkdir -p ~/.config/shellai
echo "OPENAI_API_KEY=your-openai-key" > ~/.config/shellai/openai_api_key
```

### Set convenient alias

**[RECOMMENDED]** Set convenient shell alias (like `ai`) for ease of use:

``` bash
alias ai="python $PWD/shellai"
```

### Enable interaction with previously executed command outputs

**[RECOMMENDED]** To enable `shellai` interacting with the previously executed shell command outputs, you have to install `tmux` and run `shellai` inside `tmux`.
Additionally, you have to put the following code in your `~/.bashrc`.
It will invoke `tmux`, capturing the output of the previous command and store it in a temporary file for `shellai` to use.
(Desclaimer: I didn't test it with other shells other than `bash`.)

``` bash
# Set the PROMPT_COMMAND to capture the output after each command
SHELL_OUTPUT="${HOME}/.config/shellai/shellai_output.tmp"
SHELL_OUTPUT_CLEANED="${HOME}/.config/shellai/shellai_output_cleaned.tmp"
# Function to capture the pane's output
function capture_pane_output() {
    tmux capture-pane -p > "$SHELL_OUTPUT"
    grep -v '^$' ${SHELL_OUTPUT} > ${SHELL_OUTPUT_CLEANED}
    rm -f ${SHELL_OUTPUT}
}
PROMPT_COMMAND="capture_pane_output"
```

If you get `ImportError: urllib3 v2.0 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with LibreSSL 2.8.3`, try this:

```sh
pip uninstall urllib3
pip install 'urllib3<2.0'
```

All temporary files created during the usage (context, code blocks, command call output, captured shell output) are stored in `~/.config/shellai/*`

## Usage

```txt
usage: shellai.py [-h] [--debug] [--stockrole] [--maxcontext] [--clearcontext] [--systemrole SYSTEMROLE] [--nosystemrole] [--nocolor] [--gpt4]

ShellAI: AI assistant for Linux shell

options:
  -h, --help            show this help message and exit
  --debug               Show debug output
  --stockrole           Uses stock system role
  --maxcontext          Uses max context window. Default is 1000 tokens.
  --clearcontext        Clears context window
  --systemrole SYSTEMROLE
                        Specify system role from a file
  --nosystemrole        Forces no system role
  --nocolor             Standard output without color
  --gpt4                Uses GPT-4 model instead of GPT-3
```

## Example Usage and Overview of the Features

### Basic usage

`ai PROMPT` or `python3 shellai PROMPT [args]`.

```txt
$ ai how to find how much free memory do I have?
You can find the amount of free memory on your system by using the `free` command. Here's the command:

~ 0
free -m
~
```

### Execute code block

Execute code block from previous answer: `ai C_CODE_BLOCK_ID`.
Note, there can be multiple code blocks with their own ID in the answer, so you can choose which one to execute.

```txt
$ ai 0
               total        used        free      shared  buff/cache   available
Mem:           32011       16712        7552         732        7746       14110
Swap:           8191           0        8191
```

### Print only command

Print only code/command, not explanation: `ai PROMPT =`

```txt
$ ai number of running systemd units =
systemctl list-units --state=running | wc -l
```

### Inline execution of suggested command

Inline execution: `ai PROMPT ==`. Be **CAREFUL** with this, as it will execute the command directly on your system without any confirmation.

```txt
$ ai show currently connected usb devices ==
Bus 001 Device 002: ID 1bcf:0005 Sunplus Innovation Technology Inc. Optical Mouse
Bus 001 Device 003: ID 05ac:1392 Apple, Inc. Apple Watch charger
Bus 001 Device 007: ID 05f3:0081 PI Engineering, Inc. Kinesis Integrated Hub
Bus 001 Device 010: ID 05f3:0007 PI Engineering, Inc. Kinesis Advantage PRO MPC/USB Keyboard
Bus 004 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
```

### Chaining multiple shellai commands

Chaining multiple shellai commands with pipe `|`. The genrated output of the first `ai` command is used as `stdin` for the second `ai` command.
Note: Regarding context structure, the `stdin` is always in front/above of the `argv`.

```txt
ai journalctl warnings from last 4 days == | ai anything interesting?
```

### Interacting with shell stdout/stderr

Interacting with shell `stdout/stderr` by putting `^` at the end of the line:

```txt
$ python snippet.py
Traceback (most recent call last):
  File "snippet.py", line 3, in <module>
    print(sample_dict["non_existent_key"])
KeyError: 'non_existent_key'

$ cat snippet.py | ai what is the problem with my code? ^

```txt
Exmplanation: The contents of the `snippet.py` file are passed to the `shellai` on `stdin`.
The `stdout/stderr` of the previous command (`python snippet.py`) along with the command name and `argv` are stored in the context just above the `argv="what is the problem with my code?"`.

---

Input via `cat`. Useful for pasting large text from clipboard.

```txt
$ cat | ai explain
what is ebpf?
eBPF (extended Berkeley Packet Filter) is a technology in the Linux kernel ...
Ctrl-D
```

### Use localy deployed model

TODO

## TODO

- [ ] Add option to invoke confirmation before executing the command inline with `==`
- [ ] BUG: The token trimming when the context window is full is not working properly. It can get stuck in an infinite loop. Reword this so it used different truncation strategy, maybe drop messages from middle or use keep last N message strategy
- [ ] Clean up configuration options, use env variables with app prefix, make more configruation overidable by cmd arguments
- [ ] Split ask() and run() functions in core to more readable code
- [ ] Add support for vLLM (<https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html>) and update README with how to ude local model

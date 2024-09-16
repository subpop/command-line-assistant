# CLI tool `shellai` for interacting with lightspeed service (RHEL)

For now it is expected to work with:

* [core-backend](https://gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/core-backend)
  * Set up the core-backend [via local-dev-env](https://gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/local-dev-env)

## Install & Create config

To install the package, run the following command:

```sh
pip3 install git+ssh://git@gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/shellai.git

# OR https instead of ssh
```

Save config to your desired path and then set environment variable for shellai to find the config.

```sh
export SHELLAI_CONFIG_PATH=/path/to/config.yaml
```

```yml
# Example config.yaml
output_capture: # if '^' is used, last command output will be used for query context
  enforce_script: false  # otherwise recording via script session will be enforced
  output_file: /tmp/shellai_output.txt  # file with output(s) of regular commands (e.g. ls, echo, etc.)
  prompt_separator: '$'  # Keep non-empty if your file contains only output of commands (not prompt itself)
backend_service:
  # proxy: http://todo:8080
  query_endpoint: http://0.0.0.0:8082/api/v1/query/
history:
  enabled: true
  filepath: shellai_history.json
  max_size: 100  # max number of queries in history (including responses)
```

## Example queries

Note that the core-backend service must be running to get answer from RAG

```sh
python3 shellai.py --record
python3 shellai.py "How to uninstall RHEL?"
python3 shellai.py --history-clear "How to uninstall RHEL?"
python3 shellai.py --config <custom config path> "How to uninstall RHEL?"

# OR with stdin

echo "How to uninstall RHEL?" | python3 shellai.py
echo "How to uninstall RHEL?" | python3 shellai.py "Text that will be appended to the stdin"

# Usage of caret '^'
# Takes last command output as query context (must be available from output_file value in config)
python3 shellai.py "How to uninstall RHEL? ^"
#
# The query then is in following format:
# 2024-09-11 14:27:01,667 - INFO - Query:
# Context data: context text from file specified in config
# Question: How to uninstall RHEL?
```

## How to capture cmd output for usage of `^`

1. Use `script` tool and it's session
2. Use `tee` command to simply save output of command to some file
3. Use `tmux` workaround below

### `tmux` workaround to capture output of every command

Please note that this is up to the user to decide if this is the best way to capture output of every command including potential sensitive data.

Install `tmux` and put the following code in your `~/.bashrc`.
It will invoke `tmux`, capturing the output of the previous command and store it in a temporary file for `shellai` to use.
(Desclaimer: I didn't test it with other shells other than `bash`.)

``` bash
# Set the PROMPT_COMMAND to capture the output after each command
SHELL_OUTPUT="$/tmp/shellai_output.tmp"
SHELL_OUTPUT_CLEANED="/tmp/shellai/shellai_output_cleaned.tmp"
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

All temporary files created during the usage (context, code blocks, command call output, captured shell output) are stored in `/tmp/shellai/*`

## Future improvements

* [ ] Add tests
* [ ] Add more actions like `^`
  * e.g. `==` to execute the command or `=` to print just command response
  * Or be able to execute code blocks from response (if available)

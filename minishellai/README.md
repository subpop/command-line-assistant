# Mini version of `shellai`

Made for interaction with [core-backend](https://gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/core-backend)

Set up the core-backend [via local-dev-env](https://gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/local-dev-env)

## Create config

Save config to your desired path and then set environment variable for minishellai to find the config.

```sh
export SHELLAI_CONFIG_PATH=/path/to/config.yaml
```

```yml
# Example config.yaml
output_capture: # if '^' is used, last command output will be used for query context
  enforce_script: false  # otherwise recording via script session will be enforced
  output_file: /tmp/minishellai_output.txt  # file with output(s) of regular commands (e.g. ls, echo, etc.)
  prompt_separator: '$'  # Keep non-empty if your file contains only output of commands (not prompt itself)
backend_service:
  # proxy: http://todo:8080
  query_endpoint: http://0.0.0.0:8082/api/v1/query/
history:
  enabled: true
  filepath: minishellai_history.json
  max_size: 100  # max number of queries in history (including responses)
```

## Example queries

Note that the core-backend service must be running to get answer from RAG

```sh
python3 minishellai.py --record
python3 minishellai.py "How to uninstall RHEL?"
python3 minishellai.py --history-clear "How to uninstall RHEL?"
python3 minishellai.py --config <custom config path> "How to uninstall RHEL?"

# OR with stdin

echo "How to uninstall RHEL?" | python3 minishellai.py
echo "How to uninstall RHEL?" | python3 minishellai.py "Text that will be appended to the stdin"

# Usage of caret '^'
# Takes last command output as query context (must be available from output_file value in config)
python3 minishellai.py "How to uninstall RHEL? ^"
#
# The query then is in following format:
# 2024-09-11 14:27:01,667 - INFO - Query:
# Context data: context text from file specified in config
# Question: How to uninstall RHEL?
```

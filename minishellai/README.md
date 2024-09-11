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


```

## Example queries

Note that the core-backend service must be running to get answer from RAG

```sh
python3 minishellai.py init
python3 minishellai.py "How to uninstall RHEL?"

# OR with stdin

echo "How to uninstall RHEL?" | python3 minishellai.py
echo "How to uninstall RHEL?" | python3 minishellai.py "Text that will be appended to the stdin"
```

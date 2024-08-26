import json
import requests
import sys

if len(sys.argv) < 2:
    exit(1)
argv_query = " ".join(sys.argv[1:])

# Payload "msg" has to have the following structure. It is important that
# roles of "user" and "assistant" are alternating. Role of "user" is always
# first.
# {"role": "user", "content": "tell me about selinux one sentence"},
# {"role": "assistant", "content": "selinux is really cool."},
# {"role": "user", "content": "how do I enable selinux?"},

# TODO: Implement history loading to payload
payload = {
    "msg": [
        {"role": "user", "content": argv_query},
    ],
    "metadata": {}
}

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

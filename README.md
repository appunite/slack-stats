# Calculate Slack Stats

Project is used for calculating stats from Slack channels

## Setup

*Pre requirements:* You need to have python3 installed


Create python virtual environment:
```bash
python3 -m venv .venv
```

Activate the env:
```bash
source .venv/bin/activate
```

Install required libraries:
```bash
pip install -U pip
pip install -r requirements.txt
```

## How to install the Slack Stats app in your organization
* Use [manifest.yml](manifest.yml) and upload it to the Slack.
* Authorize the app and retrieve the access token
* Store the access token in `SLACK_BOT_TOKEN` environment variable: `export SLACK_BOT_TOKEN="xoxb-XYZ"`


## Run

```bash
source .venv/bin/activate
export SLACK_BOT_TOKEN="xoxb-XYZ"
python main.py --help
```
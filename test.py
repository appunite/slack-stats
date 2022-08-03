import sys
import logging
logging.basicConfig(level=logging.DEBUG)
from slack_sdk import WebClient
client = WebClient()
api_response = client.api_test()


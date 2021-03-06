# -*- coding: utf-8 -*-
"""Functions to call when running the function.

This module should contain a function called `run_module`, that is executed
when the module is run with `python -m delphi_sir_complainsalot`.
"""

import sys

from slack import WebClient
from slack.errors import SlackApiError

from delphi_utils import read_params
import covidcast

from .check_source import check_source

def run_module():

    params = read_params()
    meta = covidcast.metadata()

    complaints = []
    for data_source in params["sources"].keys():
        complaints.extend(check_source(data_source, meta, params["sources"], params.get("grace", 0)))

    if len(complaints) > 0:
        for complaint in complaints:
            print(complaint)

        report_complaints(complaints, params)

        sys.exit(1)

def report_complaints(complaints, params):
    """Post complaints to Slack."""
    if not params["slack_token"]:
        print("\b (dry-run)")
        return

    blocks = format_complaints(complaints)

    client = WebClient(token=params["slack_token"])

    try:
        client.chat_postMessage(
            channel=params["channel"],
            blocks=blocks
        )
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]

def format_complaints(complaints):
    """Build a formatted Slack message for posting to the API.

    To find good formatting for blocks, try the block kit builder:
    https://api.slack.com/tools/block-kit-builder

    """

    maintainers = set()
    for c in complaints:
        maintainers.update(c.maintainers)

    blocks = [
	{
	    "type": "section",
	    "text": {
		"type": "mrkdwn",
		"text": "Hi, this is Sir Complains-a-Lot. I need to speak to " +
                        (", ".join("<@{0}>".format(m) for m in maintainers)) + "."
	    }
	}
    ]

    for complaint in complaints:
        blocks.append(
            {
	        "type": "section",
		"text": {
		    "type": "mrkdwn",
		    "text": complaint.to_md()
		}
	    }
        )


    return blocks

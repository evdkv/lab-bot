import os
from urllib.parse import parse_qs, unquote_plus
from flask import Flask, jsonify, request
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from dotenv import load_dotenv

from api.db_utils import db_get_user_events, db_valid_member

# Load environment variables
# load_dotenv('.env')
load_dotenv()

# Setup the WebClient and the SignatureVerifier
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

web_client = WebClient(token=SLACK_BOT_TOKEN)

signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

if SLACK_BOT_TOKEN is None or SLACK_SIGNING_SECRET is None:
  print("Environment variables not set")
else:
  print("Environment variables are set")

# Create a new Flask web server
app = Flask(__name__)

# The route for the Slack events
@app.route('/api/slack/start', methods=['POST'])
def handle_start_slash():
    data = request.get_data().decode('utf-8')
    # parse URL-encoded data
    payload = unquote_plus(data)
  
    if payload.startswith('payload='):
        payload = payload[len('payload='):]
  
    event = parse_qs(payload)
  
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
  
    if event is not None:
        user_id = event['user_id'][0]
        valid, proj = db_valid_member(user_id)

        try:
            web_client.chat_postMessage(
            channel=user_id,
            text=f"Welcome to Robbins Lab Schedule Manager, <@{user_id}>!"
            )

            if valid:
                web_client.chat_postMessage(
                channel=user_id,
                text=f"You are currently a part of {proj} project. \n 📅 You can view your current schedule by going to evdkv.github.io/lab-calendar or typing /summary \n 🤖 To see all bot commands type /commands"
                )
            else:
                web_client.chat_postMessage(
                channel=user_id,
                text=f"Hmmm... It seems like you are not a part of a project yet or you don't need to test participants right now. If you think this is a mistake, reach out to the lab coordinator."
                )

            return "", 200
        except SlackApiError as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "missing_payload"}), 400

@app.route('/api/slack/summary', methods=['POST'])
def handle_summary_slash():
    data = request.get_data().decode('utf-8')
    # parse URL-encoded data
    payload = unquote_plus(data)

    if payload.startswith('payload='):
        payload = payload[len('payload='):]
  
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    
    event = parse_qs(payload)

    if event is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    user_id = event['user_id'][0]
    valid, _ = db_valid_member(user_id)

    try:
        if valid:
            summary = db_get_user_events(user_id)
            if len(summary) == 0:
                summary = "Seems like you don't have any shifts right now. Yay!🎉"
            web_client.chat_postMessage(
            channel=user_id,
            text="Here is your schedule summary:\n" + summary
            )
        else:
            web_client.chat_postMessage(
            channel=user_id,
            text=f"Hmmm... It seems like you are not a part of a project yet or you don't need to test participants right now. If you think this is a mistake, reach out to the lab coordinator."
            )

        return "", 200
    except SlackApiError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/slack/add', methods=['POST'])
def handle_add_slash():
    data = request.get_data().decode('utf-8')
    # parse URL-encoded data
    payload = unquote_plus(data)

    if payload.startswith('payload='):
        payload = payload[len('payload='):]
  
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    
    event = parse_qs(payload)

    if event is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    user_id = event['user_id'][0]
    valid, _ = db_valid_member(user_id)

    try:
        if valid:
            web_client.views_open(trigger_id=event["trigger_id"], view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "My App"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "About the simplest modal you could conceive of :smile:\n\nMaybe <https://api.slack.com/reference/block-kit/interactive-components|*make the modal interactive*> or <https://api.slack.com/surfaces/modals/using#modifying|*learn more advanced modal use cases*>.",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "Psssst this modal was designed using <https://api.slack.com/tools/block-kit-builder|*Block Kit Builder*>",
                            }
                        ],
                    },
                ],
            },
        )
        else:
            web_client.chat_postMessage(
            channel=user_id,
            text=f"Hmmm... It seems like you are not a part of a project yet or you don't need to test participants right now. If you think this is a mistake, reach out to the lab coordinator."
            )

        return "", 200
    except SlackApiError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# if __name__ == "__main__":
#     app.run(port=3000)
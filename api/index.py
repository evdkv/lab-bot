import os, json, time
from urllib.parse import parse_qs, unquote_plus
from flask import Flask, jsonify, request
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from dotenv import load_dotenv
from api.response_utils import get_modal, verify_day_time, get_res_str, determine_effective
from api.db_utils import db_get_user_events, db_valid_member, db_get_user_info, db_add_event
from datetime import datetime

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

def add_slot_request(payload, user_db_info, user_id):
    """
        Recieves payload from the add modal, validates time entries (checks for valid entries and conflicts in the DB)
        Sends the request to the approver and notifies the requester of the successful/unsuccessful submission.
    """
    tbegin = payload['view']['state']['values']['tbegin_select']['time_begin_action']['selected_time']
    tend = payload['view']['state']['values']['tend_select']['time_end_action']['selected_time']
    day = payload['view']['state']['values']['day_select']['weekday_action']['selected_option']['value']
    approver_id = payload['view']['state']['values']['approver_select']['approver_action']['selected_option']['value']
    location = user_db_info['location']
    # Get the day and both time points and verify that
    response, is_valid_time = verify_day_time(tbegin, tend, day, location)
    try:
        if is_valid_time:
            approver_attachment = get_modal("add_req_attachment.json")
            approver_attachment["blocks"][1]["text"]["text"] = f"*Name:* <@{approver_id}>\t *Request:* " \
                                                                f"Add a slot\n*Begin:* {tbegin}\t *End:* {tend}\n *Day:* {day}"
            web_client.chat_postMessage(
                channel=user_id,
                text=response
            )
            web_client.chat_postMessage(
                channel=approver_id,
                text=f"<@{approver_id}>, you just got a new request!",
                attachments=[approver_attachment],
                metadata={"event_type" : "add_req", "event_payload" : {"requester" : user_id, 
                          "type" : "Add a slot", "tbegin" : tbegin, "tend" : tend, "day" : day}}
            )
        else:
            web_client.chat_postMessage(
                channel=user_id,
                text=f"❌ Your request was not submitted due to the following problem: \n{response}"
            )
        return "", 200
    except SlackApiError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def add_slot_approve(payload, user_id):
    """
        Handles approve button on the approver request attachment. If the request is approved, it writes
        the entry into DB along with the effective time and notifies the requester of the outcome.
    """
    try:
        updated_attachment = payload["message"]["attachments"][0]["blocks"][:2]
        updated_attachment.append({"type": "section", "text": {"type": "mrkdwn", 
                                   "text": "✅ *Request has been approved! The requester was notified*"}})
        updated_attachment = [{"color" : "#f2c744", "blocks" : updated_attachment}]
        orig_requester = payload["message"]["metadata"]["event_payload"]["requester"]
        eff_d = determine_effective()
        unixtime = time.mktime(eff_d.timetuple())
        success = db_add_event(payload["message"]["metadata"]["event_payload"], unixtime)
        web_client.chat_update(
            channel=user_id,
            ts=payload["message"]["ts"],
            text=f"Complete! The request has been approved. DB updated: {success}",
            attachments=json.dumps(updated_attachment),
            as_user=True
        )
        if not success:
            web_client.chat_postMessage(
                channel=orig_requester,
                text=f"Your request has been approved, but there was an error with Firebase. " \
                      "Please reach out to the lab coordinator directly."
            )
        else:
            web_client.chat_postMessage(
                channel=orig_requester,
                text=f"🎉 Hi, <@{orig_requester}>, your request has just been approved! " \
                      f"\nEffective starting {datetime.strftime(eff_d, '%d %b %Y')}"
                )

        return "", 200
    except SlackApiError as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


def add_slot_deny(payload, user_id):
    """
        Handles deny button on the approver request attachment. If the request is denied, it
        updates the approver attachment and sends the response information to the requester.
    """
    try:
        updated_attachment = payload["message"]["attachments"][0]["blocks"][:2]
        updated_attachment.append({"type": "section", "text": {"type": "mrkdwn", 
                                    "text": "🛑 *Request has been denied! The requester was notified*"}})
        updated_attachment = [{"color" : "#f2c744", "blocks" : updated_attachment}]
        web_client.chat_update(
            channel=user_id,
            ts=payload["message"]["ts"],
            text=f"Complete! The request has been denied",
            attachments=json.dumps(updated_attachment),
            as_user=True
        )
        orig_requester = payload["message"]["metadata"]["event_payload"]["requester"]
        web_client.chat_postMessage(
            channel=orig_requester,
            text=f"🛑 Hi, <@{orig_requester}>, your request has just been denied. " \
                  "Choose another time or reach out to the approver."
            )
        
        return "", 200
    except SlackApiError as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/slack/start', methods=['POST'])
def handle_start_slash():
    """
        Handles the /start command by validating the user and posting the
        basic membership information. Notifies the user if they are not in
        the DB.
    """
    data = request.get_data().decode('utf-8')
    payload = unquote_plus(data)
  
    if payload.startswith('payload='):
        payload = payload[len('payload='):]
  
    payload = parse_qs(payload)

    # Validate the payload
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    if payload is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    # Get user_id from the payload and validate in the DB
    user_id = payload['user_id'][0]
    valid, proj = db_valid_member(user_id)
    try:
        web_client.chat_postMessage(
        channel=user_id,
        text=f"Welcome to Robbins Lab Schedule Manager, <@{user_id}>!"
        )

        if valid:
            web_client.chat_postMessage(
            channel=user_id,
            text=f"You are currently a part of {proj} project." \
                    "\n 📅 You can view your current schedule by going to evdkv.github.io/lab-calendar " \
                    "or typing /summary \n 🤖 To see all bot commands type /commands"
            )
        else:
            web_client.chat_postMessage(
            channel=user_id,
            text=get_res_str("not valid")
            )

        return "", 200
    except SlackApiError as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/slack/summary', methods=['POST'])
def handle_summary_slash():
    """ 
        Handles the /summary commmand by searching for all user events
        in the DB and returning the summary of their shifts in addition
        to their assigned project and other general information. Validates
        the user as well.
    """
    data = request.get_data().decode('utf-8')
    payload = unquote_plus(data)

    # Validate the payload
    if payload.startswith('payload='):
        payload = payload[len('payload='):]
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    
    event = parse_qs(payload)

    if event is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    # Get user_id from the payload and validate in the DB
    user_id = event['user_id'][0]
    valid, _ = db_valid_member(user_id)

    try:
        if valid:
            # Get the events from DB and post the summary + handle no-event case
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
            text=get_res_str("not valid"))
        return "", 200
    except SlackApiError as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route('/api/slack/add', methods=['POST'])
def handle_add_slash():
    """ 
        Handles the /add-slot commmand by opening the add form request
        modal. Validates the user and notifies the user if they are not 
        in the DB.
    """
    data = request.get_data().decode('utf-8')
    payload = unquote_plus(data)

    # Validate the payload
    if payload.startswith('payload='):
        payload = payload[len('payload='):]
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    
    payload = parse_qs(payload)

    if payload is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    # Get user_id from the payload and validate in the DB
    user_id = payload['user_id'][0]
    valid, _ = db_valid_member(user_id)

    try:
        if valid:
            web_client.views_open(
                trigger_id=payload["trigger_id"][0], 
                view=get_modal("add_modal.json")
                )
        else:
            web_client.chat_postMessage(
            channel=user_id,
            text=get_res_str("not valid")
            )

        return "", 200
    except SlackApiError as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/slack/interactive-endpoint', methods=['POST'])
def handle_interactivity():
    """
        Handles all interactivity in the app like button clicks and form
        submissions.
    """
    data = request.get_data().decode('utf-8')
    payload = unquote_plus(data)

    # Validate the request
    if payload.startswith('payload='):
        payload = payload[len('payload='):]
    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403
    if payload is None:
        return jsonify({"status": "error", "message": "missing_payload"}), 400
    
    # Determine the payload type
    payload = json.loads(payload)
    if payload["type"] == "view_submission":
        user_id = payload["user"]["id"]
        callback = payload['view']['callback_id']
        user_db_info = db_get_user_info(user_id)
    elif payload["type"] == "block_actions":
        user_id = payload["channel"]["id"]
        callback = payload["actions"][0]["value"]

    # Determine the type of interaction and handle it
    if callback == 'add_slot_form':
        return add_slot_request(payload, user_db_info, user_id)
    elif callback == "add_req_approve":
        return add_slot_approve(payload, user_id)
    elif callback == "add_req_deny":
        return add_slot_deny(payload, user_id)
    
    # Return the internal server error if the interaction is unhandled
    return jsonify({"status": "error", "message": "no handlers for this interaction"}), 500
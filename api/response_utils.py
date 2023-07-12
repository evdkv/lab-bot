import json
from datetime import time, timedelta, datetime
from api.db_utils import db_get_day_events

def get_modal(modal_name):
    with open(modal_name, 'r') as f:
        read = json.load(f)
    return read

def get_res_str(msg_type):
    if msg_type == "not valid":
        return "Hmmm... It seems like you are not a part of a project yet or you don't need to test participants right now. If you think this is a mistake, reach out to the lab coordinator."
    elif "summary":
        return ""
        
def verify_day_time(tbegin, tend, day, location):
    b = time(int(tbegin.split(':')[0]), int(tbegin.split(':')[1]))
    e = time(int(tend.split(':')[0]), int(tend.split(':')[1]))
    bdelta = timedelta(hours=b.hour, minutes=b.minute)
    edelta = timedelta(hours=e.hour, minutes=e.minute)
    slot_delta = edelta - bdelta

    # Verify the time slot
    if slot_delta <= timedelta(minutes=0):
        return "Begin and end times are either reversed or equal to each other.", False
    elif slot_delta < timedelta(minutes=45):
        return "The minimum slot length is 45 minutes.", False
    elif bdelta < timedelta(hours=9) or edelta > timedelta(hours=20):
        return "The slot is either too early or too late.", False
    
    # Check for conflicts
    time_list_db = db_get_day_events(day)
    frmt = "%I:%M%p"
    time_list = [[int(datetime.strptime(x[0], frmt).strftime('%H%M')), int(datetime.strptime(x[1], frmt).strftime('%H%M')), x[2]] for x in time_list_db]
    requested_time = [int(b.strftime('%H%M')), int(e.strftime('%H%M'))]
    for event in time_list:
        latest_start = max(event[0], requested_time[0])
        earliest_end = min(event[1], requested_time[1])
        delta = earliest_end - latest_start
        if (delta > 0) and (location == event[2]):
            return "There was a scheduling conflict", False
    return "✅ Great! Your request has been submitted to the approver. Once they approve you, you will get a message.", True

def determine_effective():
    now = datetime.now()
    now_weekday = now.weekday()
    if now_weekday <= 2:
        effective = now + timedelta(days= 7 - now_weekday)
        return effective.replace(hour=0, minute=0)
    elif now_weekday > 2:
        effective = now + timedelta(days= (7 - now_weekday) + 7)
        return effective.replace(hour=0, minute=0)
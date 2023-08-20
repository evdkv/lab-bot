import firebase_admin, random, string, json, os
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime, time

cred = credentials.Certificate(json.loads(os.getenv("GOOGLE_CLOUD_CERT")))
# cred = credentials.Certificate("cloud_cert.json")

firebase_admin.initialize_app(cred)
db = firestore.client()

def randomword(length):
   letters = string.ascii_lowercase
   return ''.join(random.choice(letters) for i in range(length))

def db_valid_member(user_id):
    users_ref = db.collection("users")
    docs = users_ref.stream()

    for doc in docs:
        info = doc.to_dict()
        if (doc.id == user_id) and (info['active'] == True):
            return True, info['project']
    return False, ""

def db_get_user_events(user_id):
    user_full = db.collection("users").document(user_id).get().to_dict()['name']
    text = ""
    for day in ["mon" , "tue", "wed", "thu", "fri", "sat", "sun"]:
        docs = [d.to_dict() for d in db.collection(day).where("name", "==", user_full).stream()]
        if len(docs) != 0:
            text += day + ':'
            for doc in docs:
                text += '\n' + doc['time_begin'] + ' - ' + doc['time_end']
            text += '\n'
    return text
                
def db_get_day_events(day):
    '''Returns an array of time slots and event locations for a specific day sorted by begin time'''
    day_event_ref = db.collection(day)
    docs = day_event_ref.stream()

    time_list = []
    for doc in docs:
        info = doc.to_dict()
        time_list.append([info["time_begin"], info["time_end"], info["location"]])
    return time_list

def db_get_user_info(user_id):
    return db.collection("users").document(user_id).get().to_dict()

def db_add_event(data, effective):
    uinf = db_get_user_info(data["requester"])
    doc_id = randomword(5)
    record = {"name" : uinf["name"], "color" : uinf["color"], "location" : uinf["location"],
              "time_begin" : time.strftime(time(int(data["tbegin"].split(':')[0]), int(data["tbegin"].split(':')[1])), "%I:%M%p"),
              "time_end" : time.strftime(time(int(data["tend"].split(':')[0]), int(data["tend"].split(':')[1])), "%I:%M%p"),
              "day" : data["day"], "effective" : effective}
    db.collection(data["day"]).document(doc_id).set(record)
    return True

def db_add_user():
    pass
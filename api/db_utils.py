import os
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv

cred = credentials.Certificate(json.loads(os.getenv("GOOGLE_CLOUD_CERT")))

firebase_admin.initialize_app(cred)
db = firestore.client()

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
                

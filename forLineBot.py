from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage
import json, requests

from firebase import firebase

import os

from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# connect firestore db
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# line bot token
access_token = os.environ.get("LINEBOT_TOKEN")
secret = os.environ.get("LINEBOT_SECRET")
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(secret)

# connect firebase realtime database
url = os.environ.get("FIREBASE_URL")  # 你的 Firebase Realtime database URL
fdb = firebase.FirebaseApplication(url, None)  # 初始化 Firebase Realtime database


def linebot(request):
    body = request.get_data(as_text=True)

    try:
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)

    except:
        print('error')
    return 'OK'


# Calculate exercise time
def calculate_time(start_time, end_time):
    total_time = end_time - start_time
    return total_time

# return the last one name of firestore document
def firestore_return_doc_name(result):
    for doc in result:
        doc_name = doc.id
    return doc_name


@handler.add(MessageEvent, message=TextMessage)
def handle_message(events):
    message_text = events.message.text
    storage_message = []

    # maybe can put into the environment variables
    user = 'user01'
    data_url = '/user/' + user + '/0/'
    collections_ref = db.collection('users')

    match message_text:
        case 'start_exercise':
            # response to line user
            response = '吱吱好的，開始計時'
            message_time = datetime.now(ZoneInfo('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S")
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # save message and time in realtime db
            storage_message.append({message_text: message_time})
            fdb.put('/user', user, storage_message)

        case 'end_exercise':
            # response = '吱吱收到，結束計時'
            # line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # temp save the message time in dictionary(complete exercise date)
            message_time_str = datetime.now(ZoneInfo('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S")


            # get exercise start time on realtime db and calculate exercise time
            start_time = fdb.get(data_url, 'start_exercise')
            start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            message_time = datetime.strptime(message_time_str, "%Y-%m-%d %H:%M:%S")
            total_time = calculate_time(start_time, message_time)

            # save data in firestore
            data = {'complete_date' : message_time_str, 'exercise_time' : str(total_time)} # variable!!
            collections_ref.document(message_time_str).set(data)

            # get the info of the exercise time
            result = collections_ref.document(message_time_str).get()
            if result.exists:
                complete_date = result.to_dict()['complete_date']
                exercise_time = result.to_dict()['exercise_time']
                response = f"吱！計時結束！恭喜你運動了\n運動時長：\n{exercise_time}\n完成日期：\n{complete_date}\n繼續努力加油 σ`∀´)σ"
                line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

        case 'delete_the_last':
            # response = '要刪除剛剛的紀錄嗎'
            response = '已刪除剛剛的紀錄'
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # order the documents by the last time and get the name of the last document's name to delete the data
            result = collections_ref.order_by('complete_date', direction=firestore.Query.DESCENDING).limit(1).get() #query db and get result
            doc_name = firestore_return_doc_name(result)
            collections_ref.document(doc_name).delete()

        # case '/yes':


        case _:
            response = '知道了~'
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))



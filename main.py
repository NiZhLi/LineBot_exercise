from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage, FlexSendMessage, MemberJoinedEvent
import json, requests

from firebase import firebase

import os

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# connect firestore db
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# line bot token
token = 'z0uEprKun3s+Di70rQEZQ7MF9ijSLklVfJfAc7LElfs6bWUZhaC90uOLmNkBd+mjU4Wtvy2I+RlC5nvQdn9uqwTkATLdp4cknG8V/gP362mCDh+FcirdImx+qFFFF/u1wcWR0kkebJn3Ws0IWtxxMAdB04t89/1O/w1cDnyilFU='  # 你的 Access Token
secret = 'c989db4c0ec147e91c9fa180d424e20a'  # 你的 Channel Secret
line_bot_api = LineBotApi(token)
handler = WebhookHandler(secret)

# connect firebase realtime database
url = 'https://linebot-exersice-1-default-rtdb.firebaseio.com/'  # 你的 Firebase Realtime database URL
fdb = firebase.FirebaseApplication(url, None)  # 初始化 Firebase Realtime database


# firestore dict
user_dic = {
    'exercise_time' : '運動時長',
    'complete_date' : '運動日期'
}


app = Flask(__name__)
@app.route("/", methods=['POST'])


def linebot():
    body = request.get_data(as_text=True)

    try:

        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)

    except:
        print('error')
    return 'OK'


# 當有新成員加入群組( group )或聊天室 ( room )時而 chatbot (官方帳號)已在群組或聊天室時的事件
@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}你好哇，我是運動鼠鼠，我們一起來運動叭~\n對我說「喔~鼠鼠~」就可以知道詳細使用方法喔')
    line_bot_api.reply_message(event.reply_token, message)


@handler.add(MessageEvent, message=TextMessage)
def handle_message(events):
    message_timestamp = events.timestamp // 1000 # mile second to second
    message_time = datetime.fromtimestamp(message_timestamp)
    # message_time = datetime.fromtimestamp(message_timestamp, tz=ZoneInfo('Asia/Taipei'))

    # message_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # message_time_str = datetime.now(ZoneInfo('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S")
    # message_time = datetime.strptime(message_time_str, "%Y-%m-%d %H:%M:%S")
    message_text = events.message.text

    # maybe can put into the environment variables
    user = 'user01'
    data_url = '/user/' + user #realtime database
    collections_ref = db.collection('users')
    firestore_doc_name = 'users'


    match message_text:
        case 'start_exercise':
            # response to line user
            response = '吱吱好的，開始計時'
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # save message and time in realtime db
            storage_message = {message_text: message_timestamp}
            fdb.put('/user', user, storage_message)


        case 'end_exercise':
            # get exercise start time on realtime db and calculate exercise time
            start_time = fdb.get(data_url, 'start_exercise')  # variable!!
            if (start_time == None):
                print('dont have data')

            exercise_timestamp = calculate_time(start_time, message_timestamp)
            exercise_time = timestamp_to_time(exercise_timestamp)
            exercise_time_str = f'{exercise_time[0]}小時 {exercise_time[1]}分 {exercise_time[2]}秒'

            # exercise_time_str = exercise_time.strftime('%Y-%m-%d %H:%M:%S')
            message_time_str = message_time.strftime('%Y-%m-%d %H:%M:%S')

            # calulate exercise point
            exercise_point = calculate_point(exercise_time)

            # response to line user
            response = (f"吱！計時結束！恭喜你運動了\n"
                        f"運動時長：\n"
                        f" {exercise_time_str}\n"
                        f"完成日期：\n"
                        f" {message_time_str}\n"
                        f"獲得點數：\n"
                        f" {exercise_point}\n"
                        f"繼續努力加油 σ`∀´)σ")
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # save data in firestore
            data = {'complete_date': message_time_str,
                    'exercise_timestamp': exercise_timestamp,
                    'exercise_point': exercise_point}  # variable!!
            collections_ref.document(message_time_str).set(data)


        # 也許可以用card圖文訊息搭配callback試試看
        case 'delete_last_msg':
            response = '已刪除剛剛的紀錄'
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))

            # order the documents by the last time and get the name of the last document's name to delete the data
            result = collections_ref.order_by('complete_date', direction=firestore.Query.DESCENDING).limit(1).get() #query db and get result
            doc_name = firestore_return_doc_name(result)
            collections_ref.document(doc_name).delete()

        # case '/yes':

        case 'show_record':
            # read the exercise record and calculate total
            total_point = 0
            total_exercise_timestamp = 0.0
            docs = collections_ref.stream()
            for doc in docs:
                exercise_point = doc.to_dict()['exercise_point']
                exercise_timestamp = doc.to_dict()['exercise_timestamp']
                total_point += exercise_point
                total_exercise_timestamp += exercise_timestamp

            total_point = str(total_point)
            duration = timestamp_to_time(total_exercise_timestamp)
            duration = f'{duration[0]}小時 {duration[1]}分 {duration[2]}秒'
            countdown = str(get_remaining_time(message_time))
            flex_message = create_flex_message(total_point, duration, countdown)
            print(flex_message)
            line_bot_api.reply_message(events.reply_token, flex_message)


        case _:
            response = '知道了~'
            line_bot_api.reply_message(events.reply_token, TextSendMessage(text=response))





# calculate exercise time
def calculate_time(start_time, end_time):
    exercise_time = end_time - start_time
    return exercise_time

# calculate exercise point
def calculate_point(exercise_time):
    # 5mins = 0.5 exercise point, 10mins = 1 exercise point
    hours = exercise_time[0] * 60
    mins = exercise_time[1]

    exercise_point = ((hours / 5) + (mins // 5)) * 0.5
    return exercise_point

# format timestamp to hour, min, sec
def timestamp_to_time(timestamp):
    time_delta = timedelta(seconds=timestamp)  # 轉換成timedelta
    total_sec = time_delta.seconds  # 提取總秒數
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60

    return [hours, minutes, sec]

# coutdown one week
def get_remaining_time(current_time):
    last_days = 7 - current_time.weekday()
    next_monday = current_time + timedelta(days=last_days) # 下周一日期
    next_monday = next_monday.replace(hour=0, minute=0, second=0) # 換成零點
    time_remain = next_monday - current_time

    return time_remain

# return the last one name of firestore document
def firestore_return_doc_name(result):
    for doc in result:
        doc_name = doc.id
    return doc_name

# change variables of record.json
def create_flex_message(point, duration, countdown):
    with open('record.json', 'r', encoding='utf-8') as f:
        flex_message_json = json.load(f)

    # flex_message_json['body']['contents'][1]['contents'][0]['contents'][1]['text'] = rate
    flex_message_json['body']['contents'][1]['contents'][1]['contents'][1]['text'] = point
    flex_message_json['body']['contents'][1]['contents'][2]['contents'][1]['text'] = duration
    flex_message_json['body']['contents'][1]['contents'][3]['contents'][1]['text'] = countdown

    return  FlexSendMessage(alt_text='這是你的運動成果', contents=flex_message_json)





if __name__ == "__main__":
    app.run()

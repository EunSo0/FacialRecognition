# -*- coding: cp949 -*- 

import json
import boto3
from botocore.exceptions import NoCredentialsError
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import amazon_transcribe
import cv2
import numpy as np
from keras.models import model_from_json
from keras.preprocessing import image
from tensorflow.keras.preprocessing.image import img_to_array

# Flask 객체 인스턴스 생성
app = Flask(__name__)

# Amazon S3 정보 - 보안 유지 요망
aws_access_key_id = 'AKIASPKCPSIO5NQDPHE2'
aws_secret_access_key = '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'
aws_region_name='ap-northeast-2'
aws_bucket_name = 'maind-bucket'


# 전역 변수
s3_bucket_path = ''
transcribe_json_path = ''

# Loading JSON model
json_file = open('top_models/fer.json', 'r')
loaded_model_json = json_file.read()
json_file.close()
model = model_from_json(loaded_model_json)

# Loading weights
model.load_weights('top_models/fer.h5')

face_haar_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')


@app.route('/')
def index():
    return render_template('index.html')


# 사용자가 영상을 업로드하는 부분
@app.route('/file_upload', methods=['GET', 'POST']) # 접속하는 url
def file_upload():
    if request.method == 'POST':
        file = request.files['file']
        filename = secure_filename(file.filename)

        try:
            # 파일을 s3에 업로드
            s3 = boto3.client(
                's3',
                aws_access_key_id = aws_access_key_id,
                aws_secret_access_key = aws_secret_access_key
            )
            s3.upload_fileobj(file,aws_bucket_name, filename)
            global s3_bucket_path
            s3_bucket_path = f"s3://{aws_bucket_name}/{filename}"
            return "파일이 S3 버킷에 저장되었습니다"
        except NoCredentialsError:
            return "AWS 자격 증명 정보가 유효하지 않습니다"
        except Exception as e:
            return str(e)
    else:
        return render_template('file_upload.html')


@app.route('/do_transcribe', methods=['GET', 'POST'])
def do_transcribe():
    if request.method == 'POST':
        global s3_bucket_path
        if s3_bucket_path == "":
            return "파일을 업로드해주세요"
        global transcribe_json_path
        transcribe_json_path = amazon_transcribe.transcribe_audio(aws_access_key_id, aws_secret_access_key, s3_bucket_path, aws_bucket_name)
        return "음성 변환이 완료되었습니다"
    else:
        return render_template('do_transcribe.html')


@app.route('/show_result', methods=['GET', 'POST'])
def show_result():
    if request.method == 'POST':
        if s3_bucket_path == "":
            return "파일을 업로드해주세요"
        if transcribe_json_path == "":
            return "파일을 업로드 해주세요"


def perform_emotion_recognition(video_path):
    cap = cv2.VideoCapture(video_path)

    total_emotion_values = np.zeros(8)  # Initialize an array to store total emotion values

    while True:
        ret, img = cap.read()
        if not ret:
            break

        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces_detected = face_haar_cascade.detectMultiScale(gray_img, 1.2, 6)

        for (x, y, w, h) in faces_detected:
            roi_gray = gray_img[y:y + w, x:x + h]
            roi_gray = cv2.resize(roi_gray, (48, 48))
            img_pixels = img_to_array(roi_gray)
            img_pixels = np.expand_dims(img_pixels, axis=0)
            img_pixels /= 255.0

            predictions = model.predict(img_pixels)
            max_index = int(np.argmax(predictions[0]))

            total_emotion_values += predictions[0]  # Accumulate the emotion values

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    # Calculate the sum of total emotion values
    total_sum = np.sum(total_emotion_values)

    # Calculate the emotion ratios
    emotion_ratios = total_emotion_values / total_sum

    # Create a dictionary of emotion values
    emotion_values = {}
    emotions = ['neutral', 'happiness', 'surprise', 'sadness', 'anger', 'disgust', 'fear', 'contempt']
    for emotion, ratio in zip(emotions, emotion_ratios):
        emotion_values[emotion] = ratio

    return emotion_values


@app.route('/emotion_recognition', methods=['GET', 'POST'])
def emotion_recognition():
    if request.method == 'POST':
        global s3_bucket_path
        if s3_bucket_path == "":
            return "파일을 업로드해주세요"

        emotion_values = perform_emotion_recognition(s3_bucket_path)
        return render_template('emotion_recognition.html', emotion_values=emotion_values)

    else:
        return render_template('emotion_recognition.html', emotion_values={})




if __name__ == "__main__":
    app.run(debug=True)
    # host 등을 직접 지정하고 싶다면
    # app.run(host="127.0.0.1", port="5000", debug=True)
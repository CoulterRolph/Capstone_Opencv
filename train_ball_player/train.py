# training python code for ping pong bot
from ultralytics import YOLO
import cv2 as cv

print(cv.__version__)

model = YOLO("yolov8n-pose.pt")
model.train(data="C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\train_table\\data.yaml", epochs=100, imgsz=640, batch=16)

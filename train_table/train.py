# training python code for ping pong bot
from ultralytics import YOLO
import cv2 as cv

print(cv.__version__)

## model = YOLO("yolo26n-pose.pt")
## model.train(data="C:\\Users\\melon\\OneDrive\\Desktop\\OpenCV\\train_table\\data.yaml", epochs=100, imgsz=640, batch=32)


model = YOLO("yolo26n-pose.pt")  # or whatever pose checkpoint you're using

model.train(
    data="C:\\Users\\melon\\OneDrive\\Desktop\\OpenCV\\train_table\\data.yaml",
    epochs=300,
    patience=20,          # early stopping
    imgsz=640,
    batch=-1,             # autobatch
    ## device=0,             # GPU 0 (change if needed)
    workers=2,            # Windows-safe start; raise if stable
    cache=True,
    amp=True,
    optimizer="auto",
    cos_lr=True,
    close_mosaic=10,
    project="train_table",
    name="y26n_pose_640"
)
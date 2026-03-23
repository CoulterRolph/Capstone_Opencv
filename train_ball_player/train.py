from ultralytics import YOLO
import cv2 as cv

model = YOLO("yolo26n.pt")  # or whatever pose checkpoint you're using

model.train(
    data="C:\\Users\\melon\\OneDrive\\Desktop\\OpenCV\\train_ball_player\\data.yaml",
    epochs=300,
    save=True,
    save_period=20,   # save a checkpoint every 10 epochs
    patience=75,         # early stopping
    imgsz=640,
    batch=30,             # -1 autobatch
    ## device=0,          # GPU 0 (change if needed)
    workers=4,            # Windows-safe start; raise if stable
    cache=True,
    amp=True,
    optimizer="auto",
    cos_lr=True,
    close_mosaic=10,
    project="train_table",
    name="y26n_ball_player"
)
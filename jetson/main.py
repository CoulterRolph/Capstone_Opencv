# main.py 

# dependancies:
#import ultralytics
#import cv2 as cv
#import tkinter as tk
#import numpy as np

# libraries
from classes.objects import img_point, player, table
from imaging import video
from imaging import table

VIDEO_PATH = r"C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\raw_videos\\tcube_20260304_012.mp4"  

print("\nMAIN STARTED\n")

def main():

    print("\n|===========================================|\n")
    print("Welcome to tcubed!")
    print("\n|===========================================|\n")

    loaded = table.load_table_model()
    if not loaded:
        print("Failed to load the table model. Exiting.")
        return

    print("\n|===========================================|\n")
    print("Openning the video!")
    print("\n|===========================================|\n")

    #open the video 
    cap = video.open_video(VIDEO_PATH)
    if cap is None:
        print("Failed to open video.")

    ret, frame = cap.read()
    # Exit if the frame could not be read.
    if not ret:
        print("Failed to read frame from video.")
        cap.release()
        return
    else:
        print("Successfully read a frame from the video.")

    # collect 10 frames, but stop after 240 frames if not enough are found
    table_frames = table.collect_table_frames(cap, 10, 240) 
    print(f"Collected {len(table_frames)} valid table frames.")
    #record the position of the table corners and net position

    #calculate the homography matrix for the table corners and net position



if __name__ == "__main__":
    main()
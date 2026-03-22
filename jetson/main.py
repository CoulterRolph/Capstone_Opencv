# main.py 

# dependancies:
#import ultralytics
#import cv2 as cv
#import tkinter as tk
#import numpy as np

# libraries
from classes.objects import img_point, player, table
from imaging.table_detection import webcam_test
#import opencv.table_detection as table_detection

from test import test_class

MODEL_PATH = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\best_weights\\table_best_003.pt"
INPUT_VIDEO = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\raw_videos\\tcube_20260304_012.mp4"
OUTPUT_VIDEO = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\annotated_videos\\annotatedtcube_20260304_012_table003.mp4"

CAM_INDEX = 0   # try 0 or 1

print("\nMAIN STARTED\n")

def main():

    print("\n|===========================================|\n")
    print("Welcome to tcubed!")
    print("\n|===========================================|\n")

    print("\n|===========================================|\n")
    print("Training will start soon...")
    print("\n|===========================================|\n")

    print("\n|===========================================|\n")
    print("Set the position of the device")
    print("\n|===========================================|\n")

    # open the webcam and show the user how to a guideline on how to set up the machine 

    webcam_test()

if __name__ == "__main__":
    main()
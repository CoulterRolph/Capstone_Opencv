import cv2 as cv
import numpy as np


def open_video(video_path):
    # Create a VideoCapture object that tries to open the video file
    # located at video_path.
    cap = cv.VideoCapture(video_path)

    # Check whether OpenCV successfully opened the file.
    # If not, stop the program and show an error message.
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}") 
        return None
    
    # Read the width of the video frames in pixels.
    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))

    # Read the height of the video frames in pixels.
    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

    # Read the frames-per-second of the video.
    fps = cap.get(cv.CAP_PROP_FPS)

    # Read the total number of frames in the video.
    frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))

    # Print confirmation that the video opened correctly.
    print("Video opened successfully")

    # Print the resolution of the video.
    print(f"Resolution: {width} x {height}")

    # Print the frame rate of the video.
    print(f"FPS: {fps}")

    # Print the total number of frames in the video.
    print(f"Frame count: {frame_count}")

    # Return the opened VideoCapture object so it can be used elsewhere
    # to read frames from the video.
    return cap
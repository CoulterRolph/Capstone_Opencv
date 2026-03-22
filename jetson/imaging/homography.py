# homography.py
# calculate the homography matrix for the table corners and net position
# this will be used to transform the detected keypoints from the camera perspective to a top-down
# perspective of the table

import cv2 as cv
import numpy as np  

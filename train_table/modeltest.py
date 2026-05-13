# Import the time module so timestamps can be used to measure real frame rate.
import time

# Import the Ultralytics YOLO class so the model can be loaded and used for inference.
from ultralytics import YOLO

# Import OpenCV so the webcam can be opened and frames can be displayed.
import cv2 as cv


# Store the file path to the trained table model.
MODEL_PATH = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\best_weights\\table_best_003.pt"

# Store the webcam index to choose which camera device to open.
CAM_INDEX = 1

# Store the target frame width in pixels.
TARGET_WIDTH = 640

# Store the target frame height in pixels.
TARGET_HEIGHT = 420

# Store the target frame rate in frames per second.
TARGET_FPS = 120


# Load the YOLO model from the model file path.
model = YOLO(MODEL_PATH)

# Create a VideoCapture object to open the webcam using DirectShow on Windows.
cap = cv.VideoCapture(CAM_INDEX, cv.CAP_DSHOW)

# Check whether the webcam opened successfully.
# If not, stop the program and show an error message.
if not cap.isOpened():
    raise RuntimeError("Could not open webcam. Try CAM_INDEX = 0 or 1.")


# Ask the camera to use MJPG because many webcams need this format for high FPS modes.
cap.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc(*"MJPG"))

# Ask the camera to use the target frame width in pixels.
cap.set(cv.CAP_PROP_FRAME_WIDTH, TARGET_WIDTH)

# Ask the camera to use the target frame height in pixels.
cap.set(cv.CAP_PROP_FRAME_HEIGHT, TARGET_HEIGHT)

# Ask the camera to use the target frames per second.
cap.set(cv.CAP_PROP_FPS, TARGET_FPS)


# Read back the actual width reported by the camera in pixels.
actual_width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))

# Read back the actual height reported by the camera in pixels.
actual_height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

# Read back the actual FPS reported by the camera driver.
reported_fps = cap.get(cv.CAP_PROP_FPS)

# Print the requested capture settings for comparison.
print(f"Requested: {TARGET_WIDTH} x {TARGET_HEIGHT} @ {TARGET_FPS} FPS")

# Print the actual camera settings reported by OpenCV.
print(f"Reported : {actual_width} x {actual_height} @ {reported_fps:.2f} FPS")


# Store the frame index so progress can be tracked.
frame_i = 0

# Store the start time of the current FPS measurement window in seconds.
window_start_time = time.time()

# Store how many frames have been read inside the current time window.
window_frame_count = 0


# Start an infinite loop to continuously capture webcam frames.
while True:
    # Read one frame from the camera.
    ret, frame = cap.read()

    # Stop the loop if the frame could not be read.
    if not ret:
        break

    # Increase the total frame counter by one.
    frame_i += 1

    # Increase the frame counter for the current measurement window by one.
    window_frame_count += 1

    # Read the current time in seconds.
    current_time = time.time()

    # Compute how much time has passed since the current measurement window started.
    elapsed = current_time - window_start_time

    # Once about one second has passed, compute and print the measured FPS.
    if elapsed >= 1.0:
        # Compute the measured frame rate as frames divided by seconds.
        measured_fps = window_frame_count / elapsed

        # Print the measured frame rate from the live capture loop.
        print(f"Measured FPS: {measured_fps:.2f}")

        # Reset the window start time so the next one-second measurement can begin.
        window_start_time = current_time

        # Reset the window frame counter for the next measurement interval.
        window_frame_count = 0

    # Run YOLO inference on the current frame.
    # results = model(frame, imgsz=640, conf=0.25, verbose=False)

    # Draw the detections and keypoints on the frame for display.
    #annotated = results[0].plot()

    # Show the annotated frame in a window.
    cv.imshow("YOLO Webcam", frame)

    # Check whether the q key was pressed.
    # If so, stop the loop.
    if cv.waitKey(1) & 0xFF == ord("q"):
        break


# Release the webcam so it is properly closed.
cap.release()

# Close all OpenCV windows before the program exits.
cv.destroyAllWindows()
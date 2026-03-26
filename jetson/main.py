# main.py 

# dependancies:
#import ultralytics
import cv2 as cv
#import tkinter as tk
import numpy as np
from pathlib import Path

# libraries
from classes.objects import img_point, player, table
from imaging import homography, heatmap, table, ball, video   

VIDEO_PATH = r"C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\raw_videos\\tcube_20260304_012.mp4"  
BALL_MODEL_PATH = r"C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\jetson\\models\\ball_player_detect.pt"
RECORD = True  # Set to True to save the processed video with annotations, or False to skip saving.

def main():

    # Print a banner so it is obvious that the program has started.
    print("\n|===========================================|\n")
    print("Welcome to tcubed!")
    print("\n|===========================================|\n")

    # Load the table model before starting any video processing.
    loaded = table.load_table_model()

    # Stop the program if the table model failed to load.
    if not loaded:
        # Print an error message so it is clear why the program stopped.
        print("Failed to load the table model. Exiting.")
        return

    # Load the ball model inside a try block because model loading can raise an exception.
    try:
        # Load the YOLO ball model from the configured model path.
        ball_model = ball.load_model(BALL_MODEL_PATH)

    # Handle any model-loading error cleanly.
    except Exception as e:
        # Print the error so it is easier to debug model-loading problems.
        print(f"Failed to load the ball model. Exiting.\nError: {e}")
        return

    # Create the ball tracking state so ball positions and bounce points can persist across frames.
    ball_state = ball.create_state()

    # Create the heatmap state so mapped bounce points can persist across frames.
    heatmap_state = heatmap.create_state()

    # Print a message so it is clear that the program is about to open the video.
    print("\n|===========================================|\n")
    print("Opening the video!")
    print("\n|===========================================|\n")

    # Open the video file using your video helper function.
    cap = video.open_video(VIDEO_PATH)

    # Stop the program if the video could not be opened.
    if cap is None:
        # Print an error message so it is clear why the program stopped.
        print("Failed to open video.")
        return

    # Create a variable that will later hold the output video writer if recording is enabled.
    writer = None

    # Wrap the rest of the program in a try/finally block so resources are always released.
    try:
        # Read the frames-per-second value from the input video.
        fps = cap.get(cv.CAP_PROP_FPS)

        # Use a safe fallback fps if the video file reports an invalid value.
        if fps <= 0:
            # Store a default fps value in frames per second.
            fps = 30.0

        # Read the first frame from the video.
        ret, frame = cap.read()

        # Stop if the first frame could not be read.
        if not ret:
            # Print an error message so it is clear why the program stopped.
            print("Failed to read frame from video.")
            return

        # Print confirmation that the first frame was read successfully.
        print("Successfully read a frame from the video.")

        # Collect table keypoints from the video so the table can be estimated.
        table_keypoints = table.collect_table_keypoints(cap, 5, 120)

        # Build the table object from the detected keypoints.
        detected_table = table.build_table_from_keypoints(table_keypoints)

        # Print the detected table object so you can inspect the result.
        print("\nDetected table:")
        print(detected_table)

        # Compute the homography using the detected table.
        H, src_points, dst_points, output_size = homography.compute_table_homography(
            detected_table,
            output_width=1200,
        )

        # Print the homography matrix so you can confirm it was computed.
        print("\nHomography matrix:")
        print(H)

        # Print the source points so you can inspect the image-space corners.
        print("\nSource points:")
        print(src_points)

        # Print the destination points so you can inspect the table-space corners.
        print("\nDestination points:")
        print(dst_points)

        # Print the output size so you know the homography destination resolution.
        print("\nOutput size:")
        print(output_size)

        # Rewind the video because table keypoint collection advanced the capture position.
        cap.set(cv.CAP_PROP_POS_FRAMES, 0)

        # If recording is enabled, prepare the output video writer now.
        if RECORD:
            # Create a Path object for the original input video path.
            input_path = Path(VIDEO_PATH)

            # Build the processed output path by adding "_PROCESSED" before the file extension.
            output_path = input_path.with_name(f"{input_path.stem}_PROCESSED{input_path.suffix}")

            # Read the width of the output video frames in pixels from the first frame.
            frame_width = frame.shape[1]

            # Read the height of the output video frames in pixels from the first frame.
            frame_height = frame.shape[0]

            # Create the four-character codec code for writing an MP4-compatible video.
            fourcc = cv.VideoWriter_fourcc(*"mp4v")

            # Create the video writer using the processed filename, codec, fps, and frame size.
            writer = cv.VideoWriter(
                str(output_path),
                fourcc,
                fps,
                (frame_width, frame_height),
            )

            # Check whether the writer opened correctly.
            if not writer.isOpened():
                # Print an error and stop recording if the writer failed to open.
                print(f"Failed to open output video for writing: {output_path}")
                writer = None

            # Print the output path so you know where the processed video will be saved.
            else:
                print(f"Recording enabled. Saving annotated video to: {output_path}")

        # Print a message so it is clear that frame-by-frame processing is starting.
        print("\n|===========================================|\n")
        print("Starting ball tracking...")
        print("\n|===========================================|\n")

        # Process the video one frame at a time until it ends or the user quits.
        while True:
            # Read the next frame from the video.
            ret, frame = cap.read()

            # Stop if the video ended or if a frame could not be read.
            if not ret:
                # Print a message so it is clear why the loop ended.
                print("End of video or failed to read frame.")
                break

            # Process the current frame for ball tracking.
            ball_output = ball.process_frame(frame, ball_model, ball_state)

            # Draw the ball overlay on a copy of the frame so the original frame stays unchanged.
            annotated_frame = ball.draw_overlay(frame.copy(), ball_output, ball_state)

            # Read the newest bounce-point candidate from the ball output dictionary.
            bounce_point = ball_output["bounce_point"]

            # If a new bounce point was found, map and store it in the heatmap state.
            if bounce_point is not None:
                # Print the image-space bounce point so you can inspect it in the terminal.
                print(f"Bounce-point candidate detected: {bounce_point}")

                # Map the bounce point into table coordinates and store it.
                mapped_point = heatmap.add_bounce_point(
                    state=heatmap_state,
                    bounce_point=bounce_point,
                    H=H,
                    output_size=output_size,
                )

                # Print the mapped point if it landed inside the table.
                if mapped_point is not None:
                    # Print the table-space mapped bounce point for debugging.
                    print(f"Mapped bounce point on table: {mapped_point}")

            # Draw the top-right table overlay and mapped bounce points onto the annotated frame.
            annotated_frame = heatmap.draw_overlay(
                frame=annotated_frame,
                state=heatmap_state,
                output_size=output_size,
                overlay_height=260,
                margin=20,
            )

            # If recording is enabled and the writer exists, save the annotated frame.
            if RECORD and writer is not None:
                # Write the annotated frame into the processed output video.
                writer.write(annotated_frame)

            # Show the annotated frame in an OpenCV window.
            cv.imshow("tcubed - Ball Tracking", annotated_frame)

            # Read one keyboard key so the user can quit early.
            key = cv.waitKey(1) & 0xFF

            # Stop early if the user presses the q key.
            if key == ord("q"):
                # Print a message so it is clear why the loop ended.
                print("Stopping early: user pressed q.")
                break

    # Always release resources, even if an error happens.
    finally:
        # Release the input video capture if it was opened.
        cap.release()

        # Release the output writer if recording was enabled and the writer was created.
        if writer is not None:
            writer.release()

        # Close all OpenCV windows so the program exits cleanly.
        cv.destroyAllWindows()

if __name__ == "__main__":
    main()
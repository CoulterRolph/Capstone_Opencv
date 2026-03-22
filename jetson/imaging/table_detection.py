# table_detection.py
# the purpose of this file is to detect the table and report its corners 
from pathlib import Path
import cv2 as cv
import numpy as np
from ultralytics import YOLO

TABLE_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "table_keypoints.pt"


def webcam_test():

    frame_i = 0
    PRINT_EVERY = 10  # print once every N frames
    model = YOLO(str(TABLE_MODEL_PATH))
    cap = cv.VideoCapture(1)

    if not cap.isOpened():
            raise RuntimeError("Could not open webcam.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read frame from webcam.")
                break

            # Run inference (tune conf/imgsz for speed vs accuracy)
            results = model(frame, imgsz=640, conf=0.25, verbose=False)

            r = results[0]  # first (and only) image in batch

            # r.keypoints is None if nothing detected
            if r.keypoints is not None and len(r.keypoints) > 0:
                # Shapes:
                # xy:   (num_instances, num_kpts, 2)
                # conf: (num_instances, num_kpts)
                xy = r.keypoints.xy.cpu().numpy()
                kc = r.keypoints.conf.cpu().numpy()

                if frame_i % PRINT_EVERY == 0:
                    for inst_idx in range(xy.shape[0]):
                        print(f"\nFrame {frame_i} | instance {inst_idx}")
                        for kpt_idx in range(xy.shape[1]):
                            x, y = xy[inst_idx, kpt_idx]
                            conf = kc[inst_idx, kpt_idx]
                            print(f"  kpt {kpt_idx}: x={x:.1f}, y={y:.1f}, conf={conf:.3f}")


                # Draw boxes/keypoints on the frame
            annotated = results[0].plot()

            cv.imshow("YOLO Webcam", annotated)

            if cv.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv.destroyAllWindows()
    


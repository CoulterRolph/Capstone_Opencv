from ultralytics import YOLO
import cv2

# ----------------------------
# USER SETTINGS
# ----------------------------
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"
SOURCE = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
BALL_CLASS_NAME = "ball"   # Only this class will be drawn
CONFIDENCE_THRESHOLD = 0.25

# ----------------------------
# LOAD MODEL
# ----------------------------
model = YOLO(MODEL_PATH)

# ----------------------------
# OPEN VIDEO SOURCE
# ----------------------------
cap = cv2.VideoCapture(SOURCE)

if not cap.isOpened():
    print("Error: Could not open video source.")
    exit()

print("Press 'q' to quit.")

# ----------------------------
# MAIN LOOP
# ----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of stream or failed to grab frame.")
        break

    # Run YOLO tracking on current frame
    results = model.track(
        source=frame,
        persist=True,
        conf=CONFIDENCE_THRESHOLD,
        verbose=False
    )

    # Get first result since we're passing one frame at a time
    result = results[0]

    # Make a copy for drawing
    display_frame = frame.copy()

    # Check if any boxes were detected
    if result.boxes is not None:
        boxes = result.boxes

        for box in boxes:
            # Class ID
            cls_id = int(box.cls[0].item())
            class_name = model.names[cls_id]

            # Only draw the "ball" class
            if class_name != BALL_CLASS_NAME:
                continue

            # Confidence
            conf = float(box.conf[0].item())

            # Bounding box coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            # Tracking ID if available
            track_id = None
            if box.id is not None:
                track_id = int(box.id[0].item())

            # Draw rectangle
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Label text
            if track_id is not None:
                label = f"{class_name} ID:{track_id} {conf:.2f}"
            else:
                label = f"{class_name} {conf:.2f}"

            # Draw label background
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(display_frame, (x1, y1 - 25), (x1 + text_w + 8, y1), (0, 255, 0), -1)

            # Draw label text
            cv2.putText(
                display_frame,
                label,
                (x1 + 4, y1 - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

    # Show frame
    cv2.imshow("Ping Pong Ball Tracking", display_frame)

    # Quit on q
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# ----------------------------
# CLEANUP
# ----------------------------
cap.release()
cv2.destroyAllWindows()
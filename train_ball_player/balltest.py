from ultralytics import YOLO
import cv2 as cv

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\best_weights\\ball_player_best_001.pt"   # change this
SOURCE = 0                                 # 0 for webcam, or put video path like r"C:\path\to\video.mp4"
CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# =========================
# LOAD MODEL
# =========================
model = YOLO(MODEL_PATH)

# =========================
# OPEN VIDEO SOURCE
# =========================
cap = cv.VideoCapture(SOURCE)

if not cap.isOpened():
    raise RuntimeError(f"Could not open source: {SOURCE}")

print("Press 'q' to quit.\n")

# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or failed to read frame.")
        break

    # Run inference
    results = model(frame, imgsz=IMG_SIZE, conf=CONF_THRESHOLD, verbose=False)

    # Get first result (one frame)
    result = results[0]

    # If detections exist
    if result.boxes is not None and len(result.boxes) > 0:
        for i, box in enumerate(result.boxes):
            # Bounding box coordinates
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            class_name = model.names[cls_id]

            # Compute center point
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)

            # Print detection info to terminal
            print(
                f"Detected: {class_name} | "
                f"x={center_x}, y={center_y} | "
                f"confidence={conf:.3f}"
            )

            # Draw bounding box
            cv.rectangle(
                frame,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                (0, 255, 0),
                2
            )

            # Draw center point
            cv.circle(frame, (center_x, center_y), 4, (0, 0, 255), -1)

            # Label text
            label = f"{class_name} {conf:.2f} | x={center_x}, y={center_y}"
            cv.putText(
                frame,
                label,
                (int(x1), int(y1) - 10),
                cv.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

    # Show frame
    cv.imshow("Detection", frame)

    # Quit on q
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()
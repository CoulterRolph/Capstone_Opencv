from ultralytics import YOLO
import cv2 as cv

MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"   # Change Path Base on .pt Location 
SOURCE = 0
VIDEO = "C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# Load model
model = YOLO(MODEL_PATH, task="detect")

# Get class ID for "ball"
ball_class_id = [k for k, v in model.names.items() if v == "ball"][0]

cap = cv.VideoCapture(VIDEO)
# cap = cv.VideoCapture(SOURCE)

print("Press 'q' to quit.\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run detection ONLY for ball
    results = model(
        frame,
        imgsz=IMG_SIZE,
        conf=CONF_THRESHOLD,
        classes=[ball_class_id],
        verbose=False
    )

    result = results[0]

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes

        # 🔥 pick highest confidence detection
        best_idx = boxes.conf.argmax()
        best_box = boxes[best_idx]

        x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
        conf = float(best_box.conf[0].cpu().numpy())

        # center point
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        # print info
        print(f"ball | x={cx}, y={cy} | confidence={conf:.3f}")

        # draw box
        cv.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

        # draw center
        cv.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        # label
        cv.putText(
            frame,
            f"ball {conf:.2f}",
            (int(x1), int(y1) - 10),
            cv.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

    cv.imshow("Ball Tracking", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv.destroyAllWindows()
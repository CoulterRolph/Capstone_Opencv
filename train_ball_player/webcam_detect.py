from pathlib import Path

import cv2 as cv
from ultralytics import YOLO


TARGET_CLASS = "orange"

MODEL_CANDIDATES = [
    Path(__file__).resolve().parent / "yolo26n.pt",
    Path(__file__).resolve().parent.parent / "yolo26n.pt",
]


def find_model_path():
    for model_path in MODEL_CANDIDATES:
        if model_path.exists():
            return model_path
    searched = "\n".join(str(path) for path in MODEL_CANDIDATES)
    raise FileNotFoundError(
        f"Could not find yolo26n.pt. Checked:\n{searched}"
    )


def main():
    model = YOLO("yolo26n.pt")
    cap = cv.VideoCapture(1)

    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read frame from webcam.")
                break

            result = model(frame, verbose=False)[0]

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = str(model.names[cls_id]).lower()

                if class_name != TARGET_CLASS:
                    continue

                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                label = f"{class_name} {conf:.2f}"

                print(f"{class_name}: x={center_x}, y={center_y}, conf={conf:.2f}")

                cv.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv.putText(
                    frame,
                    label,
                    (x1, max(20, y1 - 10)),
                    cv.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv.LINE_AA,
                )
                cv.circle(frame, (center_x, center_y), 4, (0, 255, 0), -1)

            cv.imshow("train_ball_player webcam", frame)

            if cv.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv.destroyAllWindows()


if __name__ == "__main__":
    main()

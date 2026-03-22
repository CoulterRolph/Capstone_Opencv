from ultralytics import YOLO
import cv2 as cv
import os
import time

# =========================
# CHANGE ONLY THESE PATHS
# =========================
MODEL_PATH = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\best_weights\\table_best_003.pt"
INPUT_VIDEO = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\raw_videos\\tcube_20260304_012.mp4"
OUTPUT_VIDEO = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\annotated_videos\\annotatedtcube_20260304_012_table003.mp4"

# Inference settings
IMGSZ = 640
CONF_THRES = 0.25

# Optional keypoint names
# Replace these with your actual table keypoint names if you want
KEYPOINT_NAMES = [
    "NearLeft_Corner",
    "NearRight_Corner",
    "FarLeft_Corner",
    "FarRight_Corner",
    "Left_Net",
    "Right_Net"
]

# Minimum confidence to draw a keypoint label
KPT_DRAW_THRES = 0.05


def main():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not os.path.exists(INPUT_VIDEO):
        raise FileNotFoundError(f"Input video not found: {INPUT_VIDEO}")

    model = YOLO(MODEL_PATH)

    cap = cv.VideoCapture(INPUT_VIDEO)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {INPUT_VIDEO}")

    fps = cap.get(cv.CAP_PROP_FPS)
    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30.0

    fourcc = cv.VideoWriter_fourcc(*"mp4v")
    out = cv.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (width, height))
    if not out.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open output video for writing: {OUTPUT_VIDEO}")

    frame_i = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # -------------------------
        # Measure inference time
        # -------------------------
        t0 = time.perf_counter()
        results = model(frame, imgsz=IMGSZ, conf=CONF_THRES, verbose=False)
        t1 = time.perf_counter()

        inference_ms = (t1 - t0) * 1000.0
        inference_fps = 1.0 / (t1 - t0) if (t1 - t0) > 0 else 0.0

        r = results[0]
        annotated = r.plot()

        # -------------------------
        # Draw keypoint labels
        # -------------------------
        if r.keypoints is not None and len(r.keypoints) > 0:
            xy = r.keypoints.xy.cpu().numpy()
            kc = r.keypoints.conf.cpu().numpy()

            for inst_idx in range(xy.shape[0]):
                for kpt_idx in range(xy.shape[1]):
                    x, y = xy[inst_idx, kpt_idx]
                    conf = kc[inst_idx, kpt_idx]

                    if conf < KPT_DRAW_THRES:
                        continue

                    x_i, y_i = int(x), int(y)

                    if kpt_idx < len(KEYPOINT_NAMES):
                        kpt_name = KEYPOINT_NAMES[kpt_idx]
                    else:
                        kpt_name = f"kpt_{kpt_idx}"

                    label = f"{kpt_name}: {conf:.2f}"

                    cv.putText(
                        annotated,
                        label,
                        (x_i + 8, y_i - 8),
                        cv.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 255),
                        1,
                        cv.LINE_AA
                    )

        # -------------------------
        # Draw inference stats
        # -------------------------
        cv.putText(
            annotated,
            f"Inference: {inference_ms:.1f} ms",
            (15, 30),
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv.LINE_AA
        )

        cv.putText(
            annotated,
            f"Model FPS: {inference_fps:.1f}",
            (15, 60),
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv.LINE_AA
        )

        out.write(annotated)
        cv.imshow("Annotated Video", annotated)

        if cv.waitKey(1) & 0xFF == ord("q"):
            break

        frame_i += 1
        if frame_i % 30 == 0:
            print(
                f"Processed {frame_i}/{total_frames if total_frames > 0 else '?'} frames | "
                f"Inference: {inference_ms:.1f} ms | FPS: {inference_fps:.1f}"
            )

    cap.release()
    out.release()
    cv.destroyAllWindows()

    print(f"\nDone.")
    print(f"Saved annotated video to:\n{OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()
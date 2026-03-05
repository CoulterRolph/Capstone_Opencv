from ultralytics import YOLO
import cv2 as cv

MODEL_PATH = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\best_weights\\table_best.pt"   # can also be "model.onnx"
CAM_INDEX = 1            # try 0 or 1

model = YOLO(MODEL_PATH)

cap = cv.VideoCapture(CAM_INDEX, cv.CAP_DSHOW)  # CAP_DSHOW helps on Windows
if not cap.isOpened():
    raise RuntimeError("Could not open webcam. Try CAM_INDEX=0 or 1.")

# Optional: request a resolution/FPS (may be ignored by webcam)
cap.set(cv.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv.CAP_PROP_FPS, 60)

frame_i = 0
PRINT_EVERY = 10  # print once every N frames

while True:
    ret, frame = cap.read()
    if not ret:
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

cap.release()
cv.destroyAllWindows()

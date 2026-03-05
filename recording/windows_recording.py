#Using webcam to record video and save it to a file
import cv2 as cv
from datetime import datetime

OUTDIR = "C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\recording"
ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
filename = OUTDIR + f"\\session_{ts}.mp4"

cap = cv.VideoCapture(1, cv.CAP_DSHOW)
cap.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv.CAP_PROP_FPS, 60)

ret, frame = cap.read()
if not ret:
    raise RuntimeError("Could not read from camera.")

h, w = frame.shape[:2]

fourcc = cv.VideoWriter_fourcc(*"mp4v")
out = cv.VideoWriter(str(filename), fourcc, 60.0, (w, h))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    out.write(frame)
    cv.imshow("RAW", frame)

    if cv.waitKey(1) & 0xFF == ord('q'):
        break

out.release()
cap.release()
cv.destroyAllWindows()

print("Saved to:", filename)
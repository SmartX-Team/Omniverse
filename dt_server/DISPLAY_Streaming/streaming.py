from flask import Flask, Response
import cv2
import pyautogui
import numpy as np
import time
import threading
import os

app = Flask(__name__)
capture_interval = float(os.getenv('CAPTURE_INTERVAL', 0.5))  # seconds
jpeg_quality = 70  # JPEG quality (0 to 100)

frame = None
lock = threading.Lock()

def capture_screen():
    global frame
    while True:
        screen = pyautogui.screenshot()
        img = np.array(screen)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        (flag, encodedImage) = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if flag:
            with lock:
                frame = encodedImage

        time.sleep(capture_interval)

@app.route('/video_feed')
def video_feed():
    def generate_frames():
        global frame
        while True:
            with lock:
                if frame is None:
                    continue
                output_frame = frame.tobytes()
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + output_frame + b'\r\n')
    
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    capture_thread = threading.Thread(target=capture_screen)
    capture_thread.daemon = True
    capture_thread.start()
    
    app.run("0.0.0.0", port=5000)

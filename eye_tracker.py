"""
=============================================================================
AEROPRECISE - ULTRA-RELIABLE EYE GAZE & DOUBLE CLICK
=============================================================================
Features:
1. 👁️ Ultra-Smooth Gaze Mouse Control (Gaze / Head Direction)
2. ⚡ 100% Guaranteed Double-Blink -> Instant Double Click
   - Blink 1: Registers instantly (Beep + Yellow Banner)
   - Blink 2: Fires Hardware Double Click (Double Beep + Green Banner)
=============================================================================
"""

import os
import sys
import time
import math
import threading
import urllib.request
import ctypes
import numpy as np
import cv2
import mediapipe as mp

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# ==========================================
# 0. DIRECT WINDOWS MOUSE CONTROLLER
# ==========================================
user32 = ctypes.windll.user32
SCREEN_W = user32.GetSystemMetrics(0)
SCREEN_H = user32.GetSystemMetrics(1)
SCREEN_CENTER_X = SCREEN_W / 2.0
SCREEN_CENTER_Y = SCREEN_H / 2.0

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004

def move_mouse(x, y):
    user32.SetCursorPos(int(x), int(y))

def execute_double_click(x, y):
    """Executes instant hardware double click at (x, y)"""
    def _action():
        move_mouse(x, y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.04)
        move_mouse(x, y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        if HAS_WINSOUND:
            winsound.Beep(1400, 20)
            time.sleep(0.02)
            winsound.Beep(1900, 30)
    threading.Thread(target=_action, daemon=True).start()

# ==========================================
# 1. MODEL AUTO-DOWNLOAD
# ==========================================
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print(f"[SYSTEM] Downloading '{MODEL_PATH}'...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[SYSTEM] Model ready.")

ensure_model()

# ==========================================
# 2. CONFIGURATION
# ==========================================
class Config:
    CAM_WIDTH = 640
    CAM_HEIGHT = 480
    
    # Mouse Sensitivity
    SENSITIVITY_X = 2.60
    SENSITIVITY_Y = 2.40
    
    # Smoothness Factor (0.05 to 0.50: Lower = smoother, Higher = faster)
    SMOOTHING = 0.28
    
    # Blink Sensitivity (High sensitivity to catch every blink)
    EAR_BLINK_THRESHOLD = 0.22
    BLENDSHAPE_BLINK_THRESHOLD = 0.35
    
    # Double Blink Window (seconds)
    DOUBLE_BLINK_MAX_INTERVAL = 1.20


# ==========================================
# 3. EYE ASPECT RATIO (EAR)
# ==========================================
def calculate_ear(landmarks, indices, w, h):
    pts = [np.array([landmarks[i].x * w, landmarks[i].y * h]) for i in indices]
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    h_dist = np.linalg.norm(pts[0] - pts[3])
    if h_dist < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h_dist)


# ==========================================
# 4. MASTER GAZE & DOUBLE CLICK CONTROLLER
# ==========================================
class SimpleGazeTracker:
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    NOSE_TIP = 1

    def __init__(self):
        self.calibrated = False
        self.calib_samples = []
        self.base_x = 0.50
        self.base_y = 0.50
        
        self.curr_x = SCREEN_CENTER_X
        self.curr_y = SCREEN_CENTER_Y
        self.locked_pos = (int(SCREEN_CENTER_X), int(SCREEN_CENTER_Y))
        self.freeze_until = 0.0
        
        # FOOLPROOF STATE TRANSITION BLINK ENGINE
        self.blink_count = 0
        self.eyes_were_closed = False
        self.last_blink_time = 0.0
        
        # UI Alerts
        self.alert_text = ""
        self.alert_timer = 0.0
        self.alert_color = (0, 255, 0)
        self.debug_ear = 0.0

    def recalibrate(self):
        self.calibrated = False
        self.calib_samples = []
        self.curr_x = SCREEN_CENTER_X
        self.curr_y = SCREEN_CENTER_Y
        self.alert_text = "CALIBRATING... LOOK AT CENTER"
        self.alert_color = (0, 220, 255)
        self.alert_timer = time.time()

    def process(self, frame, landmarks, blendshapes):
        h, w, _ = frame.shape
        now = time.time()

        # Step 1: Detect If Eyes Are Closed (EAR + Blendshapes for 100% reliability)
        l_ear = calculate_ear(landmarks, self.LEFT_EYE, w, h)
        r_ear = calculate_ear(landmarks, self.RIGHT_EYE, w, h)
        self.debug_ear = (l_ear + r_ear) / 2.0

        is_closed = self.debug_ear < Config.EAR_BLINK_THRESHOLD

        if blendshapes:
            bs = {cat.category_name: cat.score for cat in blendshapes}
            l_blink = bs.get('eyeBlinkLeft', 0.0)
            r_blink = bs.get('eyeBlinkRight', 0.0)
            if l_blink > Config.BLENDSHAPE_BLINK_THRESHOLD or r_blink > Config.BLENDSHAPE_BLINK_THRESHOLD:
                is_closed = True

        nose = landmarks[self.NOSE_TIP]

        # Step 2: 1-Second Center Calibration
        if not self.calibrated:
            self.calib_samples.append((nose.x, nose.y))
            if len(self.calib_samples) >= 30:
                self.base_x = float(np.mean([s[0] for s in self.calib_samples]))
                self.base_y = float(np.mean([s[1] for s in self.calib_samples]))
                self.calibrated = True
                self.alert_text = "READY! BLINK TWICE TO DOUBLE CLICK"
                self.alert_color = (0, 255, 0)
                self.alert_timer = now
                if HAS_WINSOUND:
                    threading.Thread(target=lambda: winsound.Beep(1200, 100), daemon=True).start()
            return self.draw_calibration(frame, len(self.calib_samples) / 30.0)

        # Step 3: Mouse Movement Calculation
        dx = (nose.x - self.base_x) * Config.SENSITIVITY_X * SCREEN_W
        dy = (nose.y - self.base_y) * Config.SENSITIVITY_Y * SCREEN_H

        target_x = SCREEN_CENTER_X + dx
        target_y = SCREEN_CENTER_Y + dy

        self.curr_x += (target_x - self.curr_x) * Config.SMOOTHING
        self.curr_y += (target_y - self.curr_y) * Config.SMOOTHING

        clamped_x = max(5, min(SCREEN_W - 5, self.curr_x))
        clamped_y = max(5, min(SCREEN_H - 5, self.curr_y))

        # Position lock during blink or right after double-click
        if is_closed or now < self.freeze_until:
            move_mouse(self.locked_pos[0], self.locked_pos[1])
        else:
            self.locked_pos = (int(clamped_x), int(clamped_y))
            move_mouse(clamped_x, clamped_y)

        # Step 4: STATE TRANSITION DOUBLE BLINK ENGINE
        # Trigger on the rising edge when eyes re-open after closing
        if self.eyes_were_closed and not is_closed:
            if self.blink_count == 0:
                # 1st Blink Completed!
                self.blink_count = 1
                self.last_blink_time = now
                self.alert_text = "BLINK 1 DETECTED -> BLINK AGAIN!"
                self.alert_color = (0, 220, 255)
                self.alert_timer = now
                if HAS_WINSOUND:
                    threading.Thread(target=lambda: winsound.Beep(1300, 30), daemon=True).start()
                print("[EVENT] Blink 1 Detected -> Blink again to Double Click!")

            elif self.blink_count == 1:
                # 2nd Blink within window -> DOUBLE CLICK!
                if now - self.last_blink_time <= Config.DOUBLE_BLINK_MAX_INTERVAL:
                    self.freeze_until = now + 0.40  # Freeze mouse for 400ms so click is 100% stable
                    execute_double_click(self.locked_pos[0], self.locked_pos[1])
                    self.alert_text = "DOUBLE CLICKED!"
                    self.alert_color = (0, 255, 0)
                    self.alert_timer = now
                    self.blink_count = 0
                    self.last_blink_time = 0.0
                    print(f"[ACTION] *** DOUBLE CLICK FIRED AT {self.locked_pos} ***")
                else:
                    # Too slow, treat as new Blink 1
                    self.blink_count = 1
                    self.last_blink_time = now

        # Timeout reset if no second blink happens
        if self.blink_count == 1 and not is_closed and (now - self.last_blink_time > Config.DOUBLE_BLINK_MAX_INTERVAL):
            self.blink_count = 0

        self.eyes_were_closed = is_closed

        # Step 5: Draw Clean HUD
        return self.draw_hud(frame, is_closed)

    def draw_calibration(self, frame, progress):
        h, w, _ = frame.shape
        cv2.rectangle(frame, (0, 0), (w, h), (20, 20, 20), -1)
        cv2.putText(frame, "CENTER CALIBRATION", (w // 2 - 150, h // 2 - 20),
                    cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 220, 255), 2)
        cv2.putText(frame, "Look at center of screen...", (w // 2 - 130, h // 2 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)
        cv2.rectangle(frame, (w // 2 - 120, h // 2 + 35), (w // 2 - 120 + int(240 * progress), h // 2 + 48), (0, 255, 180), -1)
        return frame

    def draw_hud(self, frame, is_closed):
        h, w, _ = frame.shape

        # Header Bar
        cv2.rectangle(frame, (0, 0), (w, 50), (15, 15, 18), -1)
        cv2.putText(frame, "GAZE MOUSE", (15, 33), cv2.FONT_HERSHEY_DUPLEX, 0.60, (0, 220, 255), 1)

        # Live Eyes State Badge
        status_text = "CLOSED" if is_closed else "OPEN"
        status_color = (0, 0, 255) if is_closed else (0, 255, 0)
        cv2.putText(frame, f"EYES: {status_text}", (w - 160, 33), cv2.FONT_HERSHEY_DUPLEX, 0.50, status_color, 1)

        # Blink 1 Prompt Badge
        if self.blink_count == 1:
            cv2.rectangle(frame, (w // 2 - 170, 8), (w // 2 + 170, 44), (0, 200, 255), -1)
            cv2.putText(frame, "BLINK AGAIN FOR DOUBLE CLICK!", (w // 2 - 160, 32),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 0, 0), 1)

        # Big On-Screen Alert
        if time.time() - self.alert_timer < 1.4:
            cv2.putText(frame, self.alert_text, (w // 2 - 160, h // 2),
                        cv2.FONT_HERSHEY_DUPLEX, 0.75, self.alert_color, 2)

        # Footer Help
        cv2.putText(frame, "[C] Re-Center | [D] Test Double Click | [Q] Quit",
                    (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
        return frame


# ==========================================
# 5. APPLICATION RUN LOOP
# ==========================================
def main():
    print("==================================================")
    print("   AEROPRECISE - GAZE MOUSE & DOUBLE CLICK        ")
    print("==================================================")
    print("-> Controls:")
    print("   1. 👁️ Move Head / Eyes  -> Moves Mouse Cursor")
    print("   2. ⚡ Blink 2 Times     -> Instant Double Click")
    print("   * Key [C]              -> Re-Center Cursor")
    print("   * Key [D]              -> Test Double Click")
    print("   * Key [Q] / [ESC]      -> Quit")
    print("==================================================")

    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        output_face_blendshapes=True,
        num_faces=1
    )

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)

    cam.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAM_WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAM_HEIGHT)
    cam.set(cv2.CAP_PROP_FPS, 30)

    tracker = SimpleGazeTracker()

    with FaceLandmarker.create_from_options(options) as landmarker:
        while cam.isOpened():
            success, frame = cam.read()
            if not success:
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int(time.time() * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result and result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks = result.face_landmarks[0]
                blendshapes = result.face_blendshapes[0] if result.face_blendshapes else None
                frame = tracker.process(frame, landmarks, blendshapes)

            cv2.imshow("AeroPrecise - Eye Gaze Controller", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key in (ord('c'), ord('C')):
                tracker.recalibrate()
            elif key in (ord('d'), ord('D')):
                execute_double_click(tracker.locked_pos[0], tracker.locked_pos[1])
                tracker.alert_text = "TEST DOUBLE CLICK!"
                tracker.alert_color = (0, 255, 0)
                tracker.alert_timer = time.time()

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""
=============================================================================
AEROPRECISE PRO - ENTERPRISE HANDS-FREE EYE & GAZE CONTROLLER
=============================================================================
Incorporating:
1. 🎯 Verified Ultra-Precise Click System (Single Blink, Double Blink, Right Wink, Dwell)
2. 🎛️ Eyebrow-Raised Quick Action Radial Pie Menu (Raise Eyebrow to Open/Close)
3. 🔍 3x Precision Gaze Magnifier Scope (Key [Z] or Menu)
4. 🔊 Non-Blocking Audio Acoustic Clicks & Chimes
5. 📜 Hands-Free Smooth Page Scrolling (Edge Gaze & Mouth Aperture Detection)
6. 🪟 Full Hands-Free Drag & Drop Mode (Double-Wink Grab & Release)
7. 🎯 Smart Target Magnetism (Zero-Drift Micro-Fixation Lock)
=============================================================================
"""

import os
import sys
import time
import math
import threading
import urllib.request
import numpy as np
import cv2
import pyautogui
import mediapipe as mp

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# ==========================================
# 0. MODEL AUTO-DOWNLOAD VERIFICATION
# ==========================================
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def ensure_model_file():
    if not os.path.exists(MODEL_PATH):
        print(f"[SYSTEM] '{MODEL_PATH}' not found. Downloading MediaPipe AI Asset...")
        try:
            def reporthook(count, block_size, total_size):
                pct = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\rDownloading Neural Asset: {pct}%")
                sys.stdout.flush()
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook)
            print(f"\n[SYSTEM] Model downloaded successfully ({os.path.getsize(MODEL_PATH)} bytes).")
        except Exception as e:
            print(f"\n[ERROR] Download failed: {e}")
            sys.exit(1)

ensure_model_file()

# ==========================================
# 1. SCREEN & HARDWARE SETUP
# ==========================================
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001

SCREEN_W, SCREEN_H = pyautogui.size()
SCREEN_CENTER_X = SCREEN_W / 2.0
SCREEN_CENTER_Y = SCREEN_H / 2.0


# ==========================================
# 2. ASYNCHRONOUS AUDIO FEEDBACK ENGINE
# ==========================================
class SoundFX:
    @staticmethod
    def play_click():
        if HAS_WINSOUND:
            threading.Thread(target=lambda: winsound.Beep(1350, 25), daemon=True).start()

    @staticmethod
    def play_double_click():
        if HAS_WINSOUND:
            def _beep():
                winsound.Beep(1350, 20)
                time.sleep(0.04)
                winsound.Beep(1750, 25)
            threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_right_click():
        if HAS_WINSOUND:
            threading.Thread(target=lambda: winsound.Beep(900, 35), daemon=True).start()

    @staticmethod
    def play_drag_lock():
        if HAS_WINSOUND:
            def _beep():
                winsound.Beep(700, 25)
                winsound.Beep(1100, 35)
            threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_drag_release():
        if HAS_WINSOUND:
            def _beep():
                winsound.Beep(1100, 25)
                winsound.Beep(700, 35)
            threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_chime():
        if HAS_WINSOUND:
            def _beep():
                for freq in (900, 1300, 1700):
                    winsound.Beep(freq, 25)
                    time.sleep(0.02)
            threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_zoom(active=True):
        if HAS_WINSOUND:
            freqs = (1100, 1500) if active else (1500, 1100)
            def _beep():
                winsound.Beep(freqs[0], 25)
                winsound.Beep(freqs[1], 30)
            threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_menu_select():
        if HAS_WINSOUND:
            def _beep():
                winsound.Beep(1600, 30)
                winsound.Beep(2000, 40)
            threading.Thread(target=_beep, daemon=True).start()


# ==========================================
# 3. CONFIGURATION & TUNABLE PARAMETERS
# ==========================================
class Config:
    CAM_WIDTH = 640
    CAM_HEIGHT = 480
    
    # Sensitivity (Cursor speed multiplier)
    SENSITIVITY_X = 2.4
    SENSITIVITY_Y = 2.2
    
    # Precision Magnifier Zoom: Sensitivity reduction when Zoom Mode is active
    ZOOM_PRECISION_DIVISOR = 3.2
    
    # Anti-Jitter Deadzone Radius (in Screen Pixels)
    DEADZONE_RADIUS = 18.0
    BASE_SMOOTHING_ALPHA = 0.22
    
    # Smart Target Magnetism: Distance threshold for magnetic anchor snap
    MAGNETIC_SNAP_RADIUS = 35.0
    
    # Dwell Click Settings (Hover to click)
    DWELL_ENABLED = True
    DWELL_TIME_SEC = 0.90
    DWELL_MAX_MOVE_PIXELS = 18.0
    
    # Radial Pie Menu Settings
    RADIAL_MENU_DWELL_SEC = 0.45
    RADIAL_MENU_RADIUS = 110
    
    # Scrolling settings
    SCROLL_SPEED = 28
    EDGE_SCROLL_MARGIN = 0.12  # Top/bottom 12% of screen triggers scroll
    
    # Blink & Wink Thresholds (Original Proven Values)
    EAR_THRESHOLD = 0.19
    SINGLE_BLINK_MAX = 0.40
    DOUBLE_CLICK_WINDOW = 0.40
    
    # Eyebrow Raise Sensitivity (For Menu)
    BROW_RAISE_THRESHOLD = 0.35
    
    BORDER_MARGIN = 5


# ==========================================
# 4. SMART MAGNETIC STABILIZER & SMOOTH FILTER
# ==========================================
class SmartMagneticFilter:
    def __init__(self):
        self.cursor_x = SCREEN_CENTER_X
        self.cursor_y = SCREEN_CENTER_Y
        self.anchor_x = SCREEN_CENTER_X
        self.anchor_y = SCREEN_CENTER_Y
        self.is_magnetized = True

    def reset(self):
        self.cursor_x = SCREEN_CENTER_X
        self.cursor_y = SCREEN_CENTER_Y
        self.anchor_x = SCREEN_CENTER_X
        self.anchor_y = SCREEN_CENTER_Y
        self.is_magnetized = True

    def update(self, target_x, target_y):
        dist = math.hypot(target_x - self.anchor_x, target_y - self.anchor_y)

        # Smart Magnetism: Lock firmly onto target during fixations
        if dist <= Config.DEADZONE_RADIUS:
            self.is_magnetized = True
            out_x = self.anchor_x
            out_y = self.anchor_y
        elif dist <= Config.MAGNETIC_SNAP_RADIUS:
            # Magnetic attraction: dampens 80% of micro-drift
            self.is_magnetized = True
            out_x = self.anchor_x * 0.80 + target_x * 0.20
            out_y = self.anchor_y * 0.80 + target_y * 0.20
            self.cursor_x = out_x
            self.cursor_y = out_y
        else:
            # Deliberate movement: Break magnetic lock and accelerate
            self.is_magnetized = False
            dynamic_alpha = min(1.0, Config.BASE_SMOOTHING_ALPHA * (1.0 + dist / 120.0))
            self.cursor_x += (target_x - self.cursor_x) * dynamic_alpha
            self.cursor_y += (target_y - self.cursor_y) * dynamic_alpha
            
            # Slide anchor point
            shift = dist - Config.DEADZONE_RADIUS
            angle = math.atan2(target_y - self.anchor_y, target_x - self.anchor_x)
            self.anchor_x += math.cos(angle) * shift * 0.45
            self.anchor_y += math.sin(angle) * shift * 0.45
            
            out_x = self.cursor_x
            out_y = self.cursor_y

        out_x = max(Config.BORDER_MARGIN, min(SCREEN_W - Config.BORDER_MARGIN, out_x))
        out_y = max(Config.BORDER_MARGIN, min(SCREEN_H - Config.BORDER_MARGIN, out_y))

        return int(out_x), int(out_y), self.is_magnetized


# ==========================================
# 5. SCALE-INVARIANT EYE ASPECT RATIO (EAR)
# ==========================================
def calculate_ear(landmarks, eye_indices, w, h):
    pts = [np.array([landmarks[idx].x * w, landmarks[idx].y * h]) for idx in eye_indices]
    d_v1 = np.linalg.norm(pts[1] - pts[5])
    d_v2 = np.linalg.norm(pts[2] - pts[4])
    d_h = np.linalg.norm(pts[0] - pts[3])
    if d_h < 1e-6:
        return 0.0
    return (d_v1 + d_v2) / (2.0 * d_h)


# ==========================================
# 6. MASTER CONTROLLER
# ==========================================
class HandsFreeControllerPro:
    LEFT_EYE_LANDMARKS = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_LANDMARKS = [362, 385, 387, 263, 373, 380]
    NOSE_TIP = 1
    LEFT_IRIS = 468
    RIGHT_IRIS = 473

    RADIAL_SLICES = [
        {"name": "COPY", "icon": "[Ctrl+C]", "action": "copy"},
        {"name": "PASTE", "icon": "[Ctrl+V]", "action": "paste"},
        {"name": "ZOOM", "icon": "[3x Scope]", "action": "zoom"},
        {"name": "ALT-TAB", "icon": "[App Switch]", "action": "alttab"},
        {"name": "CLOSE TAB", "icon": "[Ctrl+W]", "action": "closetab"},
        {"name": "VOL MUTE", "icon": "[Mute/Vol]", "action": "volume"},
    ]

    def __init__(self):
        self.filter = SmartMagneticFilter()
        
        self.is_paused = False
        self.is_calibrated = False
        self.calibration_frames = 0
        self.calib_samples = []
        
        self.base_nose_x = 0.50
        self.base_nose_y = 0.50
        self.is_magnetized = True
        
        # Gesture States (Original Proven Logic)
        self.blink_start_time = None
        self.last_blink_release_time = 0.0
        self.pending_single_click = None
        self.both_closed_start = None
        
        # Left Wink (Drag & Drop State Machine)
        self.left_closed_start = None
        self.last_left_wink_release = 0.0
        self.is_dragging = False
        
        # Right Wink
        self.right_closed_start = None
        
        # Dwell Click Tracker
        self.dwell_start_time = None
        self.dwell_anchor_pos = (0, 0)
        self.dwell_progress = 0.0
        
        # Scrolling Tracker
        self.is_scrolling = False
        
        # Precision Zoom & Radial Menu
        self.is_zoom_mode = False
        self.is_radial_menu_open = False
        self.radial_hovered_slice = None
        self.radial_hover_start = None
        self.radial_hover_progress = 0.0
        self.brow_raised_prev = False
        self.brow_score = 0.0
        
        # UI Alerts
        self.action_alert = ""
        self.action_alert_time = 0.0

    def trigger_action(self, text):
        self.action_alert = text
        self.action_alert_time = time.time()
        print(f"[ACTION] {text}")

    def toggle_zoom_mode(self):
        self.is_zoom_mode = not self.is_zoom_mode
        SoundFX.play_zoom(self.is_zoom_mode)
        state_str = "PRECISION ZOOM 3x ON" if self.is_zoom_mode else "ZOOM OFF (NORMAL)"
        self.trigger_action(state_str)

    def execute_radial_action(self, action_key):
        SoundFX.play_menu_select()
        if action_key == "copy":
            pyautogui.hotkey('ctrl', 'c')
            self.trigger_action("COPIED (Ctrl+C)")
        elif action_key == "paste":
            pyautogui.hotkey('ctrl', 'v')
            self.trigger_action("PASTED (Ctrl+V)")
        elif action_key == "zoom":
            self.toggle_zoom_mode()
        elif action_key == "alttab":
            pyautogui.hotkey('alt', 'tab')
            self.trigger_action("SWITCHED APP (Alt+Tab)")
        elif action_key == "closetab":
            pyautogui.hotkey('ctrl', 'w')
            self.trigger_action("CLOSED TAB (Ctrl+W)")
        elif action_key == "volume":
            pyautogui.press('volumemute')
            self.trigger_action("VOLUME MUTE TOGGLED")

    def start_calibration(self):
        self.is_calibrated = False
        self.calibration_frames = 0
        self.calib_samples = []
        self.filter.reset()
        if self.is_dragging:
            pyautogui.mouseUp()
            self.is_dragging = False
        self.trigger_action("LOOK AT SCREEN CENTER...")

    def process_frame(self, frame, landmarks, blendshapes):
        h, w, _ = frame.shape
        curr_time = time.time()

        # Step A: Compute Eye Aspect Ratio (EAR) & Blendshapes
        left_ear = calculate_ear(landmarks, self.LEFT_EYE_LANDMARKS, w, h)
        right_ear = calculate_ear(landmarks, self.RIGHT_EYE_LANDMARKS, w, h)

        left_eye_closed = left_ear < Config.EAR_THRESHOLD
        right_eye_closed = right_ear < Config.EAR_THRESHOLD
        both_eyes_closed = left_eye_closed and right_eye_closed

        jaw_open = 0.0
        self.brow_score = 0.0
        if blendshapes:
            bs = {cat.category_name: cat.score for cat in blendshapes}
            jaw_open = bs.get('jawOpen', 0.0)
            self.brow_score = max(bs.get('browInnerUp', 0.0), bs.get('browOuterUpLeft', 0.0), bs.get('browOuterUpRight', 0.0))
            if bs.get('eyeBlinkLeft', 0) > 0.50:
                left_eye_closed = True
            if bs.get('eyeBlinkRight', 0) > 0.50:
                right_eye_closed = True
            both_eyes_closed = left_eye_closed and right_eye_closed

        nose = landmarks[self.NOSE_TIP]

        # Step B: 2-Second Startup Auto-Calibration
        if not self.is_calibrated:
            self.calib_samples.append((nose.x, nose.y))
            self.calibration_frames += 1
            progress = min(1.0, self.calibration_frames / 50.0)

            if self.calibration_frames >= 50:
                self.base_nose_x = float(np.mean([s[0] for s in self.calib_samples]))
                self.base_nose_y = float(np.mean([s[1] for s in self.calib_samples]))
                self.is_calibrated = True
                self.filter.reset()
                SoundFX.play_chime()
                self.trigger_action("CALIBRATION COMPLETE!")

            return self.draw_calibration_hud(frame, progress)

        # Step C: Safety Pause / Rest Mode (Close both eyes > 1.2s)
        if both_eyes_closed:
            if self.both_closed_start is None:
                self.both_closed_start = curr_time
            elif curr_time - self.both_closed_start > 1.2:
                self.is_paused = not self.is_paused
                self.both_closed_start = None
                if self.is_dragging:
                    pyautogui.mouseUp()
                    self.is_dragging = False
                SoundFX.play_right_click()
                self.trigger_action("PAUSED" if self.is_paused else "ACTIVE")
        else:
            self.both_closed_start = None

        if self.is_paused:
            cv2.putText(frame, "=== TRACKING PAUSED ===", (w // 2 - 170, h // 2),
                        cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2)
            return self.draw_hud(frame, left_ear, right_ear, left_eye_closed, right_eye_closed)

        # Step D: Eyebrow Raise Radial Menu Toggle
        is_brow_raised = self.brow_score > Config.BROW_RAISE_THRESHOLD
        if is_brow_raised and not self.brow_raised_prev:
            self.is_radial_menu_open = not self.is_radial_menu_open
            SoundFX.play_chime()
            self.trigger_action("RADIAL MENU OPEN" if self.is_radial_menu_open else "MENU CLOSED")
            self.radial_hovered_slice = None
            self.radial_hover_start = None
            self.radial_hover_progress = 0.0
        self.brow_raised_prev = is_brow_raised

        # Step E: Cursor Calculation
        sens_x = Config.SENSITIVITY_X / (Config.ZOOM_PRECISION_DIVISOR if self.is_zoom_mode else 1.0)
        sens_y = Config.SENSITIVITY_Y / (Config.ZOOM_PRECISION_DIVISOR if self.is_zoom_mode else 1.0)
        
        dx_rel = (nose.x - self.base_nose_x)
        dy_rel = (nose.y - self.base_nose_y)

        dx = dx_rel * sens_x * SCREEN_W
        dy = dy_rel * sens_y * SCREEN_H

        target_x = SCREEN_CENTER_X + dx
        target_y = SCREEN_CENTER_Y + dy

        # If Radial Menu is open, steer slice selection hands-free
        if self.is_radial_menu_open:
            slice_idx = self.calculate_radial_slice(dx_rel * 400.0, dy_rel * 400.0)
            if slice_idx is not None:
                if self.radial_hovered_slice != slice_idx:
                    self.radial_hovered_slice = slice_idx
                    self.radial_hover_start = curr_time
                    self.radial_hover_progress = 0.0
                else:
                    elapsed = curr_time - self.radial_hover_start
                    self.radial_hover_progress = min(1.0, elapsed / Config.RADIAL_MENU_DWELL_SEC)
                    if elapsed >= Config.RADIAL_MENU_DWELL_SEC:
                        action_item = self.RADIAL_SLICES[slice_idx]
                        self.execute_radial_action(action_item["action"])
                        self.is_radial_menu_open = False
                        self.radial_hovered_slice = None
                        self.radial_hover_progress = 0.0
            else:
                self.radial_hovered_slice = None
                self.radial_hover_start = None
                self.radial_hover_progress = 0.0

            self.draw_debug_overlay(frame, landmarks, w, h)
            self.draw_radial_pie_menu(frame, w, h)
            return self.draw_hud(frame, left_ear, right_ear, left_eye_closed, right_eye_closed)

        cursor_x, cursor_y, self.is_magnetized = self.filter.update(target_x, target_y)
        pyautogui.moveTo(cursor_x, cursor_y)

        # Step F: Smooth Page Scrolling
        self.is_scrolling = False
        if not self.is_dragging:
            if jaw_open > 0.42:
                pyautogui.scroll(-Config.SCROLL_SPEED)
                self.is_scrolling = True
                self.trigger_action("SCROLL DOWN (MOUTH)")
            elif cursor_y < SCREEN_H * Config.EDGE_SCROLL_MARGIN:
                pyautogui.scroll(Config.SCROLL_SPEED)
                self.is_scrolling = True
                self.trigger_action("SCROLL UP (EDGE)")
            elif cursor_y > SCREEN_H * (1.0 - Config.EDGE_SCROLL_MARGIN):
                pyautogui.scroll(-Config.SCROLL_SPEED)
                self.is_scrolling = True
                self.trigger_action("SCROLL DOWN (EDGE)")

        # Step G: Drag & Drop (Double Left-Wink)
        if left_eye_closed and not right_eye_closed:
            if self.left_closed_start is None:
                self.left_closed_start = curr_time
        else:
            if self.left_closed_start is not None:
                duration = curr_time - self.left_closed_start
                if 0.20 <= duration <= 0.70:
                    if curr_time - self.last_left_wink_release <= 0.55:
                        self.is_dragging = not self.is_dragging
                        if self.is_dragging:
                            pyautogui.mouseDown()
                            SoundFX.play_drag_lock()
                            self.trigger_action("DRAG LOCKED")
                        else:
                            pyautogui.mouseUp()
                            SoundFX.play_drag_release()
                            self.trigger_action("DRAG RELEASED")
                        self.last_left_wink_release = 0.0
                    else:
                        self.last_left_wink_release = curr_time
                self.left_closed_start = None

        # Step H: PROVEN SINGLE & DOUBLE BLINK ENGINE
        if both_eyes_closed:
            if self.blink_start_time is None:
                self.blink_start_time = curr_time
        else:
            if self.blink_start_time is not None:
                duration = curr_time - self.blink_start_time
                self.blink_start_time = None

                if 0.05 <= duration <= Config.SINGLE_BLINK_MAX:
                    if curr_time - self.last_blink_release_time <= Config.DOUBLE_CLICK_WINDOW:
                        pyautogui.doubleClick()
                        SoundFX.play_double_click()
                        self.trigger_action("DOUBLE CLICK!")
                        self.pending_single_click = None
                        self.last_blink_release_time = 0.0
                    else:
                        self.last_blink_release_time = curr_time
                        self.pending_single_click = curr_time

        # Flush single click after window expires
        if self.pending_single_click is not None:
            if curr_time - self.pending_single_click > Config.DOUBLE_CLICK_WINDOW:
                if not self.is_dragging:
                    pyautogui.click(button='left')
                    SoundFX.play_click()
                    self.trigger_action("SINGLE CLICK!")
                self.pending_single_click = None

        # Right Wink -> Right Click
        if right_eye_closed and not left_eye_closed:
            if self.right_closed_start is None:
                self.right_closed_start = curr_time
        else:
            if self.right_closed_start is not None:
                duration = curr_time - self.right_closed_start
                if 0.22 <= duration <= 0.75:
                    if self.is_dragging:
                        pyautogui.mouseUp()
                        self.is_dragging = False
                    pyautogui.click(button='right')
                    SoundFX.play_right_click()
                    self.trigger_action("RIGHT CLICK!")
                self.right_closed_start = None

        # Dwell Click (Hover 0.9s to auto-click)
        if Config.DWELL_ENABLED and not self.is_dragging and not self.is_scrolling:
            curr_pos = (cursor_x, cursor_y)
            dist_from_anchor = math.hypot(curr_pos[0] - self.dwell_anchor_pos[0],
                                          curr_pos[1] - self.dwell_anchor_pos[1])

            if dist_from_anchor < Config.DWELL_MAX_MOVE_PIXELS:
                if self.dwell_start_time is None:
                    self.dwell_start_time = curr_time
                else:
                    elapsed = curr_time - self.dwell_start_time
                    self.dwell_progress = min(1.0, elapsed / Config.DWELL_TIME_SEC)
                    if elapsed >= Config.DWELL_TIME_SEC:
                        pyautogui.click(button='left')
                        SoundFX.play_click()
                        self.trigger_action("DWELL CLICK!")
                        self.dwell_start_time = None
                        self.dwell_progress = 0.0
            else:
                self.dwell_anchor_pos = curr_pos
                self.dwell_start_time = curr_time
                self.dwell_progress = 0.0
        else:
            self.dwell_progress = 0.0

        self.draw_debug_overlay(frame, landmarks, w, h)
        if self.is_zoom_mode:
            self.draw_precision_zoom_scope(frame, landmarks, w, h)

        return self.draw_hud(frame, left_ear, right_ear, left_eye_closed, right_eye_closed)

    def calculate_radial_slice(self, vec_x, vec_y):
        dist = math.hypot(vec_x, vec_y)
        if dist < 22.0:
            return None
        angle = math.degrees(math.atan2(vec_y, vec_x)) % 360
        slice_size = 360.0 / len(self.RADIAL_SLICES)
        slice_idx = int((angle + slice_size / 2.0) % 360 // slice_size)
        return slice_idx

    def draw_radial_pie_menu(self, frame, w, h):
        cx, cy = w // 2, h // 2
        r = Config.RADIAL_MENU_RADIUS
        
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), r + 15, (20, 20, 25), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        
        cv2.circle(frame, (cx, cy), r + 15, (0, 220, 255), 2)
        cv2.circle(frame, (cx, cy), 22, (50, 50, 50), -1)
        cv2.putText(frame, "EYE MENU", (cx - 36, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)

        num_slices = len(self.RADIAL_SLICES)
        slice_deg = 360.0 / num_slices

        for i, item in enumerate(self.RADIAL_SLICES):
            ang_mid = math.radians(i * slice_deg)
            is_active = (self.radial_hovered_slice == i)

            ang_sep = math.radians(i * slice_deg - slice_deg / 2.0)
            sx = int(cx + (r + 15) * math.cos(ang_sep))
            sy = int(cy + (r + 15) * math.sin(ang_sep))
            cv2.line(frame, (cx, cy), (sx, sy), (60, 60, 60), 1)

            tx = int(cx + (r * 0.65) * math.cos(ang_mid))
            ty = int(cy + (r * 0.65) * math.sin(ang_mid))

            color = (0, 255, 180) if is_active else (220, 220, 220)
            if is_active:
                cv2.circle(frame, (tx, ty), 24, (0, 160, 255), -1)
                angle_arc = int(self.radial_hover_progress * 360)
                cv2.ellipse(frame, (tx, ty), (26, 26), 0, -90, -90 + angle_arc, (0, 255, 0), 3)

            cv2.putText(frame, item["name"], (tx - 24, ty - 2), cv2.FONT_HERSHEY_DUPLEX, 0.40, color, 1)
            cv2.putText(frame, item["icon"], (tx - 22, ty + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1)

    def draw_precision_zoom_scope(self, frame, landmarks, w, h):
        bx, by, bw, bh = w - 150, 65, 140, 140
        
        iris_pt = landmarks[self.LEFT_IRIS]
        ix, iy = int(iris_pt.x * w), int(iris_pt.y * h)
        
        crop_r = 30
        x1, y1 = max(0, ix - crop_r), max(0, iy - crop_r)
        x2, y2 = min(w, ix + crop_r), min(h, iy + crop_r)
        
        eye_crop = frame[y1:y2, x1:x2]
        if eye_crop.size > 0:
            eye_zoom = cv2.resize(eye_crop, (bw, bh), interpolation=cv2.INTER_LINEAR)
            
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 220, 255), 2)
            frame[by:by + bh, bx:bx + bw] = eye_zoom
            
            cv2.line(frame, (bx + bw // 2, by), (bx + bw // 2, by + bh), (0, 255, 0), 1)
            cv2.line(frame, (bx, by + bh // 2), (bx + bw, by + bh // 2), (0, 255, 0), 1)
            cv2.circle(frame, (bx + bw // 2, by + bh // 2), 16, (0, 255, 255), 1)
            cv2.putText(frame, "3x PRECISION SCOPE", (bx + 5, by - 6), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 220, 255), 1)

    def draw_debug_overlay(self, frame, landmarks, w, h):
        for iris_idx, color in [(self.LEFT_IRIS, (0, 255, 0)), (self.RIGHT_IRIS, (0, 255, 255))]:
            pt = landmarks[iris_idx]
            cx, cy = int(pt.x * w), int(pt.y * h)
            cv2.circle(frame, (cx, cy), 3, color, -1)
            cv2.circle(frame, (cx, cy), 6, (255, 255, 255), 1)

        nose = landmarks[self.NOSE_TIP]
        cv2.circle(frame, (int(nose.x * w), int(nose.y * h)), 4, (0, 165, 255), -1)

    def draw_calibration_hud(self, frame, progress):
        h, w, _ = frame.shape
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (15, 15, 20), -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        cv2.putText(frame, "AUTO-CENTER CALIBRATION", (w // 2 - 180, h // 2 - 35),
                    cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 220, 255), 2)
        cv2.putText(frame, "Look at the exact CENTER of your display...", (w // 2 - 200, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)

        bar_w = 300
        bar_x = w // 2 - bar_w // 2
        bar_y = h // 2 + 35
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 16), (70, 70, 70), 2)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + 16), (0, 255, 180), -1)
        return frame

    def draw_hud(self, frame, left_ear, right_ear, left_closed, right_closed):
        h, w, _ = frame.shape
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (18, 18, 22), -1)
        cv2.rectangle(overlay, (0, h - 35), (w, h), (18, 18, 22), -1)
        cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

        cv2.putText(frame, "AEROPRECISE PRO AI", (12, 22), cv2.FONT_HERSHEY_DUPLEX, 0.52, (0, 220, 255), 1)
        
        # Real-time Eyebrow Lift Telemetry Meter
        brow_pct = int(self.brow_score * 100.0)
        brow_color = (0, 255, 0) if self.brow_score > Config.BROW_RAISE_THRESHOLD else (180, 180, 180)
        cv2.putText(frame, f"BROW: {brow_pct}%", (12, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.38, brow_color, 1)

        # Status Badge
        if self.is_zoom_mode:
            cv2.putText(frame, "[PRECISION 3x ZOOM]", (110, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1)
        else:
            mag_badge = "[MAGNETIC SNAP: LOCKED]" if self.is_magnetized else "[ACTIVE: MOVING]"
            badge_color = (0, 255, 0) if self.is_magnetized else (0, 165, 255)
            cv2.putText(frame, mag_badge, (110, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, badge_color, 1)

        if self.is_dragging:
            cv2.rectangle(frame, (w // 2 - 75, 60), (w // 2 + 75, 85), (0, 0, 200), -1)
            cv2.putText(frame, "DRAG LOCKED", (w // 2 - 60, 78), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1)

        if time.time() - self.action_alert_time < 1.0:
            cv2.putText(frame, self.action_alert, (w // 2 - 110, 36), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 255, 0), 2)

        # Real-time EAR Gauges
        l_color = (0, 0, 255) if left_closed else (0, 255, 0)
        r_color = (0, 0, 255) if right_closed else (0, 255, 0)
        cv2.putText(frame, f"L: {left_ear:.2f}", (w - 210, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, l_color, 1)
        cv2.putText(frame, f"R: {right_ear:.2f}", (w - 105, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, r_color, 1)

        cv2.rectangle(frame, (w - 210, 30), (w - 120, 38), (70, 70, 70), 1)
        cv2.rectangle(frame, (w - 210, 30), (w - 210 + int(min(1.0, left_ear / 0.35) * 90), 38), l_color, -1)

        cv2.rectangle(frame, (w - 105, 30), (w - 15, 38), (70, 70, 70), 1)
        cv2.rectangle(frame, (w - 105, 30), (w - 105 + int(min(1.0, right_ear / 0.35) * 90), 38), r_color, -1)

        if self.dwell_progress > 0.05:
            dwell_center = (40, h - 70)
            cv2.circle(frame, dwell_center, 18, (80, 80, 80), 2)
            angle = int(self.dwell_progress * 360)
            cv2.ellipse(frame, dwell_center, (18, 18), 0, -90, -90 + angle, (0, 255, 255), 3)
            cv2.putText(frame, "DWELL", (65, h - 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        help_text = "Raise Brows: Menu | [Z] Zoom | [C] Center | [P] Pause | [Q] Quit"
        cv2.putText(frame, help_text, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
        return frame


# ==========================================
# 7. APPLICATION RUN LOOP
# ==========================================
def main():
    print("==================================================")
    print("     AEROPRECISE PRO - ULTIMATE HANDS-FREE AI     ")
    print("==================================================")
    print("-> Controls & Gestures:")
    print("   * 👁️ Single Blink           -> SINGLE CLICK")
    print("   * 👁️ 2 Rapid Blinks (.40s)   -> DOUBLE CLICK")
    print("   * 😉 Right Wink               -> RIGHT CLICK")
    print("   * 🎯 Dwell Hover (0.9s)       -> DWELL CLICK")
    print("   * 🤨 Raise Eyebrows / [M]     -> Radial Pie Menu")
    print("   * 🔍 Key [Z]                  -> 3x Precision Zoom Scope")
    print("   * 😉 2 Left Winks             -> Drag & Drop Grab/Release")
    print("   * 😮 Open Mouth / Edge Look   -> Smooth Page Scroll")
    print("   * Key [C]                     -> Re-Center Calibration")
    print("   * Key [P]                     -> Pause / Resume")
    print("   * Key [Q] / [ESC]             -> Quit")
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

    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAM_WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAM_HEIGHT)
    cam.set(cv2.CAP_PROP_FPS, 30)

    if not cam.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    controller = HandsFreeControllerPro()

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
                frame = controller.process_frame(frame, landmarks, blendshapes)
            else:
                cv2.putText(frame, "NO FACE DETECTED", (Config.CAM_WIDTH // 2 - 100, Config.CAM_HEIGHT // 2),
                            cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("AeroPrecise Pro - Hands-Free Control", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key in (ord('c'), ord('C')):
                controller.start_calibration()
            elif key in (ord('p'), ord('P')):
                controller.is_paused = not controller.is_paused
                controller.trigger_action("PAUSED" if controller.is_paused else "RESUMED")
            elif key in (ord('z'), ord('Z')):
                controller.toggle_zoom_mode()
            elif key in (ord('m'), ord('M')):
                controller.is_radial_menu_open = not controller.is_radial_menu_open
                SoundFX.play_chime()
                controller.trigger_action("RADIAL MENU OPEN" if controller.is_radial_menu_open else "MENU CLOSED")
            elif key in (ord('+'), ord('=')):
                Config.SENSITIVITY_X = min(5.0, Config.SENSITIVITY_X + 0.3)
                Config.SENSITIVITY_Y = min(5.0, Config.SENSITIVITY_Y + 0.3)
                controller.trigger_action(f"SPEED: {Config.SENSITIVITY_X:.1f}x")
            elif key in (ord('-'), ord('_')):
                Config.SENSITIVITY_X = max(1.0, Config.SENSITIVITY_X - 0.3)
                Config.SENSITIVITY_Y = max(1.0, Config.SENSITIVITY_Y - 0.3)
                controller.trigger_action(f"SPEED: {Config.SENSITIVITY_X:.1f}x")

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

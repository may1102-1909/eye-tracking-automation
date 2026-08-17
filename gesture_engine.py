"""
Assistive Gesture & Interaction Suite
=====================================
1. Precision Wink Detector (Scale-Invariant EAR + Blendshapes).
2. Dwell Click Engine with Visual Progress.
3. Drag & Drop State Machine.
4. Variable Speed Smooth Scrolling.
5. Safety Rest Mode Controller.
"""

import time
import math
import numpy as np
import pyautogui


def calculate_ear(landmarks, eye_indices, w, h):
    pts = [np.array([landmarks[idx].x * w, landmarks[idx].y * h]) for idx in eye_indices]
    d_v1 = np.linalg.norm(pts[1] - pts[5])
    d_v2 = np.linalg.norm(pts[2] - pts[4])
    d_h = np.linalg.norm(pts[0] - pts[3])
    if d_h < 1e-6:
        return 0.0
    return (d_v1 + d_v2) / (2.0 * d_h)


class GestureEngine:
    LEFT_EYE_LANDMARKS = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_LANDMARKS = [362, 385, 387, 263, 373, 380]

    def __init__(self):
        self.ear_threshold = 0.17
        self.wink_min_time = 0.22
        self.wink_max_time = 0.75
        self.dwell_time = 0.95
        self.dwell_radius = 18.0

        self.left_wink_start = None
        self.right_wink_start = None
        self.both_closed_start = None
        self.last_left_click_time = 0.0
        self.is_dragging = False

        self.dwell_start_time = None
        self.dwell_anchor = (0, 0)
        self.dwell_progress = 0.0

        self.last_scroll_time = 0.0
        self.is_paused = False

        self.event_alert = ""
        self.event_time = 0.0

    def trigger_event(self, msg):
        self.event_alert = msg
        self.event_time = time.time()

    def update(self, frame_shape, landmarks, blendshapes, cursor_pos, head_pitch):
        h, w = frame_shape[:2]
        curr_time = time.time()

        l_ear = calculate_ear(landmarks, self.LEFT_EYE_LANDMARKS, w, h)
        r_ear = calculate_ear(landmarks, self.RIGHT_EYE_LANDMARKS, w, h)

        left_closed = l_ear < self.ear_threshold
        right_closed = r_ear < self.ear_threshold

        jaw_open = 0.0
        if blendshapes:
            bs = {cat.category_name: cat.score for cat in blendshapes}
            jaw_open = bs.get('jawOpen', 0.0)
            if bs.get('eyeBlinkLeft', 0) > 0.65:
                left_closed = True
            if bs.get('eyeBlinkRight', 0) > 0.65:
                right_closed = True

        # Rest / Safety Pause Mode
        if left_closed and right_closed:
            if self.both_closed_start is None:
                self.both_closed_start = curr_time
            elif curr_time - self.both_closed_start > 1.2:
                self.is_paused = not self.is_paused
                self.both_closed_start = None
                if self.is_dragging:
                    pyautogui.mouseUp()
                    self.is_dragging = False
                self.trigger_event("SYSTEM SLEEP" if self.is_paused else "SYSTEM ACTIVE")
        else:
            self.both_closed_start = None

        if self.is_paused:
            return {
                "l_ear": l_ear, "r_ear": r_ear, 
                "left_closed": left_closed, "right_closed": right_closed,
                "is_paused": True, "dwell_progress": 0.0, "is_dragging": self.is_dragging
            }

        # Left Wink -> Left Click & Double-Wink Drag
        if left_closed and not right_closed:
            if self.left_wink_start is None:
                self.left_wink_start = curr_time
        else:
            if self.left_wink_start is not None:
                duration = curr_time - self.left_wink_start
                if self.wink_min_time <= duration <= self.wink_max_time:
                    if curr_time - self.last_left_click_time < 0.55:
                        self.is_dragging = not self.is_dragging
                        if self.is_dragging:
                            pyautogui.mouseDown()
                            self.trigger_event("DRAG LOCKED")
                        else:
                            pyautogui.mouseUp()
                            self.trigger_event("DRAG RELEASED")
                    else:
                        if not self.is_dragging:
                            pyautogui.click(button='left')
                            self.trigger_event("LEFT CLICK")
                    self.last_left_click_time = curr_time
                self.left_wink_start = None

        # Right Wink -> Right Click
        if right_closed and not left_closed:
            if self.right_wink_start is None:
                self.right_wink_start = curr_time
        else:
            if self.right_wink_start is not None:
                duration = curr_time - self.right_wink_start
                if self.wink_min_time <= duration <= self.wink_max_time:
                    if self.is_dragging:
                        pyautogui.mouseUp()
                        self.is_dragging = False
                    pyautogui.click(button='right')
                    self.trigger_event("RIGHT CLICK")
                self.right_wink_start = None

        # Hands-Free Smooth Scroll
        if jaw_open > 0.45 or abs(head_pitch) > 14.0:
            if curr_time - self.last_scroll_time > 0.08:
                scroll_amount = 0
                if jaw_open > 0.45:
                    scroll_amount = -35
                elif head_pitch > 14.0:
                    scroll_amount = int((head_pitch - 14.0) * 3)
                elif head_pitch < -14.0:
                    scroll_amount = int((head_pitch + 14.0) * 3)

                if scroll_amount != 0:
                    pyautogui.scroll(scroll_amount)
                    self.last_scroll_time = curr_time
                    self.trigger_event("SCROLLING")

        # Dwell Click Engine
        if not self.is_dragging:
            dist = math.hypot(cursor_pos[0] - self.dwell_anchor[0], cursor_pos[1] - self.dwell_anchor[1])
            if dist < self.dwell_radius:
                if self.dwell_start_time is None:
                    self.dwell_start_time = curr_time
                else:
                    elapsed = curr_time - self.dwell_start_time
                    self.dwell_progress = min(1.0, elapsed / self.dwell_time)
                    if elapsed >= self.dwell_time:
                        pyautogui.click(button='left')
                        self.trigger_event("DWELL CLICK")
                        self.dwell_start_time = None
                        self.dwell_progress = 0.0
            else:
                self.dwell_anchor = cursor_pos
                self.dwell_start_time = curr_time
                self.dwell_progress = 0.0
        else:
            self.dwell_progress = 0.0

        return {
            "l_ear": l_ear, "r_ear": r_ear,
            "left_closed": left_closed, "right_closed": right_closed,
            "is_paused": False, "dwell_progress": self.dwell_progress,
            "is_dragging": self.is_dragging
        }

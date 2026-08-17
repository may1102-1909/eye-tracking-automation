"""
Enterprise Assistive Heads-Up Display (HUD)
===========================================
Renders real-time visual telemetry, 3D pose vectors, eye meters, and system state.
"""

import time
import numpy as np
import cv2


class HUDRenderer:
    def __init__(self):
        self.fps_counter = 0
        self.fps_time = time.time()
        self.current_fps = 30.0

    def render(self, frame, state):
        h, w = frame.shape[:2]

        self.fps_counter += 1
        now = time.time()
        if now - self.fps_time >= 0.5:
            self.current_fps = self.fps_counter / (now - self.fps_time)
            self.fps_counter = 0
            self.fps_time = now

        # Semi-transparent Glass Bars
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (15, 15, 20), -1)
        cv2.rectangle(overlay, (0, h - 40), (w, h), (15, 15, 20), -1)
        cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

        # Branding
        cv2.putText(frame, "AEROPRECISE GAZE AI", (14, 25), 
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 220, 255), 1)
        
        calib_str = "CALIBRATED [5-PT POLYNOMIAL]" if state.get("is_calibrated") else "AUTO-CENTERED"
        cv2.putText(frame, calib_str, (14, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 180), 1)

        # 3D Head Orientation
        yaw, pitch, roll = state.get("pose_3d", (0, 0, 0))
        pose_text = f"3D POSE: Y:{yaw:+05.1f} P:{pitch:+05.1f} R:{roll:+05.1f}"
        cv2.putText(frame, pose_text, (w // 2 - 130, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

        # Fixation Lock Indicator
        if state.get("is_fixating"):
            cv2.putText(frame, "[FIXATION LOCK]", (w // 2 - 65, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        else:
            cv2.putText(frame, "[SACCADE TRACK]", (w // 2 - 65, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 160, 255), 1)

        # Drag Active Badge
        g_info = state.get("gesture_info", {})
        if g_info.get("is_dragging"):
            cv2.rectangle(frame, (w // 2 - 75, 60), (w // 2 + 75, 85), (0, 0, 200), -1)
            cv2.putText(frame, "DRAG ACTIVE", (w // 2 - 55, 78), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1)

        # Eye Aspect Ratio (EAR) Gauges
        l_ear = g_info.get("l_ear", 0.3)
        r_ear = g_info.get("r_ear", 0.3)
        l_closed = g_info.get("left_closed", False)
        r_closed = g_info.get("right_closed", False)

        l_color = (0, 0, 255) if l_closed else (0, 255, 0)
        r_color = (0, 0, 255) if r_closed else (0, 255, 0)

        cv2.putText(frame, f"L: {l_ear:.2f}", (w - 200, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, l_color, 1)
        cv2.rectangle(frame, (w - 200, 30), (w - 110, 38), (60, 60, 60), 1)
        cv2.rectangle(frame, (w - 200, 30), (w - 200 + int(min(1.0, l_ear / 0.35) * 90), 38), l_color, -1)

        cv2.putText(frame, f"R: {r_ear:.2f}", (w - 95, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, r_color, 1)
        cv2.rectangle(frame, (w - 95, 30), (w - 10, 38), (60, 60, 60), 1)
        cv2.rectangle(frame, (w - 95, 30), (w - 95 + int(min(1.0, r_ear / 0.35) * 85), 38), r_color, -1)

        # Action Alerts
        alert_msg = state.get("event_alert", "")
        if alert_msg and time.time() - state.get("event_time", 0) < 1.0:
            cv2.putText(frame, alert_msg, (w // 2 - 80, 110), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 255, 255), 2)

        # Dwell Ring
        dwell_prog = g_info.get("dwell_progress", 0.0)
        if dwell_prog > 0.05:
            d_center = (45, h - 80)
            cv2.circle(frame, d_center, 22, (70, 70, 70), 2)
            angle = int(dwell_prog * 360)
            cv2.ellipse(frame, d_center, (22, 22), 0, -90, -90 + angle, (0, 255, 255), 3)
            cv2.putText(frame, "DWELL", (25, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1)

        # Sleep Overlay
        if g_info.get("is_paused"):
            cv2.putText(frame, "=== TRACKING SLEEP MODE ===", (w // 2 - 180, h // 2),
                        cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2)

        # Footer
        footer_text = "[C] 5-Pt Calibrate | [P] Pause | [S] Recenter | [Q] Quit"
        cv2.putText(frame, footer_text, (14, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1)
        cv2.putText(frame, f"{self.current_fps:.1f} FPS", (w - 75, h - 14), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 180), 1)

        return frame

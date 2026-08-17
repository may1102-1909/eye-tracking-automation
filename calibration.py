"""
Enterprise Calibration Engine & Polynomial Gaze Mapper
======================================================
1. 5-Point Fullscreen Interactive Calibration.
2. Bivariate Quadratic Polynomial Regression (Ridge Regularized).
3. Persistent Profiles (calibration_profile.json).
"""

import os
import json
import time
import numpy as np
import cv2

CALIBRATION_FILE = "calibration_profile.json"

class PolynomialGazeMapper:
    """Maps 2D gaze vector to screen pixels via 2nd-order bivariate polynomial."""
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.is_calibrated = False
        self.weights_x = None
        self.weights_y = None
        self.center_u = 0.0
        self.center_v = 0.0
        self.gain_x = 2.2
        self.gain_y = 2.0
        self.load_profile()

    def _build_features(self, u, v):
        u, v = float(u), float(v)
        return np.array([1.0, u, v, u**2, v**2, u * v], dtype=np.float64)

    def fit(self, samples_uv, targets_xy, reg_lambda=1e-3):
        N = len(samples_uv)
        if N < 5:
            return False

        Phi = np.zeros((N, 6), dtype=np.float64)
        for i, (u, v) in enumerate(samples_uv):
            Phi[i] = self._build_features(u, v)

        targets_x = np.array([t[0] for t in targets_xy], dtype=np.float64)
        targets_y = np.array([t[1] for t in targets_xy], dtype=np.float64)

        reg_matrix = reg_lambda * np.eye(6)
        reg_matrix[0, 0] = 0.0
        
        try:
            A = Phi.T @ Phi + reg_matrix
            self.weights_x = np.linalg.solve(A, Phi.T @ targets_x)
            self.weights_y = np.linalg.solve(A, Phi.T @ targets_y)
            self.is_calibrated = True
            self.save_profile()
            return True
        except Exception as e:
            print(f"[CALIBRATION] Fit error: {e}")
            return False

    def predict(self, u, v):
        if self.is_calibrated and self.weights_x is not None:
            feat = self._build_features(u, v)
            px = float(np.dot(feat, self.weights_x))
            py = float(np.dot(feat, self.weights_y))
        else:
            du = (u - self.center_u) * self.gain_x
            dv = (v - self.center_v) * self.gain_y
            px = (0.5 + du) * self.screen_w
            py = (0.5 + dv) * self.screen_h

        px = max(5.0, min(self.screen_w - 5.0, px))
        py = max(5.0, min(self.screen_h - 5.0, py))
        return px, py

    def save_profile(self):
        try:
            data = {
                "is_calibrated": self.is_calibrated,
                "weights_x": self.weights_x.tolist() if self.weights_x is not None else None,
                "weights_y": self.weights_y.tolist() if self.weights_y is not None else None,
                "center_u": self.center_u, "center_v": self.center_v,
                "screen_w": self.screen_w, "screen_h": self.screen_h
            }
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def load_profile(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    data = json.load(f)
                if data.get("is_calibrated") and data.get("weights_x"):
                    self.weights_x = np.array(data["weights_x"], dtype=np.float64)
                    self.weights_y = np.array(data["weights_y"], dtype=np.float64)
                    self.center_u = data.get("center_u", 0.0)
                    self.center_v = data.get("center_v", 0.0)
                    self.is_calibrated = True
            except Exception:
                pass


class InteractiveCalibrator:
    CALIBRATION_POINTS = [
        ("CENTER", 0.50, 0.50),
        ("TOP-LEFT", 0.12, 0.12),
        ("TOP-RIGHT", 0.88, 0.12),
        ("BOTTOM-RIGHT", 0.88, 0.88),
        ("BOTTOM-LEFT", 0.12, 0.88),
    ]

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.point_idx = 0
        self.point_start_time = None
        self.point_duration = 1.8
        self.collected_samples = []
        self.target_points = []
        self.current_point_samples = []
        self.is_active = False

    def start(self):
        self.point_idx = 0
        self.point_start_time = time.time()
        self.collected_samples = []
        self.target_points = []
        self.current_point_samples = []
        self.is_active = True

    def update(self, current_uv):
        if not self.is_active or self.point_idx >= len(self.CALIBRATION_POINTS):
            return True, None

        curr_time = time.time()
        elapsed = curr_time - self.point_start_time
        name, nx, ny = self.CALIBRATION_POINTS[self.point_idx]
        target_x = int(nx * self.screen_w)
        target_y = int(ny * self.screen_h)

        if elapsed > 0.4:
            self.current_point_samples.append(current_uv)

        canvas = np.zeros((self.screen_h, self.screen_w, 3), dtype=np.uint8)
        canvas[:] = (18, 18, 22)

        cv2.putText(canvas, "PRECISION EYE CALIBRATION", (self.screen_w // 2 - 250, 60),
                    cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 220, 255), 2)
        cv2.putText(canvas, f"Focus your eyes on the target: [{self.point_idx + 1}/5 - {name}]", 
                    (self.screen_w // 2 - 300, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        progress = min(1.0, elapsed / self.point_duration)
        radius = int(35 * (1.0 - progress * 0.65) + 6)
        
        cv2.circle(canvas, (target_x, target_y), radius + 8, (0, 120, 255), 2)
        cv2.circle(canvas, (target_x, target_y), radius, (0, 255, 255), -1)
        cv2.circle(canvas, (target_x, target_y), 3, (255, 255, 255), -1)

        if elapsed >= self.point_duration:
            if self.current_point_samples:
                avg_u = float(np.mean([s[0] for s in self.current_point_samples]))
                avg_v = float(np.mean([s[1] for s in self.current_point_samples]))
                self.collected_samples.append((avg_u, avg_v))
                self.target_points.append((target_x, target_y))

            self.point_idx += 1
            self.current_point_samples = []
            self.point_start_time = curr_time

            if self.point_idx >= len(self.CALIBRATION_POINTS):
                self.is_active = False
                return True, canvas

        return False, canvas

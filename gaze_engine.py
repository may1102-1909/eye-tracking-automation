"""
3D Head Pose & Dual Iris Gaze Estimation Engine
===============================================
1. 3D Head Pose (Yaw, Pitch, Roll) via Perspective-n-Point (solvePnP).
2. Sub-pixel Pupil/Iris relative offset within eye socket.
3. Fused High-Dimensional Gaze Feature Vector.
"""

import math
import numpy as np
import cv2

class GazeEngine:
    MODEL_POINTS_3D = np.array([
        (0.0, 0.0, 0.0),             # Nose tip
        (0.0, -330.0, -65.0),        # Chin
        (-225.0, 170.0, -135.0),     # Left eye corner
        (225.0, 170.0, -135.0),      # Right eye corner
        (-150.0, -150.0, -125.0),    # Left mouth corner
        (150.0, -150.0, -125.0)      # Right mouth corner
    ], dtype=np.float64)

    def __init__(self, frame_w=640, frame_h=480):
        self.w = frame_w
        self.h = frame_h
        focal_length = self.w
        center = (self.w / 2.0, self.h / 2.0)
        self.camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        self.dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    def extract_features(self, landmarks):
        w, h = self.w, self.h

        # 2D Points for solvePnP
        image_points = np.array([
            (landmarks[1].x * w, landmarks[1].y * h),
            (landmarks[152].x * w, landmarks[152].y * h),
            (landmarks[33].x * w, landmarks[33].y * h),
            (landmarks[263].x * w, landmarks[263].y * h),
            (landmarks[61].x * w, landmarks[61].y * h),
            (landmarks[291].x * w, landmarks[291].y * h)
        ], dtype=np.float64)

        success, rvec, tvec = cv2.solvePnP(
            self.MODEL_POINTS_3D, image_points, 
            self.camera_matrix, self.dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
        )

        yaw, pitch, roll = 0.0, 0.0, 0.0
        if success:
            rot_mat, _ = cv2.Rodrigues(rvec)
            sy = math.sqrt(rot_mat[0, 0]**2 + rot_mat[1, 0]**2)
            if sy >= 1e-6:
                pitch = math.atan2(rot_mat[2, 1], rot_mat[2, 2])
                yaw = math.atan2(-rot_mat[2, 0], sy)
                roll = math.atan2(rot_mat[1, 0], rot_mat[0, 0])
            else:
                pitch = math.atan2(-rot_mat[1, 2], rot_mat[1, 1])
                yaw = math.atan2(-rot_mat[2, 0], sy)
                roll = 0.0

            pitch, yaw, roll = math.degrees(pitch), math.degrees(yaw), math.degrees(roll)

        # Dual Iris Socket Normalization
        l_out = np.array([landmarks[33].x, landmarks[33].y])
        l_in = np.array([landmarks[133].x, landmarks[133].y])
        l_iris = np.array([landmarks[468].x, landmarks[468].y])
        l_width = np.linalg.norm(l_in - l_out)
        
        r_out = np.array([landmarks[263].x, landmarks[263].y])
        r_in = np.array([landmarks[362].x, landmarks[362].y])
        r_iris = np.array([landmarks[473].x, landmarks[473].y])
        r_width = np.linalg.norm(r_in - r_out)

        gaze_x, gaze_y = 0.0, 0.0
        if l_width > 1e-5 and r_width > 1e-5:
            l_ratio_x = (l_iris[0] - l_out[0]) / l_width
            l_ratio_y = (l_iris[1] - l_out[1]) / l_width
            r_ratio_x = (r_iris[0] - r_in[0]) / r_width
            r_ratio_y = (r_iris[1] - r_in[1]) / r_width
            gaze_x = (l_ratio_x + r_ratio_x) / 2.0
            gaze_y = (l_ratio_y + r_ratio_y) / 2.0

        # Fused Feature Vector (Head Pose + Iris Gaze)
        nose_norm_x = landmarks[1].x
        nose_norm_y = landmarks[1].y
        u = (nose_norm_x - 0.5) * 1.5 + (gaze_x - 0.45) * 0.8
        v = (nose_norm_y - 0.5) * 1.5 + (gaze_y - 0.18) * 0.8

        return (u, v), (yaw, pitch, roll), (gaze_x, gaze_y), image_points

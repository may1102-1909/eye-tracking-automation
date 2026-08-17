"""
High-Precision Signal Processing & Filtering Module
===================================================
1. One-Euro Filter (1€ Filter) for zero-lag, jitter-free cursor motion.
2. Saccade vs Fixation Classifier (Smart UI target locking).
"""

import math
import time
import numpy as np


class LowPassFilter:
    def __init__(self, alpha):
        self.set_alpha(alpha)
        self.y = None
        self.s = None

    def set_alpha(self, alpha):
        self.alpha = max(1e-4, min(1.0, float(alpha)))

    def __call__(self, value, alpha=None):
        if alpha is not None:
            self.set_alpha(alpha)
        if self.s is None:
            self.s = float(value)
        else:
            self.s = self.alpha * float(value) + (1.0 - self.alpha) * self.s
        self.y = float(value)
        return self.s

    def last_value(self):
        return self.y


class OneEuroFilter:
    """Industrial 1€ Filter (Casiez et al., CHI 2012)."""
    def __init__(self, min_cutoff=0.85, beta=0.015, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filter = LowPassFilter(self._alpha(min_cutoff, 1.0 / 30.0))
        self.dx_filter = LowPassFilter(self._alpha(d_cutoff, 1.0 / 30.0))
        self.last_time = None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        if self.last_time is None:
            self.last_time = timestamp
            return self.x_filter(x)
            
        dt = max(1e-4, timestamp - self.last_time)
        self.last_time = timestamp

        prev_x = self.x_filter.last_value()
        dx = 0.0 if prev_x is None else (x - prev_x) / dt
        edx = self.dx_filter(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter(x, self._alpha(cutoff, dt))

    def reset(self):
        self.x_filter.s = None
        self.x_filter.y = None
        self.dx_filter.s = None
        self.dx_filter.y = None
        self.last_time = None


class Point2DOneEuroFilter:
    """2D wrapper for (X, Y) cursor tracking."""
    def __init__(self, min_cutoff=0.85, beta=0.015, d_cutoff=1.0):
        self.fx = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.fy = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def filter(self, x, y, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        return self.fx.filter(x, timestamp), self.fy.filter(y, timestamp)


class SaccadeFixationManager:
    """Classifies rapid eye saccades vs fixations and stabilizes targets."""
    def __init__(self, velocity_threshold=180.0, fixation_duration=0.12):
        self.velocity_thresh = velocity_threshold
        self.fixation_duration = fixation_duration
        self.prev_pos = None
        self.prev_time = None
        self.fixation_start = None
        self.is_fixating = False
        self.anchor_pos = None

    def update(self, x, y, curr_time=None):
        if curr_time is None:
            curr_time = time.time()

        if self.prev_pos is None or self.prev_time is None:
            self.prev_pos = (x, y)
            self.prev_time = curr_time
            return x, y, False

        dt = max(1e-4, curr_time - self.prev_time)
        dist = math.hypot(x - self.prev_pos[0], y - self.prev_pos[1])
        velocity = dist / dt

        self.prev_pos = (x, y)
        self.prev_time = curr_time

        if velocity > self.velocity_thresh:
            self.is_fixating = False
            self.fixation_start = None
            self.anchor_pos = None
            return x, y, False

        if self.fixation_start is None:
            self.fixation_start = curr_time
            self.anchor_pos = (x, y)
        elif curr_time - self.fixation_start >= self.fixation_duration:
            self.is_fixating = True
            anchor_dist = math.hypot(x - self.anchor_pos[0], y - self.anchor_pos[1])
            if anchor_dist < 45.0:
                out_x = self.anchor_pos[0] * 0.75 + x * 0.25
                out_y = self.anchor_pos[1] * 0.75 + y * 0.25
                return out_x, out_y, True
            else:
                self.anchor_pos = (x, y)

        return x, y, self.is_fixating

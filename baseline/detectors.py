"""
detectors.py — Baseline phát hiện: static threshold (B1) và EWMA (adaptive).

Cả hai nhận một chuỗi giá trị của MỘT feature (thường packet_rate) và trả về
nhãn attack/benign mỗi window. Đây là baseline để so với ML; mục tiêu là cho
thấy threshold tĩnh gây false positive khi có Flash Crowd (RQ2).

Thuần Python, test offline được.
"""
import math


class StaticThreshold:
    """B1: alarm khi x > threshold.

    Cách chọn threshold công bằng: lấy từ dữ liệu Normal, ví dụ phân vị 99
    nhân hệ số k (xem fit_from_normal). KHÔNG chọn thấp để cố tình thắng.
    """

    def __init__(self, threshold):
        self.threshold = threshold

    @classmethod
    def fit_from_normal(cls, normal_values, pct=99, k=1.0):
        xs = sorted(normal_values)
        if not xs:
            return cls(float("inf"))
        idx = min(len(xs) - 1, int(round((pct / 100.0) * (len(xs) - 1))))
        return cls(xs[idx] * k)

    def predict(self, x):
        return 1 if x > self.threshold else 0

    def predict_series(self, values):
        return [self.predict(x) for x in values]


class EWMA:
    """Adaptive threshold bằng EWMA: alarm khi x > mu + k*sigma.

    mu_t   = a*x + (1-a)*mu_{t-1}
    var_t  = a*(x-mu_t)^2 + (1-a)*var_{t-1}
    Cập nhật mu/var CHỈ khi không alarm (hoặc có warmup) để attack không kéo
    baseline lên theo nó.
    """

    def __init__(self, alpha=0.2, k=3.0, warmup=10):
        self.alpha = alpha
        self.k = k
        self.warmup = warmup
        self.mu = None
        self.var = 0.0
        self.n = 0

    def predict(self, x):
        self.n += 1
        if self.mu is None:
            self.mu = x
            return 0
        thresh = self.mu + self.k * math.sqrt(max(self.var, 0.0))
        alarm = 1 if (self.n > self.warmup and x > thresh) else 0
        # chỉ cập nhật baseline khi bình thường, hoặc trong warmup
        if alarm == 0 or self.n <= self.warmup:
            new_mu = self.alpha * x + (1 - self.alpha) * self.mu
            self.var = self.alpha * (x - new_mu) ** 2 + (1 - self.alpha) * self.var
            self.mu = new_mu
        return alarm

    def predict_series(self, values):
        return [self.predict(x) for x in values]

"""QR code detection using OpenCV's built-in QR detector.

The detector runs on frames coming from the camera abstraction. It returns the
decoded payload strings found in a frame (typically a user id like "CLUB-123").
"""

import cv2


class QRReader:
    def __init__(self):
        self._detector = cv2.QRCodeDetector()

    def detect(self, frame):
        """Return a list of decoded payload strings found in the frame."""
        if frame is None:
            return []
        result = self._detector.detectAndDecodeMulti(frame)
        # OpenCV 4:  (decoded_info, points, straight_qrcode)
        # OpenCV 5:  (retval, decoded_info, straight_qrcode, points)
        if not isinstance(result, (list, tuple)) or len(result) < 3:
            return []
        if isinstance(result[0], bool):
            # OpenCV 5 form: (ok, decoded, straight, points)
            ok, data, _, _ = result[:4]
            if not ok or data is None:
                return []
            return [d for d in data if d]
        data, _points, _straight = result[:3]
        if data is None:
            return []
        return [d for d in data if d]


def decode_qr_image(image_path):
    """Utility: decode all QR payloads from a still image file (for tests)."""
    frame = cv2.imread(str(image_path))
    if frame is None:
        return []
    return QRReader().detect(frame)
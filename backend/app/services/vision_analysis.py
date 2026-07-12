"""
Phase 4 — per-frame webcam analysis: eye contact, facial expression, posture.

Design choice worth calling out: this analyzes individual sampled frames
(the frontend should POST one frame every ~1-2 seconds while the candidate
is answering), not a continuous video stream. Piping full-motion video
through a Python backend for MediaPipe processing would be both a latency
and bandwidth problem; periodic sampling is what keeps this responsive.

Like the Phase 3 voice-confidence heuristic, the expression and posture
scores here are geometry-based heuristics on MediaPipe landmarks, not a
trained emotion/posture classifier. That's a deliberate scope choice for a
first pass — a real emotion classifier (trained CNN) or a proper posture
model would be a natural upgrade later, but these heuristics give a
reasonable, fast, dependency-light signal without needing a second ML
model or GPU.

Models are loaded once as module-level singletons since MediaPipe's model
init cost is significant relative to per-frame inference.
"""
import numpy as np
import cv2
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh
mp_pose = mp.solutions.pose

_face_mesh = None
_pose = None


def _get_face_mesh():
    global _face_mesh
    if _face_mesh is None:
        _face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,  # needed for iris landmarks (gaze estimate)
            min_detection_confidence=0.5,
        )
    return _face_mesh


def _get_pose():
    global _pose
    if _pose is None:
        _pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
    return _pose


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _eye_contact_score(landmarks) -> float:
    """
    Approximates gaze direction from iris position relative to eye corners.
    Iris centered between the corners (both horizontally and vertically) ->
    looking roughly at the camera -> high score. Iris skewed toward one
    corner -> looking away -> lower score. This is a proxy for "looking at
    the camera", not precise gaze-angle tracking.
    """
    def axis_score(iris_idx, corner_a_idx, corner_b_idx, coord):
        iris = getattr(landmarks[iris_idx], coord)
        a = getattr(landmarks[corner_a_idx], coord)
        b = getattr(landmarks[corner_b_idx], coord)
        lo, hi = min(a, b), max(a, b)
        span = hi - lo
        if span < 1e-6:
            return 100.0
        ratio = (iris - lo) / span  # 0..1, 0.5 = centered
        return _clip(100.0 - abs(ratio - 0.5) * 200.0)

    # Left eye: outer corner 33, inner corner 133, iris center 468
    # Right eye: inner corner 362, outer corner 263, iris center 473
    left_h = axis_score(468, 33, 133, "x")
    right_h = axis_score(473, 362, 263, "x")

    # Vertical: upper/lower lid landmarks per eye
    left_v = axis_score(468, 159, 145, "y")
    right_v = axis_score(473, 386, 374, "y")

    return round((left_h + right_h + left_v + right_v) / 4.0, 1)


def _facial_expression_score(landmarks) -> float:
    """
    Heuristic "engaged/positive expression" score based on mouth geometry:
    wider mouth relative to face width plus lip corners raised above the
    midline reads as a slight smile/engagement. Baseline of 60 represents
    a neutral, attentive expression rather than penalizing a straight face.
    """
    # Face width proxy: left cheek (234) to right cheek (454)
    face_width = abs(landmarks[454].x - landmarks[234].x)
    if face_width < 1e-6:
        return 60.0

    left_corner, right_corner = landmarks[61], landmarks[291]
    upper_lip, lower_lip = landmarks[13], landmarks[14]

    mouth_width = abs(right_corner.x - left_corner.x)
    width_ratio = mouth_width / face_width  # ~0.35-0.5 typical, higher = wider

    lip_midline_y = (upper_lip.y + lower_lip.y) / 2.0
    corner_y = (left_corner.y + right_corner.y) / 2.0
    # In image coords, smaller y = higher up. Corners above the midline = smile.
    smile_lift = (lip_midline_y - corner_y) / face_width

    score = 60.0 + (width_ratio - 0.4) * 150.0 + smile_lift * 400.0
    return round(_clip(score), 1)


def _posture_score(pose_landmarks) -> float:
    """
    Heuristic posture score from shoulder/hip alignment:
      - shoulder tilt (uneven shoulders) penalized
      - forward/slouched lean, approximated by how much the shoulder
        midpoint is vertically compressed toward the hip midpoint relative
        to shoulder width, penalized
    Assumes the candidate is roughly upper-body-framed and facing the
    camera, as in a typical webcam interview setup.
    """
    lm = pose_landmarks
    l_sh, r_sh = lm[11], lm[12]
    l_hip, r_hip = lm[23], lm[24]

    shoulder_width = abs(r_sh.x - l_sh.x)
    if shoulder_width < 1e-6:
        return 60.0

    tilt = abs(l_sh.y - r_sh.y) / shoulder_width
    tilt_penalty = min(tilt * 200.0, 40.0)

    shoulder_mid_y = (l_sh.y + r_sh.y) / 2.0
    hip_mid_y = (l_hip.y + r_hip.y) / 2.0
    torso_span = abs(hip_mid_y - shoulder_mid_y)
    # A compressed torso span (relative to shoulder width) suggests
    # slouching/leaning in close rather than sitting upright.
    expected_span = shoulder_width * 1.0
    slouch_ratio = torso_span / expected_span if expected_span > 1e-6 else 1.0
    slouch_penalty = min(max(1.0 - slouch_ratio, 0.0) * 60.0, 30.0)

    return round(_clip(100.0 - tilt_penalty - slouch_penalty), 1)


def analyze_frame(image_bytes: bytes) -> dict:
    """
    Analyzes a single webcam frame. Returns:
      {
        "face_detected": bool,
        "eye_contact_score": float | None,
        "facial_expression_score": float | None,
        "posture_score": float | None,   # None if pose/shoulders not visible
      }
    Scores are None (not zero) when the relevant landmarks weren't
    detected, so averaging later doesn't get dragged down by frames where
    the candidate briefly stepped out of frame.
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        return {
            "face_detected": False,
            "eye_contact_score": None,
            "facial_expression_score": None,
            "posture_score": None,
        }

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    face_result = _get_face_mesh().process(rgb)
    face_detected = bool(face_result.multi_face_landmarks)

    eye_contact_score = None
    facial_expression_score = None
    if face_detected:
        landmarks = face_result.multi_face_landmarks[0].landmark
        eye_contact_score = _eye_contact_score(landmarks)
        facial_expression_score = _facial_expression_score(landmarks)

    pose_result = _get_pose().process(rgb)
    posture_score = None
    if pose_result.pose_landmarks:
        posture_score = _posture_score(pose_result.pose_landmarks.landmark)

    return {
        "face_detected": face_detected,
        "eye_contact_score": eye_contact_score,
        "facial_expression_score": facial_expression_score,
        "posture_score": posture_score,
    }

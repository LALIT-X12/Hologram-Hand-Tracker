"""JARVIS Holographic Hand Control — webcam/MediaPipe backend."""
import asyncio
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
HTTP_HOST, HTTP_PORT = "127.0.0.1", 8000
WS_HOST, WS_PORT = "127.0.0.1", 8765

state_lock = threading.Lock()
latest_jpeg = None
latest_state = {"hands": [], "hand_count": 0, "timestamp": 0.0}


class WebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_GET(self):
        if self.path == "/video_feed":
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with state_lock:
                        frame = latest_jpeg
                    if frame:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                    time.sleep(0.04)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, *_args):
        pass


def start_http():
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), WebHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[JARVIS] Interface: http://{HTTP_HOST}:{HTTP_PORT}")


def finger_up(lm, tip, pip):
    return lm[tip].y < lm[pip].y


def detect_gesture(lm):
    # Distances use normalized image coordinates; thresholds are deliberately forgiving.
    pinch_dist = np.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
    if pinch_dist < 0.055:
        return "PINCH"
    index = finger_up(lm, 8, 6)
    middle = finger_up(lm, 12, 10)
    ring = finger_up(lm, 16, 14)
    pinky = finger_up(lm, 20, 18)
    if index and not middle and not ring and not pinky:
        return "POINT"
    if index and middle and ring and pinky:
        return "OPEN PALM"
    if not index and not middle and not ring and not pinky:
        return "FIST"
    return "TRACKING"


async def ws_handler(websocket):
    # Compatible with the one-argument handler API used by modern websockets releases.
    try:
        async for _message in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        pass


async def broadcast_loop(clients):
    while True:
        with state_lock:
            payload = json.dumps(latest_state)
        dead = []
        for client in tuple(clients):
            try:
                await client.send(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            clients.discard(client)
        await asyncio.sleep(1 / 30)


async def client_handler(websocket, clients):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.discard(websocket)


async def run_camera():
    global latest_jpeg, latest_state
    start_http()
    clients = set()
    ws_server = await websockets.serve(lambda ws: client_handler(ws, clients), WS_HOST, WS_PORT)
    # IMPORTANT: start the broadcaster so browser clients receive live hand state.
    broadcaster = asyncio.create_task(broadcast_loop(clients))
    print(f"[JARVIS] Hand data socket: ws://{WS_HOST}:{WS_PORT}")
    print("[JARVIS] Broadcasting live hand data to the holographic interface.")
    print("[JARVIS] Press Q in the camera preview or Ctrl+C here to stop.")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        ws_server.close()
        await ws_server.wait_closed()
        raise RuntimeError("Could not open webcam. Close other apps using the camera and try again.")
    # Lower capture resolution and buffer size for better real-time latency.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    previous_wrist_x = None
    previous_wrist_t = time.time()
    last_swipe_t = 0.0
    last_preview_encode_t = 0.0

    try:
        with mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                            model_complexity=0, min_detection_confidence=0.55,
                            min_tracking_confidence=0.55) as hands_model:
            while True:
                ok, frame = cap.read()
                if not ok:
                    await asyncio.sleep(0.02)
                    continue
                # Mirror the webcam like a selfie view.
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands_model.process(rgb)
                hands_out = []
                if results.multi_hand_landmarks:
                    for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                        lm = hand_lms.landmark
                        gesture = detect_gesture(lm)
                        points = [[round(float(p.x), 5), round(float(p.y), 5), round(float(p.z), 5)] for p in lm]
                        handed = "Hand"
                        if results.multi_handedness and idx < len(results.multi_handedness):
                            handed = results.multi_handedness[idx].classification[0].label
                        # The image is already mirrored; invert handedness label for display convention.
                        handed = "Left" if handed == "Right" else ("Right" if handed == "Left" else handed)
                        hands_out.append({"landmarks": points, "gesture": gesture, "handedness": handed,
                                          "palm": [round(float(lm[0].x), 5), round(float(lm[0].y), 5)],
                                          "pinch": round(float(np.hypot(lm[4].x-lm[8].x, lm[4].y-lm[8].y)), 5)})
                        mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                    # Simple swipe detection from the first detected wrist.
                    now = time.time()
                    wrist_x = hands_out[0]["landmarks"][0][0]
                    dt = max(now - previous_wrist_t, 0.001)
                    dx = wrist_x - previous_wrist_x if previous_wrist_x is not None else 0
                    if abs(dx) > 0.16 and dt < 0.45 and now - last_swipe_t > 0.9:
                        hands_out[0]["gesture"] = "SWIPE RIGHT" if dx > 0 else "SWIPE LEFT"
                        last_swipe_t = now
                    previous_wrist_x, previous_wrist_t = wrist_x, now
                else:
                    previous_wrist_x, previous_wrist_t = None, time.time()

                two_hand_distance = None
                if len(hands_out) >= 2:
                    p1, p2 = hands_out[0]["palm"], hands_out[1]["palm"]
                    two_hand_distance = round(float(np.hypot(p1[0]-p2[0], p1[1]-p2[1])), 5)

                # A tiny camera preview is useful for debugging, while the browser displays the full UI.
                for i, hand in enumerate(hands_out):
                    cv2.putText(frame, f"{hand['handedness']} | {hand['gesture']}", (18, 32 + i*30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 230, 50), 2, cv2.LINE_AA)
                # Encode the small camera-preview stream at ~15 FPS; hand data still updates every frame.
                now_preview = time.time()
                if now_preview - last_preview_encode_t >= 1 / 15:
                    ok_jpg, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                    if ok_jpg:
                        with state_lock:
                            latest_jpeg = jpg.tobytes()
                    last_preview_encode_t = now_preview
                with state_lock:
                    latest_state = {"hands": hands_out, "hand_count": len(hands_out),
                                    "two_hand_distance": two_hand_distance, "timestamp": time.time()}
                cv2.imshow("JARVIS Hand Tracking — press Q to close", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                await asyncio.sleep(0.001)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        broadcaster.cancel()
        try:
            await broadcaster
        except asyncio.CancelledError:
            pass
        ws_server.close()
        await ws_server.wait_closed()


def main():
    try:
        asyncio.run(run_camera())
    except KeyboardInterrupt:
        print("\n[JARVIS] Stopped.")
    except Exception as exc:
        print(f"\n[JARVIS ERROR] {exc}")
        print("Check that the virtual environment has the compatible packages and your webcam is available.")
        input("Press Enter to close...")


if __name__ == "__main__":
    main()

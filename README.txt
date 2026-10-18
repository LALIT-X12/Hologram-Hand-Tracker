JARVIS HOLOGRAPHIC HAND CONTROL — WINDOWS
========================================

This is an upgraded version of the project: a webcam/MediaPipe backend streams
hand landmarks to a Three.js holographic interface in your browser.

GESTURES
--------
- PINCH (thumb + index close): grab and drag the central hologram.
- POINT (index finger extended): steer/rotate the hologram.
- OPEN PALM: toggle the radial holographic control menu.
- SWIPE LEFT / SWIPE RIGHT: switch the active HUD panel.
- TWO HANDS: move hands apart/together to zoom.
- Mouse drag and wheel are available as a fallback.

IMPORTANT FOR YOUR CURRENT PROJECT
---------------------------------
Your existing virtual environment appears to be in the parent folder:
  ..\.venv\Scripts\python.exe
This project ZIP contains updated backend/main.py and frontend/index.html.
Extract this ZIP and copy/replace those two files in your existing inner
jarvis_hand_interface folder, keeping its current .venv folder untouched.
Or use the extracted project as a standalone folder and create its own .venv.

START USING YOUR EXISTING ENVIRONMENT
-------------------------------------
1. Extract the ZIP.
2. Copy backend\main.py and frontend\index.html into your existing project,
   replacing the files with the same names.
3. In VS Code terminal, change to the inner project folder (the folder that
   contains backend and frontend), then run:

   & "..\.venv\Scripts\python.exe" -m pip uninstall -y opencv-python
   & "..\.venv\Scripts\python.exe" -m pip install mediapipe==0.10.21 numpy==1.26.4 opencv-contrib-python==4.11.0.86 websockets==12.0

4. Start the backend:

   & "..\.venv\Scripts\python.exe" backend\main.py

5. Open http://127.0.0.1:8000 in Chrome or Edge.
6. Keep the terminal running. The backend opens a camera preview window too.
   Press Q in that preview or Ctrl+C in the terminal to stop.

STANDALONE SETUP
----------------
If using this extracted folder independently:
  py -3.11 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe backend\main.py

Then open http://127.0.0.1:8000.

TROUBLESHOOTING
---------------
- If the camera cannot open, close Zoom/Teams/Camera and retry.
- If the page says the hand-data socket is offline, make sure backend/main.py
  is still running and port 8765 is not blocked.
- Three.js loads from a CDN, so the browser needs internet access on first load.
- The browser UI is a screen-based 3D simulation, not a physical projector.

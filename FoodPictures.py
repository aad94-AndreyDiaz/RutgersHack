from flask import Flask, request, jsonify, send_from_directory
import cv2
import numpy as np
import base64

app = Flask(__name__, static_folder='static')

# ─── HARDCODED FOOD DATABASE ──────────────────────────────
FOOD_DB = [
    {
        "name":      "Grilled Chicken",
        "hue_range": (10, 20),
        "sat_min":   50,
        "calories":  165,
        "nutrition": "This is a healthy meal!"
    },
    {
        "name":      "Cookie",
        "hue_range": (12, 28),
        "sat_min":   30,
        "calories":  148,
        "nutrition": "This is not a meal!"
    },
    
    {
        "name":      "Steak",
        "hue_range": (0, 15),
        "sat_min":   30,
        "calories":  271,
        "nutrition": "This is a healthy meal!"
    }
]

# ─── CLASSIFIER ───────────────────────────────────────────
def classify_food(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    scores = []
    for food in FOOD_DB:
        lo, hi  = food["hue_range"]
        sat_min = food["sat_min"]
        mask        = cv2.inRange(hsv, (lo, sat_min, 30), (hi, 255, 255))
        pixel_count = cv2.countNonZero(mask)
        scores.append((pixel_count, food))
    scores.sort(key=lambda x: x[0], reverse=True)
    best_count, best_food = scores[0]
    total_pixels = frame.shape[0] * frame.shape[1]
    confidence   = min(best_count / max(total_pixels * 0.3, 1), 1.0)
    return best_food, confidence

# ─── ROUTES ───────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/scan', methods=['POST'])
def scan():
    data = request.json.get('image', '')
    # strip data URL header
    if ',' in data:
        data = data.split(',')[1]

    img_bytes = base64.b64decode(data)
    np_arr    = np.frombuffer(img_bytes, np.uint8)
    frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "Could not decode image"}), 400

    food, confidence = classify_food(frame)

    return jsonify({
        "name":       food["name"],
        "confidence": round(confidence * 100),
        "nutrition":  food["nutrition"],
        "calories":   food["calories"]
    })

if __name__ == '__main__':
    # host=0.0.0.0 makes it reachable from your phone on the same WiFi
    app.run(host='0.0.0.0', port=5000, debug=True)
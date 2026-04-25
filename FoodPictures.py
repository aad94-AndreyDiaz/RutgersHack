from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import cv2
import numpy as np
import base64
import json
import re
import requests
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

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
    return send_from_directory('static', 'dashboard.html')

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

# ─── GROQ / OPTIMIZER ────────────────────────────────────
GROQ_API_KEY = "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"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

def sleep_score(h):
    if h < 4:  return 0.1
    if h < 6:  return 0.1 + 0.15*(h-4)
    if h < 8:  return 0.4 + 0.25*(h-6)
    if h <= 9: return 0.9
    return 0.9 - 0.1*(h-9)

def burnout_engine_simple(data):
    sleep_penalty = 0.85 if (data["sleep_hours"] < 6 and 2 <= data.get("bedtime_hour",0) <= 6) else 1.0
    S = sleep_score(data["sleep_hours"]) * sleep_penalty
    W = min(1, data["water_glasses"]/8)
    B = min(1, data["break_minutes"]/60)
    E = (5 - data["mood"])/4
    F = min(1, data["free_time_minutes"]/60)
    tasks = data.get("tasks", [])
    tl = sum(1 for t in tasks if not t["done"])/len(tasks) if tasks else 0
    C = min(1, 0.5*(data["calendar_hours"]/10) + 0.5*tl)
    score = 100*(0.30*(1-S)+0.14*(1-W)+0.20*C+0.18*E+0.10*(1-B)+0.08*(1-F))
    issues = []
    if S < 0.75: issues.append("sleep_risk")
    if W < 0.7:  issues.append("hydration_drift")
    if B < 0.6:  issues.append("recovery_debt")
    if E > 0.45: issues.append("emotional_pressure")
    if C > 0.5:  issues.append("work_accumulation")
    if F < 0.6:  issues.append("buffer_loss")
    return round(score, 2), issues, {"sleep":S,"water":W,"break":B,"mood_strain":E,"free":F,"cognitive":C}

@app.route('/optimize', methods=['POST'])
def optimize():
    data = request.json
    score, issues, breakdown = burnout_engine_simple(data)
    intensity = 0.9 if score>75 else 0.65 if score>55 else 0.45 if score>35 else 0.25
    system_prompt = """You are a behavioral load optimizer that prevents burnout.
Return ONLY valid JSON:
{
  "summary": "...",
  "priority_actions": {"now": ["..."], "next": ["..."], "tonight": ["..."]},
  "risk_note": "..."
}
Max 5 actions total. Every action must include a number (time/quantity). No vague advice."""

    payload = {"burnout_score": score, "breakdown": breakdown, "issues": issues, "intensity": intensity}
    try:
        resp = requests.post(GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role":"system","content":system_prompt},
                                {"role":"user","content":json.dumps(payload)}],
                  "temperature": 0.3},
            timeout=15)
        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        llm_output = json.loads(content)
    except Exception as e:
        llm_output = {"summary": f"LLM error: {e}", "priority_actions":{"now":[],"next":[],"tonight":[]},"risk_note":""}

    stage = ("early_alert" if score>75 else "rising_load" if score>55 else
             "balanced_adjustment" if score>35 else "stable")
    return jsonify({"burnout_score": score, "stage": stage, "llm_output": llm_output})


# ─── SCHEDULE BUILDER ────────────────────────────────────

SCHEDULE_SYSTEM_PROMPT = """
You are a deterministic scheduling engine.
Return ONLY valid JSON — no markdown, no explanation.

Rules:
- Use ONLY provided free blocks
- Do NOT modify calendar events
- Fill free time with tasks or breaks
- If burnout > 70: reduce workload heavily, prioritise rest
- If burnout > 60: insert 10-15 min breaks between tasks
- No overlaps allowed

Output format:
{
  "schedule": [
    { "start": "HH:MM", "end": "HH:MM", "title": "string", "type": "task|break|idle" }
  ]
}
"""

def to_min(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m

def to_time(m):
    return f"{m//60:02d}:{m%60:02d}"

def build_fixed_events():
    return [
        {"name": "Outwater Basketball", "start": "07:00", "end": "09:00"},
        {"name": "Cabinet Meeting",      "start": "09:00", "end": "09:30"},
        {"name": "CS288",                "start": "11:30", "end": "12:50"},
        {"name": "Common Hour",          "start": "11:30", "end": "13:00"},
        {"name": "E-Board Meeting",      "start": "11:30", "end": "13:00"},
        {"name": "YWCC Class",           "start": "13:00", "end": "14:20"},
        {"name": "CS Generative AI",     "start": "16:00", "end": "17:20"},
    ]

def compute_free_blocks(events):
    events = sorted(events, key=lambda x: to_min(x["start"]))
    start_day, end_day = 6 * 60, 23 * 60
    free = []
    cur = start_day
    for e in events:
        s, t = to_min(e["start"]), to_min(e["end"])
        if s > cur:
            free.append({"start": to_time(cur), "end": to_time(s)})
        cur = max(cur, t)
    if cur < end_day:
        free.append({"start": to_time(cur), "end": to_time(end_day)})
    return free

@app.route('/build-schedule', methods=['POST'])
def build_schedule():
    data = request.json
    score, issues, breakdown = burnout_engine_simple(data)
    events = build_fixed_events()
    free_blocks = compute_free_blocks(events)

    payload = {
        "burnout": score,
        "tasks": [t["name"] if isinstance(t, dict) else t for t in data.get("tasks", [])],
        "free_blocks": free_blocks
    }

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": SCHEDULE_SYSTEM_PROMPT},
                    {"role": "user",   "content": json.dumps(payload)}
                ],
                "temperature": 0.2
            },
            timeout=20
        )
        body = resp.json()
        if "choices" not in body:
            raise RuntimeError(f"Groq error: {json.dumps(body)}")
        raw = body["choices"][0]["message"]["content"]
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        plan = json.loads(raw)
    except Exception as e:
        plan = {"schedule": []}
        print(f"Schedule LLM error: {e}")

    return jsonify({"burnout": score, "plan": plan})

@app.route('/export-ics', methods=['POST'])
def export_ics_route():
    schedule = request.json.get("schedule", [])
    now = datetime(2026, 4, 25)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CalmCore//EN"]
    for i, item in enumerate(schedule):
        try:
            sh, sm = map(int, item["start"].split(":"))
            eh, em = map(int, item["end"].split(":"))
            lines += [
                "BEGIN:VEVENT",
                f"UID:{i}@calmcore",
                f"DTSTART:{now.strftime('%Y%m%d')}T{sh:02d}{sm:02d}00",
                f"DTEND:{now.strftime('%Y%m%d')}T{eh:02d}{em:02d}00",
                f"SUMMARY:{item.get('title', 'Task')}",
                "END:VEVENT"
            ]
        except Exception:
            continue
    lines.append("END:VCALENDAR")
    filepath = "generated_schedule.ics"
    with open(filepath, "w") as f:
        f.write("\r\n".join(lines))
    return send_file(filepath, as_attachment=True)

if __name__ == '__main__':
    # host=0.0.0.0 makes it reachable from your phone on the same WiFi
    app.run(host='0.0.0.0', port=5000, debug=True)

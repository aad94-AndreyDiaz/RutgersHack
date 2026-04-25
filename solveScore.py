import json
import requests
import math

# =========================================================
# STATE MEMORY
# =========================================================
state_memory = {
    "sleep": [],
    "water": [],
    "breaks": [],
    "burnout_history": []
}

# =========================================================
# CORE SCORING
# =========================================================
def sleep_score(h): return min(1.0, max(0.1, h / 8))
def water_score(g): return min(1.0, g / 8)
def break_score(m): return min(1.0, m / 60)
def emotional_strain(m): return (5 - m) / 4
def free_time_score(t): return min(1.0, t / 60)

def cognitive_load(data):
    if not data["tasks"]:
        return 0.0
    unfinished = sum(1 for t in data["tasks"] if not t["done"])
    return min(1.0,
        0.5 * (data["calendar_hours"] / 10) +
        0.5 * (unfinished / len(data["tasks"]))
    )

# =========================================================
# SLEEP CONTEXT INFERENCE
# =========================================================
def sleep_context(hours, bedtime=None):

    context = {
        "short_sleep": hours < 6,
        "healthy_range": 6 <= hours <= 8,
        "late_sleep_flag": False,
        "sleep_quality_penalty": 1.0
    }

    if bedtime is not None:
        if 2 <= bedtime <= 6:
            context["late_sleep_flag"] = True

    if context["short_sleep"] and context["late_sleep_flag"]:
        context["sleep_quality_penalty"] = 0.85
    elif context["short_sleep"]:
        context["sleep_quality_penalty"] = 0.92
    elif context["late_sleep_flag"]:
        context["sleep_quality_penalty"] = 0.95

    return context

# =========================================================
# BURNOUT ENGINE
# =========================================================
def burnout_engine(data):

    sleep_ctx = sleep_context(
        data["sleep_hours"],
        data.get("bedtime_hour", None)
    )

    S = sleep_score(data["sleep_hours"]) * sleep_ctx["sleep_quality_penalty"]
    W = water_score(data["water_glasses"])
    B = break_score(data["break_minutes"])
    E = emotional_strain(data["mood"])
    F = free_time_score(data["free_time_minutes"])
    C = cognitive_load(data)

    burnout = 100 * (
        0.30 * (1 - S) +
        0.14 * (1 - W) +
        0.20 * C +
        0.18 * E +
        0.10 * (1 - B) +
        0.08 * (1 - F)
    )

    return burnout, {
        "sleep_score": S,
        "water_score": W,
        "break_score": B,
        "emotional_strain": E,
        "free_time_score": F,
        "cognitive_load": C,
        "sleep_context": sleep_ctx
    }

# =========================================================
# WARNING SIGNALS
# =========================================================
def detect_weak_points(breakdown):

    issues = []

    if breakdown["sleep_score"] < 0.75:
        issues.append("sleep_risk")
    if breakdown["water_score"] < 0.7:
        issues.append("hydration_drift")
    if breakdown["break_score"] < 0.6:
        issues.append("recovery_debt")
    if breakdown["emotional_strain"] > 0.45:
        issues.append("emotional_pressure")
    if breakdown["cognitive_load"] > 0.5:
        issues.append("work_accumulation")
    if breakdown["free_time_score"] < 0.6:
        issues.append("buffer_loss")

    return issues

# =========================================================
# INTENSITY
# =========================================================
def adaptive_intensity(score):
    if score > 75: return 0.9
    if score > 55: return 0.65
    if score > 35: return 0.45
    return 0.25

# =========================================================
# LLM (GROQ API)
# =========================================================
GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def llm_generate(burnout_score, breakdown, issues, intensity):

    system_prompt = """
You are a behavioral load optimizer that prevents burnout before it happens.

Return ONLY valid JSON:
{
  "summary": "...",
  "priority_actions": {
    "now": ["..."],
    "next": ["..."],
    "tonight": ["..."]
  },
  "risk_note": "..."
}

STRICT RULES:
- max 5 total actions
- EVERY action must include a number (time, quantity, or limit)
- NO vague advice allowed
- NO abstract language (no "manage stress", "optimize", "reduce strain")

Each action must look like:
- "drink 500ml water now"
- "take 10 minute break"
- "finish 1 task then stop"
- "stop work by 11:30pm"
- "sleep at least 6.5 hours tonight"

Behavior logic:
- If sleep is low + late bedtime → enforce earlier cutoff + minimum sleep target
- If workload high → cap tasks (e.g. "do 2 tasks max next hour")
- If break time low → force timed breaks
- If cognitive load high → reduce task count, not just "pace yourself"

Time framing:
- now = next 5–30 min
- next = 1–6 hours
- tonight = sleep + shutdown rules

Goal:
Prevent burnout by controlling workload, not describing it.
"""

    payload = {
        "burnout_score": burnout_score,
        "breakdown": breakdown,
        "issues": issues,
        "intensity": intensity
    }

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload)}
            ],
            "temperature": 0.3
        }
    )

    content = response.json()["choices"][0]["message"]["content"]

    try:
        return json.loads(content)
    except:
        return {
            "summary": "Parse failure",
            "priority_actions": {"now": [], "next": [], "tonight": []},
            "risk_note": "fallback triggered"
        }

# =========================================================
# PIPELINE
# =========================================================
def calm_optimizer(data, state):

    burnout_score, breakdown = burnout_engine(data)

    issues = detect_weak_points(breakdown)

    intensity = adaptive_intensity(burnout_score)

    llm_output = llm_generate(
        round(burnout_score, 2),
        breakdown,
        issues,
        intensity
    )

    state["burnout_history"].append(burnout_score)

    return {
        "burnout_score": round(burnout_score, 2),
        "stage":
            "early_alert" if burnout_score > 75 else
            "rising_load" if burnout_score > 55 else
            "balanced_adjustment" if burnout_score > 35 else
            "stable",
        "intensity": intensity,
        "llm_output": llm_output,
        "trend": state["burnout_history"][-5:]
    }

# =========================================================
# TEST
# =========================================================
if __name__ == "__main__":

    data = {
        "sleep_hours": 5.2,
        "bedtime_hour": 4,
        "water_glasses": 3,
        "break_minutes": 10,
        "mood": 2,
        "free_time_minutes": 15,
        "calendar_hours": 9,
        "screen_time_hours": 8,
        "tasks": [
            {"name": "study", "done": False},
            {"name": "emails", "done": False},
            {"name": "gym", "done": True}
        ]
    }

    result = calm_optimizer(data, state_memory)

    print("\n=== PROACTIVE STRAIN MONITOR ===\n")
    print("Strain Score:", result["burnout_score"])
    print("Stage:", result["stage"])
    print("Intensity:", result["intensity"])

    print("\nSummary:")
    print(result["llm_output"]["summary"])

    print("\nNow:")
    for a in result["llm_output"]["priority_actions"].get("now", []):
        print("-", a)

    print("\nNext:")
    for a in result["llm_output"]["priority_actions"].get("next", []):
        print("-", a)

    print("\nTonight:")
    for a in result["llm_output"]["priority_actions"].get("tonight", []):
        print("-", a)

    print("\nTrend:", result["trend"])

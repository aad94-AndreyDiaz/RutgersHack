import math

# =========================================================
# 0. STATE MEMORY (SIMULATES LONG-TERM ADAPTATION)
# =========================================================
state_memory = {
    "sleep": [],
    "water": [],
    "breaks": [],
    "burnout_history": []
}


# =========================================================
# 1. BASIC SCORING FUNCTIONS
# =========================================================
def sleep_score(h): return min(1.0, max(0.1, h / 8))
def water_score(g): return min(1.0, g / 8)
def break_score(m): return min(1.0, m / 60)
def emotional_strain(m): return (5 - m) / 4

def free_time_score(t):
    return min(1.0, t / 60)

def cognitive_load(data):
    if not data["tasks"]:
        return 0.0

    unfinished = sum(1 for t in data["tasks"] if not t["done"])
    return min(
        1.0,
        0.5 * (data["calendar_hours"] / 10) +
        0.5 * (unfinished / len(data["tasks"]))
    )


# =========================================================
# 2. TREND TRACKING (SMOOTH CONVERGENCE SIGNAL)
# =========================================================
def update_trend(history, key, value, window=5):
    history[key].append(value)
    history[key] = history[key][-window:]

    if len(history[key]) < 2:
        return 0.0

    avg = sum(history[key]) / len(history[key])
    return value - avg


# =========================================================
# 3. BURNOUT ENGINE (CORE SCORE)
# =========================================================
def burnout_engine(data):

    S = sleep_score(data["sleep_hours"])
    W = water_score(data["water_glasses"])
    B = break_score(data["break_minutes"])
    E = emotional_strain(data["mood"])
    F = free_time_score(data["free_time_minutes"])
    C = cognitive_load(data)

    burnout = 100 * (
        0.32 * (1 - S) +
        0.16 * (1 - W) +
        0.22 * C +
        0.18 * E +
        0.12 * (1 - B)
    )

    return burnout, {
        "sleep_score": S,
        "water_score": W,
        "break_score": B,
        "emotional_strain": E,
        "free_time_score": F,
        "cognitive_load": C
    }


# =========================================================
# 4. WEAK POINT DETECTION (PRIORITY SIGNALS)
# =========================================================
def detect_weak_points(data, breakdown, state):

    issues = []

    sleep_trend = update_trend(state, "sleep", data["sleep_hours"])
    water_trend = update_trend(state, "water", data["water_glasses"])
    break_trend = update_trend(state, "breaks", data["break_minutes"])

    if breakdown["sleep_score"] < 0.65 or sleep_trend < -0.3:
        issues.append(("sleep", 1 - breakdown["sleep_score"]))

    if breakdown["water_score"] < 0.6:
        issues.append(("hydration", 1 - breakdown["water_score"]))

    if breakdown["break_score"] < 0.5 or break_trend < -0.2:
        issues.append(("recovery", 1 - breakdown["break_score"]))

    if breakdown["emotional_strain"] > 0.55:
        issues.append(("emotional_load", breakdown["emotional_strain"]))

    if breakdown["cognitive_load"] > 0.6:
        issues.append(("work_overload", breakdown["cognitive_load"]))

    if breakdown["free_time_score"] < 0.5:
        issues.append(("no_buffer", 1 - breakdown["free_time_score"]))

    return issues


# =========================================================
# 5. ADAPTIVE INTENSITY (PREVENT OVERWHELM)
# =========================================================
def adaptive_intensity(score):
    if score > 80:
        return 1.0
    if score > 60:
        return 0.7
    if score > 40:
        return 0.5
    return 0.3


# =========================================================
# 6. CALM ACTION ENGINE (CONTROLLED, NON-OVERWHELMING)
# =========================================================
def select_actions(issues, intensity):

    issues = sorted(issues, key=lambda x: x[1], reverse=True)

    actions = []

    for name, _ in issues:

        if name == "sleep":
            actions.append(
                "Increase sleep by +30–45 min for next 2 nights"
                if intensity < 0.8 else
                "Lock 7–8h sleep window (non-negotiable)"
            )

        elif name == "hydration":
            actions.append("Add 2 extra water checkpoints during the day")

        elif name == "recovery":
            actions.append("Take 2 short breaks (10–15 min, no screens)")

        elif name == "emotional_load":
            actions.append("Remove 1 non-essential task today")

        elif name == "work_overload":
            actions.append("Delay lowest priority task by 24 hours")

        elif name == "no_buffer":
            actions.append("Block 30–45 min zero-pressure recovery time")

    # cap but do NOT under-restrict (key design choice)
    return actions[:5]


# =========================================================
# 7. RECOVERY STAGE (LONG-TERM INTERPRETATION)
# =========================================================
def recovery_stage(score):

    if score > 80:
        return "Stabilization phase: reduce load first"
    elif score > 60:
        return "Recovery phase: small fixes compound fast"
    elif score > 30:
        return "Adjustment phase: stabilize routine"
    return "Stable phase: maintain baseline"


# =========================================================
# 8. FULL CALM OPTIMIZER
# =========================================================
def calm_optimizer(data, state):

    burnout_score, breakdown = burnout_engine(data)

    issues = detect_weak_points(data, breakdown, state)

    intensity = adaptive_intensity(burnout_score)

    actions = select_actions(issues, intensity)

    state["burnout_history"].append(burnout_score)

    return {
        "burnout_score": round(burnout_score, 2),
        "stage": recovery_stage(burnout_score),
        "intensity": intensity,
        "recommended_actions": actions,
        "trend": state["burnout_history"][-5:]
    }


# =========================================================
# 9. EXAMPLE DATA (NO USER INPUT REQUIRED)
# =========================================================
if __name__ == "__main__":

    state = state_memory

    data = {
        "sleep_hours": 5.2,
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

    result = calm_optimizer(data, state)

    print("\n=== CALM LONG-TERM OPTIMIZER ===\n")

    print("Burnout Score:", result["burnout_score"])
    print("Stage:", result["stage"])
    print("Intensity:", result["intensity"])

    print("\nRecommended Actions:")
    for a in result["recommended_actions"]:
        print("-", a)

    print("\nTrend:")
    print(result["trend"])

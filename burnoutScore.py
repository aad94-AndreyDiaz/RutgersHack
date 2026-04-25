import math
import json

# =========================================================
# 1. SLEEP FUNCTION
# =========================================================
def sleep_score(h):
    if h < 4:
        return 0.1
    elif h < 6:
        return 0.1 + 0.15 * (h - 4)
    elif h < 8:
        return 0.4 + 0.25 * (h - 6)
    elif h <= 9:
        return 0.9
    else:
        return 0.9 - 0.1 * (h - 9)


# =========================================================
# 2. WATER FUNCTION
# =========================================================
def water_score(g):
    return min(1.0, g / 8)


# =========================================================
# 3. BREAK / RECOVERY
# =========================================================
def break_score(minutes):
    return min(1.0, minutes / 60)


# =========================================================
# 4. HYGIENE
# =========================================================
def hygiene_score(done):
    return 1.0 if done else 0.3


# =========================================================
# 5. MOOD → EMOTIONAL STRAIN
# =========================================================
def emotional_strain(m):
    return (5 - m) / 4


# =========================================================
# 6. FREE TIME
# =========================================================
def free_time_score(t):
    return min(1.0, t / 60)


# =========================================================
# 7. PEER SYSTEM (STATE-AWARE)
# =========================================================
def peer_score(peer_mode, peer_checkin):

    if peer_mode == "none":
        return 1.0

    if peer_mode == "setup":
        return 1.0 if peer_checkin else 0.6

    if peer_mode == "daily":
        return 1.0 if peer_checkin else 0.0

    return 1.0


# =========================================================
# 8. MEDICATION / VITAMINS
# =========================================================
def health_support_score(took_meds, took_vitamins):
    return (0.6 if took_meds else 0.0) + (0.4 if took_vitamins else 0.0)


# =========================================================
# 9. TASK LIST → COGNITIVE LOAD
# =========================================================
def task_load(tasks):
    if not tasks:
        return 0.0

    total = len(tasks)
    unfinished = sum(1 for t in tasks if not t["done"])

    return unfinished / total


# =========================================================
# 10. COGNITIVE LOAD
# =========================================================
def cognitive_load(calendar_hours, screen_time, tasks):
    return min(
        1.0,
        0.5 * (calendar_hours / 10) +
        0.5 * task_load(tasks)
    )


# =========================================================
# 11. BURNOUT ENGINE
# =========================================================
def burnout_engine(data):

    S = sleep_score(data["sleep_hours"])
    W = water_score(data["water_glasses"])
    B = break_score(data["break_minutes"])
    H = hygiene_score(data["hygiene_done"])
    E = emotional_strain(data["mood"])
    F = free_time_score(data["free_time_minutes"])
    P = peer_score(data["peer_mode"], data["peer_checkin"])
    M = health_support_score(data["took_meds"], data["took_vitamins"])

    C = cognitive_load(
        data["calendar_hours"],
        data["screen_time_hours"],
        data["tasks"]
    )

    burnout = 100 * (
        0.28 * (1 - S) +
        0.14 * (1 - W) +
        0.16 * C +
        0.14 * E +
        0.10 * (1 - B) +
        0.05 * (1 - F) +
        0.05 * (1 - H) +
        0.04 * (1 - P) +
        0.04 * (1 - M)
    )

    return burnout, {
        "sleep_score": S,
        "water_score": W,
        "break_score": B,
        "hygiene_score": H,
        "emotional_strain": E,
        "free_time_score": F,
        "cognitive_load": C,
        "peer_score": P,
        "health_support_score": M
    }


# =========================================================
# 12. CLASSIFICATION
# =========================================================
def classify(score):
    if score < 30:
        return "Not Burnout"
    elif score < 60:
        return "Mild Burnout"
    elif score < 80:
        return "Medium Burnout"
    else:
        return "Severe Burnout"


# =========================================================
# 13. LLM TASK PARSER (SIMPLIFIED)
# =========================================================
def llm_parse_tasks(raw_text):
    items = [x.strip() for x in raw_text.split(",") if x.strip()]
    return [{"name": i, "done": False} for i in items]


# =========================================================
# 14. MAIN INTERACTIVE SYSTEM
# =========================================================
if __name__ == "__main__":

    print("\n=== AI BURNOUT WELLNESS ENGINE ===\n")

    # -------------------------
    # TASK INPUT
    # -------------------------
    print("Enter tasks (comma separated):")
    raw_tasks = input("> ")
    tasks = llm_parse_tasks(raw_tasks)

    print("\nTasks Loaded:")
    for t in tasks:
        print("-", t["name"])

    # -------------------------
    # DATA INPUT
    # -------------------------
    data = {
        "tasks": tasks,

        "sleep_hours": float(input("\nSleep hours: ")),
        "water_glasses": float(input("Water glasses: ")),
        "break_minutes": float(input("Break / recovery minutes: ")),
        "hygiene_done": input("Hygiene done (y/n): ").lower() == "y",
        "mood": float(input("Mood (1-5): ")),
        "free_time_minutes": float(input("Free time minutes: ")),

        "calendar_hours": float(input("Calendar hours: ")),
        "screen_time_hours": float(input("Screen time hours: ")),

        # PEER SYSTEM (OPTIONAL)
        "peer_mode": input("Peer mode (setup/daily/none): ").lower(),
        "peer_checkin": input("Peer check-in done (y/n): ").lower() == "y",

        # HEALTH SUPPORT
        "took_meds": input("Took medication? (y/n): ").lower() == "y",
        "took_vitamins": input("Took vitamins? (y/n): ").lower() == "y"
    }

    # -------------------------
    # RUN MODEL
    # -------------------------
    score, breakdown = burnout_engine(data)
    category = classify(score)

    # -------------------------
    # OUTPUT
    # -------------------------
    print("\n==============================")
    print(f"BURNOUT SCORE: {score:.2f}")
    print(f"STATUS: {category}")
    print("==============================\n")

    print("Feature Breakdown:")
    for k, v in breakdown.items():
        print(f"{k}: {v:.3f}")

    print("\nSystem Mode:", data["peer_mode"])

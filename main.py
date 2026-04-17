from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)

# -----------------------------
# LOAD DATA
# -----------------------------
schedule = pd.read_csv("schedule.csv")
roles = pd.read_csv("crew_roles.csv")

# -----------------------------
# CLEAN DATA
# -----------------------------
schedule.columns = schedule.columns.str.strip().str.lower()
roles.columns = roles.columns.str.strip().str.lower()

schedule["name"] = schedule["name"].str.strip().str.lower()
schedule["day"] = schedule["day"].str.strip().str.lower()
schedule["type"] = schedule["type"].str.strip().str.lower()

roles["name"] = roles["name"].str.strip().str.lower()
roles["role"] = roles["role"].str.strip().str.lower()

# -----------------------------
# FIX TIME
# -----------------------------
schedule["start"] = pd.to_datetime(
    schedule["start"].astype(str).str.strip(),
    format="%I:%M %p"
).dt.time

schedule["end"] = pd.to_datetime(
    schedule["end"].astype(str).str.strip(),
    format="%I:%M %p"
).dt.time


# -----------------------------
# WEEK CALC
# -----------------------------
def week_of_month(date):
    return (date.day - 1) // 7 + 1


def get_week_label(week):
    return {
        1: "1st week",
        2: "2nd week",
        3: "3rd week",
        4: "4th week",
        5: "5th week"
    }.get(week, "")


# -----------------------------
# ✅ GLOBAL WEEK GROUPS (FIXED)
# -----------------------------
def get_week_groups():
    week_13 = sorted(
        set(schedule[schedule["type"] == "week_1st_&_3rd"]["name"].str.title())
    )

    week_24 = sorted(
        set(schedule[schedule["type"] == "week_2nd_&_4th"]["name"].str.title())
    )

    return week_13, week_24


# -----------------------------
# CORE LOGIC
# -----------------------------
def find_available(day, start_time, end_time, week):

    day_data = schedule[schedule["day"] == day.lower()]
    results = []

    for name, person in day_data.groupby("name"):

        # -------------------------
        # APPLY WEEK RULES
        # -------------------------
        person = person[
            (person["type"].isin(["available", "unavailable", "weekly_work"])) |
            ((person["type"] == "week_1st_&_3rd") & (week in [1, 3])) |
            ((person["type"] == "week_2nd_&_4th") & (week in [2, 4]))
        ]

        # Convert valid week rows → available
        person.loc[
            person["type"].isin(["week_1st_&_3rd", "week_2nd_&_4th"]),
            "type"
        ] = "available"

        # -------------------------
        # BLOCK CHECK
        # -------------------------
        blocked = person[
            (person["type"].isin(["unavailable", "weekly_work"])) &
            (person["start"] < end_time) &
            (person["end"] > start_time)
        ]

        if not blocked.empty:
            continue

        # -------------------------
        # AVAILABILITY CHECK
        # -------------------------
        available_blocks = person[person["type"] == "available"]

        match = available_blocks[
            (available_blocks["start"] < end_time) &
            (available_blocks["end"] > start_time)
        ]

        if match.empty:
            continue

        times = [
            f"{row['start'].strftime('%I:%M %p')} - {row['end'].strftime('%I:%M %p')}"
            for _, row in available_blocks.iterrows()
        ]

        results.append({
            "name": name.title(),
            "times": times
        })

    return results


# -----------------------------
# ROUTE
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    seniors = []
    crew = []
    selected_info = None
    error = None

    # ✅ ALWAYS GET WEEK GROUPS
    week_13, week_24 = get_week_groups()

    if request.method == "POST":
        try:
            date_input = request.form["date"]
            start_input = request.form["start"]
            end_input = request.form["end"]

            date = datetime.strptime(date_input, "%Y-%m-%d")
            start_time = datetime.strptime(start_input.strip(), "%I:%M %p").time()
            end_time = datetime.strptime(end_input.strip(), "%I:%M %p").time()

            if start_time >= end_time:
                raise ValueError("End time must be after start time")

            day = date.strftime("%A").lower()
            week = week_of_month(date)
            week_label = get_week_label(week)

            # -------------------------
            # AVAILABILITY
            # -------------------------
            people = find_available(day, start_time, end_time, week)

            selected_info = {
                "date": date.strftime("%A, %B %d, %Y"),
                "start": start_time.strftime("%I:%M %p"),
                "end": end_time.strftime("%I:%M %p"),
                "week": week_label
            }

            # -------------------------
            # ROLE SPLIT
            # -------------------------
            role_map = roles.set_index("name")["role"].to_dict()

            for p in people:
                role = role_map.get(p["name"].lower(), "")
                if role == "senior":
                    seniors.append(p)
                elif role == "crew":
                    crew.append(p)

        except Exception as e:
            error = str(e)

    return render_template(
        "index.html",
        seniors=seniors,
        crew=crew,
        selected=selected_info,
        error=error,
        week_13=week_13,
        week_24=week_24
    )


# -----------------------------
# RUN
# -----------------------------


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
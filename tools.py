"""The tools the harness can run, and the JSON that describes them to the model."""

import json

import unicodedata

from fastf1.ergast import Ergast

import pandas as pd

from datetime import date

ergast = Ergast() 

# helper

def _norm(text) -> str:
    """Lowercase and remove accents so driver/team names match."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()

def _matches(query: str, *fields) -> bool: # *fields means func takes any # of extra positional args
    """True if every word in the query appears in at least one field."""
    words = _norm(query).split()
    normed = [_norm(f) for f in fields]
    return all(any(w in f for f in normed) for w in words)

def _build_rows(df, driver: str | None, team: str | None) -> list[dict]:
    """Filter a results DataFrame by driver/team and keep only the fields the model needs."""
    rows = []
    for _, r in df.iterrows():
        if driver and not _matches(driver, r.givenName, r.familyName, r.driverCode, r.driverId):
            continue
        if team and not _matches(team, r.constructorName, r.constructorId):
            continue
        rows.append({
            "position": r.positionText,  # "R" = retired, "D" = disqualified, etc.
            "driver": f"{r.givenName} {r.familyName}",
            "team": r.constructorName,
            "grid": int(r.grid),
            "points": float(r.points),
            "status": r.status,
        })
    return rows

def _round_info(r) -> dict:
    return {
        "round": int(r["round"]),
        "race": r["raceName"],
        "circuit": r["circuitName"],
        "location": f"{r['locality']}, {r['country']}",
        "date": str(r["raceDate"])[:10],
    }

def _earliest_clinch(my_pts, rival_pts, remaining, pts, rival_scores_second) -> dict | None:
    """Assume we win everything. Walk remaining rounds in order and return the first
    round after which our lead is bigger than all points still available."""
    has_sprint = remaining["sprintDate"].notna().tolist()
    my_gain = [pts["gp"] + (pts["sprint"] if s else 0) for s in has_sprint]
    rival_gain = [
        (pts["rival_gp"] + (pts["rival_sprint"] if s else 0)) if rival_scores_second else 0
        for s in has_sprint
    ]
    left = sum(my_gain)

    for i, (_, r) in enumerate(remaining.iterrows()):
        my_pts += my_gain[i]
        rival_pts += rival_gain[i]
        left -= my_gain[i]
        if my_pts - rival_pts > left:
            return _round_info(r)
    return None

def _date(x):
    """Format a schedule date, or None if the session doesn't exist."""
    return str(x)[:10] if pd.notna(x) else None

# tools

def get_last_race_results(driver: str | None = None, team: str | None = None, session: str = "race") -> str:
    race_resp = ergast.get_race_results(season="current", round="last")
    if not race_resp.content:
        return json.dumps({"error": "Race results not yet available for the current season."})

    race = race_resp.description.iloc[0]
    resp = race_resp

    if session == "sprint":
        resp = ergast.get_sprint_results(season="current", round=int(race["round"]))
        if not resp.content:
            return json.dumps({"error": f"The {race['raceName']} was not a sprint weekend."})

    rows = _build_rows(resp.content[0], driver, team)
    if not rows:
        return json.dumps({"error": f"No match for driver={driver!r}, team={team!r}."})

    return json.dumps({
        "race": race["raceName"],
        "session": session,
        "date": str(race["raceDate"])[:10],
        "circuit": race["circuitName"],
        "results": rows,
    })

# gp/sprint = the most a driver or team can score.
# rival_gp/rival_sprint = the rival's best outcome when the leader takes the top spot(s).
POINTS = {
    "driver": {"gp": 25, "sprint": 8, "rival_gp": 18, "rival_sprint": 7},
    "team": {"gp": 25 + 18, "sprint": 8 + 7, "rival_gp": 15 + 12, "rival_sprint": 6 + 5},
}

def can_win_championship(driver: str | None = None, team: str | None = None) -> str:
    if bool(driver) == bool(team):
        return json.dumps({"error": "Pass exactly one of driver or team."})

    pts = POINTS["driver" if driver else "team"]
    if driver:
        resp = ergast.get_driver_standings(season="current")
    else:
        resp = ergast.get_constructor_standings(season="current")

    if not resp.content:
        return json.dumps({"error": "No standings available for the current season yet."})

    df = resp.content[0]
    rounds_done = int(resp.description.iloc[0]["round"])

    if driver:
        mask = df.apply(lambda r: _matches(driver, r.givenName, r.familyName, r.driverCode, r.driverId), axis=1)
        names = df["givenName"] + " " + df["familyName"]
    else:
        mask = df.apply(lambda r: _matches(team, r.constructorName, r.constructorId), axis=1)
        names = df["constructorName"]

    if mask.sum() == 0:
        return json.dumps({"error": f"No match for {driver or team!r} in the standings."})
    if mask.sum() > 1 and driver:
        q = _norm(driver)
        exact = df.apply(lambda r: q in (_norm(r.driverCode), _norm(r.familyName)), axis=1)
        if exact.sum() == 1:
            mask = exact
    if mask.sum() > 1:
        return json.dumps({"error": f"Ambiguous name, matches: {names[mask].tolist()}. Be more specific."})
    me = df[mask].iloc[0]
    my_points = float(me["points"])

    # Closest rival = highest-placed entry that isn't us (standings are sorted)
    rival = df[~mask].iloc[0] # every row except ours
    rival_points = float(rival["points"])
    lead = my_points - rival_points  # negative if behind

    schedule = ergast.get_race_schedule(season="current")
    remaining = schedule[schedule["round"] > rounds_done].sort_values("round")
    sprints_left = int(remaining["sprintDate"].notna().sum())
    max_available = len(remaining) * pts["gp"] + sprints_left * pts["sprint"]

    result = {
        "name": names[mask].iloc[0],
        "position": int(me["position"]),
        "points": my_points,
        "main_rival": names[~mask].iloc[0],
        "rival_points": rival_points,
        "lead_over_rival": lead,
        "races_left": len(remaining),
        "sprints_left": sprints_left,
        "max_points_available": max_available,
        "points_system": "GP 25-18-15-12-10-8-6-4-2-1, sprint 8-7-6-5-4-3-2-1, no fastest-lap point",
    }

    if lead > max_available:
        result["status"] = "clinched"
    elif lead < -max_available:
        result["status"] = "eliminated"
    elif remaining.empty:
        result["status"] = "season over, tied on points (decided by countback)"
    else:
        result["status"] = "still possible"

        # To clinch at the next round, the lead after it must exceed what's left after it
        nxt = remaining.iloc[0]
        max_next = pts["gp"] + (pts["sprint"] if pd.notna(nxt["sprintDate"]) else 0)
        margin_needed = max_available - max_next - lead
        result["next_round"] = {
            **_round_info(nxt),
            "can_clinch_here": margin_needed < max_next,
            "must_outscore_rival_by_more_than": margin_needed,
        }

        result["earliest_clinch_best_case"] = _earliest_clinch(
            my_points, rival_points, remaining, pts, rival_scores_second=False
        )
        result["earliest_clinch_if_rival_finishes_second"] = _earliest_clinch(
            my_points, rival_points, remaining, pts, rival_scores_second=True
        )

    result["can_still_win"] = result["status"] != "eliminated"
    return json.dumps(result)

def get_standings(kind: str = "drivers") -> str:
    if kind == "drivers":
        resp = ergast.get_driver_standings(season="current")
    else:
        resp = ergast.get_constructor_standings(season="current")
    if not resp.content:
        return json.dumps({"error": "Standings not yet available for the current season."})

    df = resp.content[0]
    rows = []
    for _, r in df.iterrows():
        row = {"position": int(r["position"]), "points": float(r["points"]), "wins": int(r["wins"])}
        if kind == "drivers":
            row["driver"] = f"{r['givenName']} {r['familyName']}"
            row["team"] = r["constructorNames"][-1]  # a list; last entry is the current team
        else:
            row["team"] = r["constructorName"]
        rows.append(row)

    return json.dumps({"after_round": int(resp.description.iloc[0]["round"]), "standings": rows})

def get_next_race() -> str:
    schedule = ergast.get_race_schedule(season="current")
    today = pd.Timestamp(date.today())
    upcoming = schedule[pd.to_datetime(schedule["raceDate"]) >= today].sort_values("round")
    if upcoming.empty:
        return json.dumps({"error": "No races left this season."})

    r = upcoming.iloc[0]
    is_sprint = pd.notna(r["sprintDate"])
    result = {
        **_round_info(r),
        "days_until": (pd.to_datetime(r["raceDate"]) - today).days,
        "sprint_weekend": bool(is_sprint),
        "qualifying_date": _date(r["qualifyingDate"]),
    }
    if is_sprint:
        result["sprint_date"] = _date(r["sprintDate"])
    return json.dumps(result)

# What the model sees: the "set notes" in the screenplay.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_last_race_results",
            "description": (
                "Get results of the most recent Formula 1 race weekend. Call with no "
                "arguments for the full Grand Prix results, or pass driver "
                "and/or team to get only their results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "driver": {
                        "type": "string",
                        "description": "Driver first name, surname, or 3-letter code, e.g. 'Verstappen' or 'VER'",
                    },
                    "team": {
                        "type": "string",
                        "description": "Team name, e.g. 'Ferrari' or 'McLaren'",
                    },
                    "session": {
                        "type": "string",
                        "enum": ["race", "sprint"],
                        "description": "Defaults to 'race' (the Grand Prix). Use 'sprint' only if the user asks about the sprint.",
                    },
                },
            },
        },
    },
    {
    "type": "function",
    "function": {
        "name": "can_win_championship",
        "description": (
            "Check a Formula 1 driver's or team's championship chances this season: whether "
            "they can still win or have clinched, what they need at the next round to clinch "
            "it, and the earliest round (with location) they could clinch. Pass exactly one "
            "of driver or team."
),
        "parameters": {
            "type": "object",
            "properties": {
                "driver": {
                    "type": "string",
                    "description": "Driver first name, surname, or 3-letter code, e.g. 'Leclerc' or 'LEC'",
                },
                "team": {
                    "type": "string",
                    "description": "Team name, e.g. 'Ferrari' or 'McLaren'",
                },
            },
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "get_standings",
        "description": "Get the full current Formula 1 championship standings, for drivers or constructors (teams).",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["drivers", "constructors"], "description": "Defaults to 'drivers'."},
            },
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "get_next_race",
        "description": "Get the next Formula 1 race: name, circuit, location, date, days until it, and whether it's a sprint weekend.",
        "parameters": {"type": "object", "properties": {}},
    },
},
]

# What the harness runs: tool name -> Python function.
TOOL_MAP = {"get_last_race_results": get_last_race_results, "can_win_championship": can_win_championship, "get_standings": get_standings, "get_next_race": get_next_race}

def run_tool(name: str, args: dict) -> str:
    """Run one tool call. Models invent tool names and arguments; never let that crash the loop."""
    if name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool '{name}'. Available: {list(TOOL_MAP)}"})
    try:
        return TOOL_MAP[name](**args)
    except TypeError as e:
        return json.dumps({"error": f"Bad arguments for {name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"{name} failed: {type(e).__name__}: {e}"})

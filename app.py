from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any
import json
import os
import random

from flask import Flask, jsonify, request, abort
from flask_cors import CORS

from soccer_events import Match, EventType
from soccer_events.statsbomb_loader import match_from_statsbomb_events
from soccer_events.probabilistic import StateEventTypePriors


app = Flask(__name__)
CORS(app)


# In-memory storage of matches keyed by match_id
_matches: Dict[str, Match] = {}


def _create_demo_match(match_id: str = "demo") -> None:
    """Populate an in-memory match for demo/visualization.

    Prefers a real StatsBomb open-data events file if available at
    ``data/statsbomb_events.json``; otherwise falls back to a
    stochastic synthetic generator.
    """

    if match_id in _matches:
        return

    # 1) Try to load from local StatsBomb open-data events file
    # NOTE: we now strictly use `data.json` as the source file the user
    # has downloaded from the StatsBomb open-data repository.
    sb_path = os.path.join(os.path.dirname(__file__), "soccer_events", "data", "data.json")
    if os.path.exists(sb_path):
        try:
            with open(sb_path, "r", encoding="utf-8") as f:
                events = json.load(f)
            match = match_from_statsbomb_events(events)
            _matches[match_id] = match
            return
        except Exception:
            # If parsing fails for any reason, fall back to synthetic below.
            pass

    # 2) Fallback: synthetic stochastic generator
    home_team = "Home FC"
    away_team = "Away FC"
    match = Match(home_team=home_team, away_team=away_team)

    # basic tempo: average ~7 seconds between events over 90 minutes
    current_time = 0.0
    end_time = 90 * 60
    team_in_possession = home_team

    while current_time < end_time:
        # New possession for current team
        possession = match.new_possession(team_in_possession=team_in_possession)

        # Each possession has between 3 and 10 events
        num_events = random.randint(3, 10)

        for _ in range(num_events):
            if current_time > end_time:
                break

            # small randomness in gap between events
            gap = random.expovariate(1 / 7.0)  # mean ~7 seconds
            current_time += gap
            if current_time > end_time:
                break

            # choose event type with sensible distribution
            r = random.random()
            if r < 0.65:
                etype = EventType.PASS
            elif r < 0.75:
                etype = EventType.DRIBBLE
            elif r < 0.82:
                etype = EventType.TACKLE
            elif r < 0.9:
                etype = EventType.TURNOVER
            elif r < 0.95:
                etype = EventType.FOUL
            else:
                etype = EventType.SHOT

            tags: Dict[str, Any] = {}
            description = etype.value.title()

            # low probability that a shot becomes a goal
            if etype is EventType.SHOT and random.random() < 0.15:
                tags["is_goal"] = True
                description = "Goal!"  # type: ignore[assignment]

            # random field position
            x = random.random()
            y = random.random()

            match.add_event(
                match_time=current_time,
                event_type=etype,
                team=team_in_possession,
                possession=possession,
                description=description,
                x=x,
                y=y,
                tags=tags,
            )

        # Switch team for next possession with some persistence
        if random.random() < 0.4:
            team_in_possession = away_team if team_in_possession == home_team else home_team

    _matches[match_id] = match


def _get_match_or_404(match_id: str) -> Match:
    match = _matches.get(match_id)
    if match is None:
        abort(404, description=f"Match '{match_id}' not found")
    return match


@app.route("/matches", methods=["POST"])
def create_match() -> Any:
    data = request.get_json(force=True, silent=True) or {}
    match_id = data.get("id")
    home_team = data.get("home_team")
    away_team = data.get("away_team")

    if not match_id or not home_team or not away_team:
        abort(400, description="Fields 'id', 'home_team', and 'away_team' are required")

    if match_id in _matches:
        abort(409, description=f"Match '{match_id}' already exists")

    _matches[match_id] = Match(home_team=home_team, away_team=away_team)

    return jsonify({"id": match_id, "home_team": home_team, "away_team": away_team}), 201


@app.route("/matches/<match_id>", methods=["GET"])
def get_match(match_id: str) -> Any:
    match = _get_match_or_404(match_id)
    return jsonify({
        "id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
    })


@app.route("/matches", methods=["GET"])
def list_matches() -> Any:
    return jsonify([
        {"id": match_id, "home_team": m.home_team, "away_team": m.away_team}
        for match_id, m in _matches.items()
    ])


# --- Event helpers -----------------------------------------------------------


def _event_to_dict(ev) -> Dict[str, Any]:
    """Convert an Event to a JSON-safe dict without following cycles."""

    base: Dict[str, Any] = {
        "match_time": ev.match_time,
        "event_type": ev.event_type.value,
        "team": ev.team,
        "player": ev.player,
        "description": ev.description,
        "x": ev.x,
        "y": ev.y,
        "tags": ev.tags,
    }

    if ev.possession is not None:
        base["possession"] = {
            "id": ev.possession.id,
            "team_in_possession": ev.possession.team_in_possession,
        }
    else:
        base["possession"] = None

    return base


def _zone_from_xy(ev) -> str:
    """Coarse zone label from normalized x,y.

    Uses thirds in x (def/mid/att) and y (left/center/right).
    """

    x = ev.x
    y = ev.y
    if x is None or y is None:
        return "unknown"

    if x < 1 / 3:
        xband = "def"
    elif x < 2 / 3:
        xband = "mid"
    else:
        xband = "att"

    if y < 1 / 3:
        yband = "left"
    elif y < 2 / 3:
        yband = "center"
    else:
        yband = "right"

    return f"{xband}_{yband}"


def _parse_event_type(value: str) -> EventType:
    try:
        return EventType(value)
    except ValueError:
        abort(400, description=f"Unknown event_type '{value}'")


# --- Event CRUD --------------------------------------------------------------


@app.route("/matches/<match_id>/events", methods=["POST"])
def create_event(match_id: str) -> Any:
    match = _get_match_or_404(match_id)
    data = request.get_json(force=True, silent=True) or {}

    try:
        match_time = float(data["match_time"])
    except (KeyError, TypeError, ValueError):
        abort(400, description="Field 'match_time' (float) is required")

    event_type_raw = data.get("event_type")
    if not event_type_raw:
        abort(400, description="Field 'event_type' is required")
    event_type = _parse_event_type(event_type_raw)

    team = data.get("team")
    if not team:
        abort(400, description="Field 'team' is required")

    possession_id = data.get("possession_id")

    # Select possession (existing by id or new for team)
    possession = None
    if possession_id is not None:
        # Walk possessions to locate by id
        for pos in match.iter_possessions():
            if pos.id == possession_id:
                possession = pos
                break
        if possession is None:
            abort(400, description=f"Possession id {possession_id} not found in match '{match_id}'")

    ev = match.add_event(
        match_time=match_time,
        event_type=event_type,
        team=team,
        possession=possession,
        player=data.get("player"),
        description=data.get("description"),
        x=data.get("x"),
        y=data.get("y"),
        tags=data.get("tags") or {},
    )

    return jsonify(_event_to_dict(ev)), 201


@app.route("/matches/<match_id>/events", methods=["GET"])
def list_events(match_id: str) -> Any:
    match = _get_match_or_404(match_id)

    # Optional filters
    event_type_param = request.args.get("event_type")
    possession_id_param = request.args.get("possession_id", type=int)
    start_time = request.args.get("start_time", type=float)
    end_time = request.args.get("end_time", type=float)

    # Start with time-ordered events
    events_iter = match.iter_events()

    # Filter by event type
    if event_type_param:
        etype = _parse_event_type(event_type_param)
        events_iter = (ev for ev in events_iter if ev.event_type == etype)

    # Filter by possession
    if possession_id_param is not None:
        events_iter = (
            ev for ev in events_iter
            if ev.possession is not None and ev.possession.id == possession_id_param
        )

    # Filter by time window (inclusive)
    if start_time is not None and end_time is not None:
        events_iter = (
            ev for ev in events_iter
            if start_time <= ev.match_time <= end_time
        )

    events = [_event_to_dict(ev) for ev in events_iter]
    return jsonify(events)


@app.route("/matches/<match_id>/events/by-type/<event_type>", methods=["GET"])
def list_events_by_type(match_id: str, event_type: str) -> Any:
    match = _get_match_or_404(match_id)
    etype = _parse_event_type(event_type)
    events = [_event_to_dict(ev) for ev in match.events_by_type(etype)]
    return jsonify(events)


@app.route("/matches/<match_id>/possessions", methods=["GET"])
def list_possessions(match_id: str) -> Any:
    match = _get_match_or_404(match_id)
    possessions = [
        {
            "id": pos.id,
            "team_in_possession": pos.team_in_possession,
        }
        for pos in match.iter_possessions()
    ]
    return jsonify(possessions)


@app.route("/matches/<match_id>/possessions/<int:possession_id>/events", methods=["GET"])
def list_events_for_possession(match_id: str, possession_id: int) -> Any:
    match = _get_match_or_404(match_id)
    for pos in match.iter_possessions():
        if pos.id == possession_id:
            events = [_event_to_dict(ev) for ev in pos.iter_events()]
            return jsonify(events)
    abort(404, description=f"Possession id {possession_id} not found in match '{match_id}'")


# --- Event-type priors -------------------------------------------------------


@app.route("/matches/<match_id>/priors/team", methods=["GET"])
def event_type_priors_by_team(match_id: str) -> Any:
    """Return per-team event-type priors for a match.

    State key: team name.
    """

    match = _get_match_or_404(match_id)
    priors = StateEventTypePriors.from_events(
        match.iter_events(), key_fn=lambda ev: ev.team, alpha=0.5
    )
    return jsonify(priors.to_dict())


@app.route("/matches/<match_id>/priors/possession", methods=["GET"])
def event_type_priors_by_possession(match_id: str) -> Any:
    """Return per-possession event-type priors for a match.

    State key: possession id (or "None" if missing).
    """

    match = _get_match_or_404(match_id)

    def key_fn(ev):
        return ev.possession.id if ev.possession is not None else None

    priors = StateEventTypePriors.from_events(
        match.iter_events(), key_fn=key_fn, alpha=0.5
    )
    return jsonify(priors.to_dict())


@app.route("/matches/<match_id>/priors/team_zone", methods=["GET"])
def event_type_priors_by_team_zone(match_id: str) -> Any:
    """Return per-(team, zone) event-type priors.

    State key: (team_name, coarse_zone_label).
    """

    match = _get_match_or_404(match_id)

    def key_fn(ev):
        return (ev.team, _zone_from_xy(ev))

    priors = StateEventTypePriors.from_events(
        match.iter_events(), key_fn=key_fn, alpha=0.5
    )
    return jsonify(priors.to_dict())


# For simplicity, we implement a basic update/delete based on index in the
# global time-ordered list. In a real system you'd probably add a stable
# event_id field.


def _get_event_by_index_or_404(match: Match, index: int):
    events = list(match.iter_events())
    if index < 0 or index >= len(events):
        abort(404, description=f"Event index {index} out of range")
    return events[index]


@app.route("/matches/<match_id>/events/<int:event_index>", methods=["GET"])
def get_event(match_id: str, event_index: int) -> Any:
    match = _get_match_or_404(match_id)
    ev = _get_event_by_index_or_404(match, event_index)
    return jsonify(_event_to_dict(ev))


@app.route("/matches/<match_id>/events/<int:event_index>", methods=["PATCH"])
def update_event(match_id: str, event_index: int) -> Any:
    match = _get_match_or_404(match_id)
    ev = _get_event_by_index_or_404(match, event_index)
    data = request.get_json(force=True, silent=True) or {}

    if "match_time" in data:
        try:
            ev.match_time = float(data["match_time"])
        except (TypeError, ValueError):
            abort(400, description="Field 'match_time' must be a float")

    if "event_type" in data:
        ev.event_type = _parse_event_type(data["event_type"])

    if "team" in data:
        ev.team = data["team"]

    for field_name in ("player", "description", "x", "y", "tags"):
        if field_name in data:
            setattr(ev, field_name, data[field_name])

    # NOTE: we do not re-balance the global time ordering list on update in this
    # simple implementation. For most use-cases you'll delete & recreate.

    return jsonify(_event_to_dict(ev))


@app.route("/matches/<match_id>/events/<int:event_index>", methods=["DELETE"])
def delete_event(match_id: str, event_index: int) -> Any:
    match = _get_match_or_404(match_id)
    events = list(match.iter_events())
    if event_index < 0 or event_index >= len(events):
        abort(404, description=f"Event index {event_index} out of range")
    target = events[event_index]

    # Remove from possession linked list
    if target.prev_in_possession is not None:
        target.prev_in_possession.next_in_possession = target.next_in_possession
    if target.next_in_possession is not None:
        target.next_in_possession.prev_in_possession = target.prev_in_possession
    if target.possession is not None:
        pos = target.possession
        if pos.first_event is target:
            pos.first_event = target.next_in_possession
        if pos.last_event is target:
            pos.last_event = target.prev_in_possession

    # Remove from global event list
    match._events.remove(target)  # type: ignore[attr-defined]

    return "", 204


if __name__ == "__main__":
    # create a demo match so the frontend has data immediately
    _create_demo_match("demo")
    app.run(host="0.0.0.0", port=5000, debug=True)

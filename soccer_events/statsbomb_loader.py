from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .core import Match, EventType, PossessionNode


@dataclass
class StatsBombConfig:
    """Configuration for mapping StatsBomb open-data events into our model."""

    # Pitch dimensions in StatsBomb open data (usually 120x80)
    pitch_length: float = 120.0
    pitch_width: float = 80.0


def _infer_team_names(events: Iterable[Dict[str, Any]]) -> Tuple[str, str]:
    names: List[str] = []
    for ev in events:
        team = ev.get("team") or {}
        name = team.get("name")
        if name and name not in names:
            names.append(name)
        if len(names) >= 2:
            break
    if len(names) != 2:
        raise ValueError("Could not infer exactly two team names from StatsBomb events")
    return names[0], names[1]


def _map_event_type(sb_type: str) -> EventType:
    """Map StatsBomb `type.name` to our EventType.

    This is intentionally approximate; unknown types fall back to OTHER.
    """

    name = sb_type.lower()
    if name == "pass":
        return EventType.PASS
    if name == "shot":
        return EventType.SHOT
    if name in {"foul committed", "foul won"}:
        return EventType.FOUL
    if name in {"dispossessed", "miscontrol"}:
        return EventType.TURNOVER
    if name in {"tackle", "block", "clearance"}:
        if name == "clearance":
            return EventType.CLEARANCE
        return EventType.TACKLE
    if name in {"dribble", "carry"}:
        return EventType.DRIBBLE
    if name in {"ball recovery", "interception"}:
        return EventType.INTERCEPTION
    if name in {"goalkeeper", "save"}:
        return EventType.SAVE
    return EventType.OTHER


def match_from_statsbomb_events(
    events: List[Dict[str, Any]],
    *,
    config: StatsBombConfig | None = None,
) -> Match:
    """Build a Match from a StatsBomb open-data events array.

    This expects a *single-match* events file from StatsBomb open data.
    It does not use every StatsBomb field; it focuses on core timing,
    team, basic spatial info, and event type.
    """

    if config is None:
        config = StatsBombConfig()

    # We need two team names to construct the Match
    home_team, away_team = _infer_team_names(events)
    match = Match(home_team=home_team, away_team=away_team)

    # Possessions keyed by StatsBomb "possession" integer id
    possessions: Dict[int, PossessionNode] = {}

    for ev in events:
        t = ev.get("type") or {}
        sb_type_name = t.get("name")
        if not sb_type_name:
            continue

        # Basic filtering: ignore things that aren't really on-pitch events
        # (e.g. starting XI). You can relax this if needed.
        if sb_type_name in {"Starting XI", "Half Start", "Half End", "Substitution"}:
            continue

        minute = ev.get("minute")
        second = ev.get("second")
        if minute is None or second is None:
            continue

        match_time = float(minute) * 60.0 + float(second)

        team_info = ev.get("team") or {}
        team_name = team_info.get("name")
        if not team_name:
            continue

        # possession id and team
        poss_id = ev.get("possession")
        poss_team_info = ev.get("possession_team") or {}
        poss_team_name = poss_team_info.get("name") or team_name

        if isinstance(poss_id, int):
            if poss_id not in possessions:
                possessions[poss_id] = match.new_possession(team_in_possession=poss_team_name)
            possession = possessions[poss_id]
        else:
            possession = match.new_possession(team_in_possession=poss_team_name)

        # spatial location (StatsBomb uses [x, y] in 120x80 by default)
        loc = ev.get("location") or []
        x = y = None
        if isinstance(loc, list) and len(loc) >= 2:
            try:
                raw_x, raw_y = float(loc[0]), float(loc[1])
                x = raw_x / config.pitch_length
                y = raw_y / config.pitch_width
            except (TypeError, ValueError):
                x = y = None

        player_info = ev.get("player") or {}
        player_name = player_info.get("name")

        outcome = (ev.get("shot") or {}).get("outcome") or {}
        outcome_name = outcome.get("name")

        etype = _map_event_type(sb_type_name)

        tags: Dict[str, Any] = {}
        description = sb_type_name

        # Mark goals for shot events
        if etype is EventType.SHOT and outcome_name in {"Goal"}:
            tags["is_goal"] = True
            description = "Goal"

        match.add_event(
            match_time=match_time,
            event_type=etype,
            team=team_name,
            possession=possession,
            player=player_name,
            description=description,
            x=x,
            y=y,
            tags=tags,
        )

    return match

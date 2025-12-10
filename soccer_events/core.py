from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class EventType(str, Enum):
    PASS = "PASS"
    SHOT = "SHOT"
    FOUL = "FOUL"
    TURNOVER = "TURNOVER"
    TACKLE = "TACKLE"
    DRIBBLE = "DRIBBLE"
    INTERCEPTION = "INTERCEPTION"
    SAVE = "SAVE"
    CLEARANCE = "CLEARANCE"
    OTHER = "OTHER"


@dataclass
class Event:
    """Single soccer event tied to a specific time and possession node."""

    match_time: float  # seconds from kickoff; can extend to > 90*60 for added time
    event_type: EventType
    team: str
    player: Optional[str] = None
    description: Optional[str] = None
    x: Optional[float] = None  # 0-1 normalized pitch coordinate (length)
    y: Optional[float] = None  # 0-1 normalized pitch coordinate (width)
    tags: Dict[str, Any] = field(default_factory=dict)

    # links for node-based browsing inside a possession
    prev_in_possession: Optional["Event"] = field(default=None, repr=False)
    next_in_possession: Optional["Event"] = field(default=None, repr=False)

    # reference to owning possession node
    possession: Optional["PossessionNode"] = field(default=None, repr=False)


@dataclass
class PossessionNode:
    """Node representing a single team possession sequence.

    Supports node-based traversal: previous/next possession and walking
    forward/backward through events in this possession.
    """

    id: int
    team_in_possession: str

    # linked list of possessions within the match
    prev_possession: Optional["PossessionNode"] = field(default=None, repr=False)
    next_possession: Optional["PossessionNode"] = field(default=None, repr=False)

    # head/tail of events linked list within this possession
    first_event: Optional[Event] = field(default=None, repr=False)
    last_event: Optional[Event] = field(default=None, repr=False)

    def add_event(self, event: Event) -> Event:
        """Append an event to this possession, updating links."""

        event.possession = self
        if self.last_event is None:
            self.first_event = self.last_event = event
        else:
            event.prev_in_possession = self.last_event
            self.last_event.next_in_possession = event
            self.last_event = event
        return event

    def iter_events(self) -> Iterable[Event]:
        """Iterate forward through events in this possession."""

        cur = self.first_event
        while cur is not None:
            yield cur
            cur = cur.next_in_possession

    def iter_events_reverse(self) -> Iterable[Event]:
        """Iterate backward through events in this possession."""

        cur = self.last_event
        while cur is not None:
            yield cur
            cur = cur.prev_in_possession


class Match:
    """Container for all possessions and events in a single match.

    Provides time-ordered access and node-based possession browsing.
    """

    def __init__(self, home_team: str, away_team: str):
        self.home_team = home_team
        self.away_team = away_team

        # doubly-linked list of possessions
        self._first_possession: Optional[PossessionNode] = None
        self._last_possession: Optional[PossessionNode] = None

        # flat list of all events, always kept sorted by match_time
        self._events: List[Event] = []

        self._next_possession_id: int = 1

    # --- possession management -------------------------------------------------

    @property
    def first_possession(self) -> Optional[PossessionNode]:
        return self._first_possession

    @property
    def last_possession(self) -> Optional[PossessionNode]:
        return self._last_possession

    def new_possession(self, team_in_possession: str) -> PossessionNode:
        """Create a new possession node at the end of the match timeline."""

        node = PossessionNode(id=self._next_possession_id, team_in_possession=team_in_possession)
        self._next_possession_id += 1

        if self._last_possession is None:
            self._first_possession = self._last_possession = node
        else:
            node.prev_possession = self._last_possession
            self._last_possession.next_possession = node
            self._last_possession = node
        return node

    def iter_possessions(self) -> Iterable[PossessionNode]:
        cur = self._first_possession
        while cur is not None:
            yield cur
            cur = cur.next_possession

    def iter_possessions_reverse(self) -> Iterable[PossessionNode]:
        cur = self._last_possession
        while cur is not None:
            yield cur
            cur = cur.prev_possession

    # --- event management ------------------------------------------------------

    def add_event(
        self,
        match_time: float,
        event_type: EventType,
        team: str,
        possession: Optional[PossessionNode] = None,
        player: Optional[str] = None,
        description: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """Create and attach an event to a possession and the global timeline.

        If `possession` is None, a new possession will be started for `team`.
        """

        if possession is None:
            possession = self.new_possession(team_in_possession=team)

        ev = Event(
            match_time=match_time,
            event_type=event_type,
            team=team,
            player=player,
            description=description,
            x=x,
            y=y,
            tags=tags or {},
        )

        possession.add_event(ev)

        # keep global events sorted by time (simple insertion; ok for small/medium matches)
        idx = len(self._events)
        while idx > 0 and self._events[idx - 1].match_time > ev.match_time:
            idx -= 1
        self._events.insert(idx, ev)

        return ev

    def iter_events(self) -> Iterable[Event]:
        """Iterate through all match events in time order."""

        return iter(self._events)

    def events_in_time_range(self, start: float, end: float) -> Iterable[Event]:
        """Yield events whose `match_time` is in [start, end]."""

        for ev in self._events:
            if ev.match_time < start:
                continue
            if ev.match_time > end:
                break
            yield ev

    def events_by_type(self, *types: EventType) -> Iterable[Event]:
        """Yield events whose `event_type` is one of the given types."""

        type_set = set(types)
        for ev in self._events:
            if ev.event_type in type_set:
                yield ev

    def possessions_for_team(self, team: str) -> Iterable[PossessionNode]:
        """Iterate over possessions where the given team is in control."""

        for pos in self.iter_possessions():
            if pos.team_in_possession == team:
                yield pos

    # --- convenience queries ---------------------------------------------------

    def shots_for_team(self, team: str) -> Iterable[Event]:
        for ev in self.events_by_type(EventType.SHOT):
            if ev.team == team:
                yield ev

    def goals_for_team(self, team: str) -> Iterable[Event]:
        """Return events tagged as goals for a team (tag `is_goal` = True)."""

        for ev in self.events_by_type(EventType.SHOT):
            if ev.team == team and ev.tags.get("is_goal"):
                yield ev

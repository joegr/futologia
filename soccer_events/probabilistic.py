from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Hashable, Iterable, Mapping, Optional

import math
import random

from .core import Event, EventType


@dataclass
class EventTypePrior:
    """Simple stochastic wrapper around EventType frequencies.

    This models a categorical distribution over EventType with a
    Dirichlet prior. It can be updated from observed events and
    queried for smoothed prior probabilities or samples. The goal
    is to provide a light-weight "stochastic representative system"
    that captures typical event-type proportions for a dataset
    or a single match.
    """

    # symmetric Dirichlet concentration parameter
    alpha: float = 1.0

    # internal counts per event type (not including alpha)
    counts: Dict[EventType, float] = field(
        default_factory=lambda: {et: 0.0 for et in EventType}
    )

    def copy(self) -> "EventTypePrior":
        return EventTypePrior(alpha=self.alpha, counts=dict(self.counts))

    # ---------------------------------------------------------------------
    # Updating from data
    # ---------------------------------------------------------------------

    def update_from_events(self, events: Iterable[Event]) -> None:
        """Update counts from an iterable of Event instances."""

        for ev in events:
            if ev.event_type in self.counts:
                self.counts[ev.event_type] += 1.0
            else:
                # In case new enum members are added at runtime
                self.counts[ev.event_type] = 1.0

    def update_from_histogram(self, hist: Mapping[EventType, float]) -> None:
        """Update counts from an externally-computed histogram."""

        for et, c in hist.items():
            if et in self.counts:
                self.counts[et] += float(c)
            else:
                self.counts[et] = float(c)

    # ---------------------------------------------------------------------
    # Probabilities and sampling
    # ---------------------------------------------------------------------

    @property
    def total_mass(self) -> float:
        """Total pseudo-count (alpha * K + sum counts)."""

        k = len(self.counts) or len(EventType)
        return sum(self.counts.values()) + self.alpha * k

    def posterior_prob(self, event_type: EventType) -> float:
        """Return the smoothed probability of a particular EventType.

        This is (count + alpha) / (sum_counts + alpha * K).
        """

        k = len(self.counts) or len(EventType)
        num = self.counts.get(event_type, 0.0) + self.alpha
        denom = sum(self.counts.values()) + self.alpha * k
        if denom <= 0.0:
            return 1.0 / float(k)
        return num / denom

    def probs(self) -> Dict[EventType, float]:
        """Return the full posterior probability distribution."""

        k = len(self.counts) or len(EventType)
        denom = sum(self.counts.values()) + self.alpha * k
        if denom <= 0.0:
            uniform = 1.0 / float(k)
            return {et: uniform for et in self.counts}

        return {
            et: (c + self.alpha) / denom for et, c in self.counts.items()
        }

    def log_probs(self) -> Dict[EventType, float]:
        """Log-probabilities for numerical work."""

        return {et: math.log(p) for et, p in self.probs().items()}

    def sample(self, rng: Optional[random.Random] = None) -> EventType:
        """Draw a single EventType according to the current posterior."""

        if rng is None:
            rng = random
        items = list(self.probs().items())
        r = rng.random()
        acc = 0.0
        for et, p in items:
            acc += p
            if r <= acc:
                return et
        # Fallback in case of numerical issues
        return items[-1][0]

    # ---------------------------------------------------------------------
    # Serialization helpers
    # ---------------------------------------------------------------------

    def to_dict(self) -> Dict[str, float]:
        """Return a JSON-friendly mapping from event_type name to prob."""

        return {et.value: p for et, p in self.probs().items()}

    @classmethod
    def from_events(
        cls, events: Iterable[Event], alpha: float = 1.0
    ) -> "EventTypePrior":
        """Convenience constructor from a collection of events."""

        prior = cls(alpha=alpha)
        prior.update_from_events(events)
        return prior


@dataclass
class StateEventTypePriors:
    """Collection of EventTypePrior objects indexed by a discrete state.

    A *state* can be any hashable key that represents context, e.g.:

    - possession id
    - (team, tactical_zone)
    - (score_diff_bucket, time_bucket)

    This lets you maintain per-state priors over event types, approximating
    a simple stochastic model of how event distributions change across
    different game situations.
    """

    alpha: float = 1.0
    priors: Dict[Hashable, EventTypePrior] = field(default_factory=dict)

    def _get_or_create(self, state: Hashable) -> EventTypePrior:
        if state not in self.priors:
            self.priors[state] = EventTypePrior(alpha=self.alpha)
        return self.priors[state]

    # ------------------------------------------------------------------
    # Updating from events
    # ------------------------------------------------------------------

    def update_from_events(
        self,
        events: Iterable[Event],
        key_fn: Callable[[Event], Hashable],
    ) -> None:
        """Update per-state priors from events using a state key function.

        key_fn(ev) should return a hashable object that defines the state for
        that event, e.g. ev.possession.id or (ev.team, zone(ev.x, ev.y)).
        """

        for ev in events:
            state = key_fn(ev)
            prior = self._get_or_create(state)
            prior.update_from_events([ev])

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_prior(self, state: Hashable) -> EventTypePrior:
        """Return the EventTypePrior for a given state (creating if needed)."""

        return self._get_or_create(state)

    def state_probs(self) -> Dict[Hashable, Dict[EventType, float]]:
        """Return posterior probabilities for all states."""

        return {state: prior.probs() for state, prior in self.priors.items()}

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        """JSON-friendly mapping state -> {event_type_name: prob}.

        States are stringified via `str(state)` for simplicity. For more
        structured keys, manage serialization at a higher level.
        """

        out: Dict[str, Dict[str, float]] = {}
        for state, prior in self.priors.items():
            out[str(state)] = prior.to_dict()
        return out

    @classmethod
    def from_events(
        cls,
        events: Iterable[Event],
        key_fn: Callable[[Event], Hashable],
        alpha: float = 1.0,
    ) -> "StateEventTypePriors":
        """Build per-state priors from a collection of events."""

        inst = cls(alpha=alpha)
        inst.update_from_events(events, key_fn=key_fn)
        return inst

import React, { useEffect, useMemo, useState } from 'react';
import Timeline from './Timeline.jsx';
import Pitch from './Pitch.jsx';

const API_BASE = 'http://localhost:5000';

const EVENT_TYPES = [
  'PASS',
  'SHOT',
  'FOUL',
  'TURNOVER',
  'TACKLE',
  'DRIBBLE',
  'INTERCEPTION',
  'SAVE',
  'CLEARANCE',
  'OTHER',
];

function MatchView2() {
  const [matches, setMatches] = useState([]);
  const [selectedMatchId, setSelectedMatchId] = useState('');
  const [possessions, setPossessions] = useState([]);
  const [events, setEvents] = useState([]);

  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [possessionFilter, setPossessionFilter] = useState('');
  const [startTimeFilter, setStartTimeFilter] = useState('');
  const [endTimeFilter, setEndTimeFilter] = useState('');

  const [windowStart, setWindowStart] = useState(0);
  const [windowEnd, setWindowEnd] = useState(0);
  const [windowStartIdx, setWindowStartIdx] = useState(0);
  const [windowEndIdx, setWindowEndIdx] = useState(0);

  // Load matches
  useEffect(() => {
    fetch(`${API_BASE}/matches`)
      .then((res) => res.json())
      .then(setMatches)
      .catch((err) => console.error('Failed to load matches', err));
  }, []);

  // Load possessions when match changes
  useEffect(() => {
    if (!selectedMatchId) return;

    fetch(`${API_BASE}/matches/${selectedMatchId}/possessions`)
      .then((res) => res.json())
      .then(setPossessions)
      .catch((err) => console.error('Failed to load possessions', err));
  }, [selectedMatchId]);

  const loadEvents = () => {
    if (!selectedMatchId) return;

    const params = new URLSearchParams();
    if (eventTypeFilter) params.set('event_type', eventTypeFilter);
    if (possessionFilter) params.set('possession_id', possessionFilter);
    if (startTimeFilter !== '' && endTimeFilter !== '') {
      params.set('start_time', startTimeFilter);
      params.set('end_time', endTimeFilter);
    }

    const qs = params.toString();
    const url = `${API_BASE}/matches/${selectedMatchId}/events${qs ? `?${qs}` : ''}`;

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        setEvents(data);
      })
      .catch((err) => console.error('Failed to load events', err));
  };

  // Auto-load events when filters change
  useEffect(() => {
    loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMatchId, eventTypeFilter, possessionFilter, startTimeFilter, endTimeFilter]);

  const currentMatch = useMemo(
    () => matches.find((m) => m.id === selectedMatchId) || null,
    [matches, selectedMatchId]
  );

  const maxTime = useMemo(() => {
    if (!events.length) return 0;
    return events.reduce((max, e) => Math.max(max, e.match_time), 0);
  }, [events]);

  const timePoints = useMemo(() => {
    if (!events.length) return [];
    const arr = events.map((e) => e.match_time);
    arr.sort((a, b) => a - b);
    return arr;
  }, [events]);

  // Initialize / clamp time window for slider
  useEffect(() => {
    if (!events.length || !timePoints.length) {
      setWindowStart(0);
      setWindowEnd(0);
      setWindowStartIdx(0);
      setWindowEndIdx(0);
      return;
    }
    const firstIdx = 0;
    const lastIdx = timePoints.length - 1;
    setWindowStartIdx(firstIdx);
    setWindowEndIdx(lastIdx);
    setWindowStart(timePoints[firstIdx]);
    setWindowEnd(timePoints[lastIdx]);
  }, [events, maxTime, timePoints]);

  const windowEvents = useMemo(() => {
    if (!events.length) return [];
    return events.filter((e) => e.match_time >= windowStart && e.match_time <= windowEnd);
  }, [events, windowStart, windowEnd]);

  return (
    <div className="match-view">
      <section className="controls">
        <div className="control-row">
          <label>
            Match:
            <select
              value={selectedMatchId}
              onChange={(e) => setSelectedMatchId(e.target.value)}
            >
              <option value="">Select a match</option>
              {matches.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id} – {m.home_team} vs {m.away_team}
                </option>
              ))}
            </select>
          </label>
        </div>

        {currentMatch && (
          <>
            <div className="control-row">
              <label>
                Event type:
                <select
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                >
                  <option value="">All</option>
                  {EVENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Possession:
                <select
                  value={possessionFilter}
                  onChange={(e) => setPossessionFilter(e.target.value)}
                >
                  <option value="">All</option>
                  {possessions.map((p) => (
                    <option key={p.id} value={p.id}>
                      #{p.id} – {p.team_in_possession}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="control-row">
              <label>
                Start time (s):
                <input
                  type="number"
                  value={startTimeFilter}
                  onChange={(e) => setStartTimeFilter(e.target.value)}
                  min="0"
                />
              </label>

              <label>
                End time (s):
                <input
                  type="number"
                  value={endTimeFilter}
                  onChange={(e) => setEndTimeFilter(e.target.value)}
                  min="0"
                />
              </label>

              <button type="button" onClick={loadEvents}>
                Refresh
              </button>
            </div>
          </>
        )}
      </section>

      <section className="visualization">
        {currentMatch ? (
          <Timeline
            events={windowEvents}
            maxTime={maxTime}
            homeTeam={currentMatch.home_team}
            awayTeam={currentMatch.away_team}
            currentTime={null}
          />
        ) : (
          <p>Select a match to view events.</p>
        )}
      </section>

      {events.length > 0 && (
        <section className="timeline-slider">
          <div className="control-row">
            <label className="slider-label">
              Window start (s):
              <input
                type="range"
                min={0}
                max={Math.max(timePoints.length - 1, 0)}
                step="1"
                value={windowStartIdx}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  const clampedIdx = Math.min(val, windowEndIdx);
                  setWindowStartIdx(clampedIdx);
                  if (timePoints.length) {
                    setWindowStart(timePoints[clampedIdx]);
                  }
                }}
              />
            </label>
            <label className="slider-label">
              Window end (s):
              <input
                type="range"
                min={0}
                max={Math.max(timePoints.length - 1, 0)}
                step="1"
                value={windowEndIdx}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  const clampedIdx = Math.max(val, windowStartIdx);
                  setWindowEndIdx(clampedIdx);
                  if (timePoints.length) {
                    setWindowEnd(timePoints[clampedIdx]);
                  }
                }}
              />
            </label>
            <div className="slider-readout">
              Showing events from {windowStart.toFixed ? windowStart.toFixed(1) : windowStart}s to{' '}
              {windowEnd.toFixed ? windowEnd.toFixed(1) : windowEnd}s ({windowEvents.length} events)
            </div>
          </div>
        </section>
      )}

      {windowEvents.length > 0 && currentMatch && (
        <section className="visualization">
          <Pitch
            events={windowEvents}
            homeTeam={currentMatch.home_team}
            awayTeam={currentMatch.away_team}
          />
        </section>
      )}
    </div>
  );
}

export default MatchView2;

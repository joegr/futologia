from soccer_events import Match, EventType


def build_sample_match() -> Match:
    match = Match(home_team="Team A", away_team="Team B")

    # First possession - Team A from kickoff
    pos1 = match.new_possession(team_in_possession="Team A")
    match.add_event(
        match_time=0.0,
        event_type=EventType.PASS,
        team="Team A",
        possession=pos1,
        player="A1",
        description="Kickoff pass back",
    )
    match.add_event(
        match_time=5.0,
        event_type=EventType.DRIBBLE,
        team="Team A",
        possession=pos1,
        player="A2",
        description="Carries the ball forward",
    )
    match.add_event(
        match_time=10.0,
        event_type=EventType.SHOT,
        team="Team A",
        possession=pos1,
        player="A9",
        description="Shot from edge of box",
        tags={"is_goal": True},
    )

    # Second possession - Team B from kickoff after goal
    pos2 = match.new_possession(team_in_possession="Team B")
    match.add_event(
        match_time=70.0,
        event_type=EventType.PASS,
        team="Team B",
        possession=pos2,
        player="B6",
        description="Pass into midfield",
    )
    match.add_event(
        match_time=75.0,
        event_type=EventType.TURNOVER,
        team="Team B",
        possession=pos2,
        player="B8",
        description="Loses ball under pressure",
    )

    return match


def main() -> None:
    match = build_sample_match()

    print("All events in time order:")
    for ev in match.iter_events():
        print(f"t={ev.match_time:5.1f}s team={ev.team:6} type={ev.event_type.value:9} desc={ev.description}")

    print("\nPossession-by-possession browsing:")
    for pos in match.iter_possessions():
        print(f"Possession {pos.id} - {pos.team_in_possession}")
        for ev in pos.iter_events():
            print(f"  t={ev.match_time:5.1f}s {ev.event_type.value:9} {ev.description}")

    print("\nShots for Team A:")
    for ev in match.shots_for_team("Team A"):
        print(f"t={ev.match_time:5.1f}s {ev.description}")

    print("\nGoals for Team A:")
    for ev in match.goals_for_team("Team A"):
        print(f"t={ev.match_time:5.1f}s {ev.description}")


if __name__ == "__main__":
    main()

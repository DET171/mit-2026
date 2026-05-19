"""
Helper utilities to evaluate pit strategies with optional Safety Car (SC) / Virtual Safety Car (VSC)
event handling. This is a lightweight, deterministic approach intended to be imported into the
existing notebook. It does NOT change the notebook cells automatically; import and call the
functions where strategy evaluation is performed.

Usage (recommended):
- from tyre_strategy_with_events import simulate_strategy_with_events, detect_events_simple
- event_intervals = detect_events_simple(session)   # best-effort from fastf1 session.events
- result = simulate_strategy_with_events(total_laps, stint_lengths, compounds, model_inputs, event_intervals)

The simulator uses a simple rule:
- laps during SC/VSC are treated as neutralised laps with a configurable pace multiplier
- pitting during an event reduces pit loss by a configurable factor
- fuel/track gain (if provided in model_inputs) is applied per global lap

This file is intentionally conservative and defensive so it can be used even if session.events
is not present or differently structured.
"""
from typing import List, Tuple, Dict, Optional

# Event interval tuple: (start_lap_inclusive, end_lap_inclusive, event_type)
EventInterval = Tuple[int, int, str]


def detect_events_simple(session) -> List[EventInterval]:
    """Try to extract SC/VSC events from a fastf1 Session object.
    Returns a list of (start_lap, end_lap, event_type).
    This is a best-effort extractor: fastf1 exposes different fields by version; this function
    probes common locations and falls back to empty list.
    """
    intervals: List[EventInterval] = []
    try:
        ev = getattr(session, 'events', None)
        if ev is None:
            return intervals
        # ev is often a DataFrame with columns like 'Event', 'StartTime', 'EndTime', 'StartLap', 'EndLap'
        # Try to find lap-based boundaries first
        if 'StartLap' in ev.columns and 'EndLap' in ev.columns and 'Event' in ev.columns:
            for _, row in ev.iterrows():
                evname = str(row.get('Event', '')).upper()
                if 'SAFETY' in evname or 'VIRTUAL' in evname or 'VSC' in evname or 'SAFETY CAR' in evname:
                    try:
                        s = int(row['StartLap'])
                        e = int(row['EndLap'])
                        intervals.append((s, e, evname))
                    except Exception:
                        continue
            return intervals
        # Fallback: some fastf1 versions give only timestamps. Convert to lap numbers if laps exist.
        # Try session.laps for mapping times to lap numbers
        laps = getattr(session, 'laps', None)
        if laps is None or laps.empty:
            return intervals
        if 'StartTime' in ev.columns and 'EndTime' in ev.columns and 'Event' in ev.columns:
            for _, row in ev.iterrows():
                evname = str(row.get('Event', '')).upper()
                if 'SAFETY' in evname or 'VIRTUAL' in evname or 'VSC' in evname or 'SAFETY CAR' in evname:
                    try:
                        st = row['StartTime']
                        et = row['EndTime']
                        # map times to laps by finding laps that overlap the times
                        # this is coarse but usable
                        s_lap = laps[laps['Time'] >= st]['LapNumber'].min()
                        e_lap = laps[laps['Time'] <= et]['LapNumber'].max()
                        if not (s_lap is None or e_lap is None):
                            intervals.append((int(s_lap), int(e_lap), evname))
                    except Exception:
                        continue
            return intervals
    except Exception:
        return intervals
    return intervals


def simulate_strategy_with_events(
    total_laps: int,
    stint_lengths: List[int],
    compounds: List[str],
    model_inputs: Dict,
    event_intervals: Optional[List[EventInterval]] = None,
    sc_multiplier: float = 1.25,
    vsc_multiplier: float = 1.10,
    pit_loss_reduction: float = 0.5,
) -> Dict:
    """Simulate a strategy lap-by-lap, applying simple deterministic SC/VSC effects.

    Parameters:
    - total_laps: total race laps
    - stint_lengths: list of stint lengths summing to total_laps
    - compounds: list of compounds per stint (same length as stint_lengths)
    - model_inputs: dict with keys: 'deg_rate_by_compound', 'base_lap_by_compound', 'PIT_STOP_LOSS_SECONDS', optionally 'fuel_track_gain_sec_per_lap'
    - event_intervals: optional list of (start_lap, end_lap, event_type)
    - sc_multiplier/vsc_multiplier: multipliers applied to "nominal" lap times during events (>=1)
    - pit_loss_reduction: fraction of pit loss when pitting under event (e.g., 0.5 -> 50% of normal pit loss)

    Returns a dict with total_time_s, lap_times list, pit_laps list, and breakdown.
    """
    # Unpack model inputs with sensible defaults
    deg = model_inputs.get('deg_rate_by_compound', {})
    base = model_inputs.get('base_lap_by_compound', {})
    pit_loss = float(model_inputs.get('PIT_STOP_LOSS_SECONDS', 20.0))
    fuel_gain = float(model_inputs.get('fuel_track_gain_sec_per_lap', 0.0))

    if sum(stint_lengths) != total_laps:
        raise ValueError('stint_lengths must sum to total_laps')
    if len(stint_lengths) != len(compounds):
        raise ValueError('stint_lengths and compounds must have same length')

    # Build per-lap mapping of compound and tyre age
    lap_compound: List[str] = []
    lap_tyre_age: List[int] = []
    for stint_len, comp in zip(stint_lengths, compounds):
        for age in range(1, stint_len + 1):
            lap_compound.append(comp)
            lap_tyre_age.append(age)

    # Precompute event lookup set and event type per lap
    event_by_lap: Dict[int, str] = {}
    if event_intervals:
        for s, e, etype in event_intervals:
            for L in range(max(1, s), min(total_laps, e) + 1):
                event_by_lap[L] = etype.upper()

    lap_times: List[float] = []
    pit_laps: List[int] = []
    current_global_lap = 1

    # Simulate lap times
    for idx in range(total_laps):
        comp = lap_compound[idx]
        age = lap_tyre_age[idx]
        T0 = float(base.get(comp, 0.0))
        d = float(deg.get(comp, 0.0))
        # nominal AP lap time for this tyre age (age=1 -> n-1=0)
        nominal = T0 + (age - 1) * d
        # apply fuel/track trend as per lap index if provided
        nominal += fuel_gain * (current_global_lap - 1)

        lap_event = event_by_lap.get(current_global_lap, '').upper()
        if 'SAFETY' in lap_event or 'SAFETY CAR' in lap_event or 'SC' == lap_event:
            lap_time = nominal * sc_multiplier
        elif 'VIRTUAL' in lap_event or 'VSC' in lap_event:
            lap_time = nominal * vsc_multiplier
        else:
            lap_time = nominal

        lap_times.append(float(lap_time))
        current_global_lap += 1

    # Now add pit stop losses. Pit stops happen between stints: after stint 1..(m-1)
    # Determine lap numbers where pits happen (pit at end of stint -> pit on that lap)
    pit_positions: List[int] = []
    lap_cursor = 0
    for s_idx, s_len in enumerate(stint_lengths):
        lap_cursor += s_len
        if s_idx < len(stint_lengths) - 1:
            # pit occurs between lap_cursor and lap_cursor+1; record pit at lap_cursor
            pit_positions.append(lap_cursor)

    total_time = sum(lap_times)
    pit_loss_events: List[float] = []
    for pit_lap in pit_positions:
        # check if pit lap falls within an event for reduction
        lap_event = event_by_lap.get(pit_lap, '').upper()
        if lap_event:
            applied_pit_loss = pit_loss * pit_loss_reduction
        else:
            applied_pit_loss = pit_loss
        pit_loss_events.append(applied_pit_loss)
        total_time += applied_pit_loss
        pit_laps.append(pit_lap)

    return {
        'total_time_s': float(total_time),
        'lap_times_s': lap_times,
        'pit_laps': pit_laps,
        'pit_loss_events_s': pit_loss_events,
        'event_intervals': event_intervals or [],
        'notes': 'Simple deterministic SC/VSC handling: neutralised laps use multipliers; pit loss reduced when pitting during event.'
    }

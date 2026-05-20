# `f1_tyre_degradation_all_drivers.ipynb` — Detailed Process & Algorithm Explanation

This document explains exactly how the notebook works, including data preparation, estimation logic, mathematical models, and strategy search.

---

## 1) Goal and structure

The notebook has two computational phases:

1. **Part A (data-driven estimation):**
   - Estimate tyre degradation rates by compound (`d`, in sec/lap)
   - Estimate race-level fuel/track trend (`g`, in sec/lap)
   - Estimate pit-stop time loss (`L_pit`, in sec)
   - Estimate base lap time per compound (`T0`, in sec)

2. **Part B (AP-based strategy optimization):**
   - Use the estimated values from Part A
   - Model stint lap times with an arithmetic progression (AP)
   - Enumerate many legal pit strategies
   - Return the strategy with minimum estimated race time

---

## 2) Setup and inputs

The notebook imports:

- `fastf1` for session/lap data
- `numpy`, `pandas` for statistics and tabular operations
- `matplotlib` for plotting
- `itertools.product` for strategy combination generation

It enables local FastF1 cache (`fastf1_cache`) and defines:

- `YEAR = 2025`
- `GRAND_PRIX = 'Abu Dhabi'`
- `SESSION = 'R'` (race session)
- `COMPOUNDS_TO_ANALYZE = ['SOFT', 'MEDIUM', 'HARD']`

Then it loads race laps as `all_laps = session.laps.copy()`.

---

## 3) Part A — Estimating model inputs from raw laps

Part A is the key calibration stage. It transforms noisy race-lap data into stable parameters for Part B.

### 3.1 `prepare_nonpit_laps(laps_df, group_cols)`

This function builds a **clean, analysis-ready lap table**:

1. Keep only rows with valid `LapTime`.
2. Normalize compound labels to uppercase in `CompoundU`.
3. Convert lap times to seconds in `LapTimeSec`.
4. Remove pit in/out laps:
   - `PitInTime` must be null
   - `PitOutTime` must be null
5. Keep only “quick” laps via `pick_quicklaps(threshold=1.07)`  
   (discard slow/noisy laps beyond 107% pace threshold).
6. Sort by stint progression (`group_cols + ['LapNumber']`).
7. Create:
   - `TyreLap`: tyre age index within each stint (`1, 2, 3, ...`)
   - `LapDeltaSec`: lap-to-lap change in raw lap time inside each stint

**Why this matters:** degradation inference is very sensitive to outliers and pit-related artifacts; this preprocessing makes subsequent estimators robust.

---

### 3.2 `estimate_fuel_track_gain_from_field(session_laps, frontier_quantile=0.2)`

This estimates race-wide lap-time trend from fuel burn and track evolution.

Algorithm:

1. Build cleaned non-pit laps grouped by `['Driver', 'Stint']`.
2. For each race lap number, compute the **20th percentile** lap time across the field (`frontier`).
3. Compute lap-to-lap differences of this frontier: `deltas = frontier.diff()`.
4. Return `median(deltas)`.

Interpretation:

- If negative, field frontier is generally getting faster over race laps.
- This value is used as `fuel_track_gain_sec_per_lap` (denote as `g`).

The function raises an error if fewer than 5 deltas exist.

---

### 3.3 `theil_sen_slope(x, y)`

This is a robust slope estimator:

1. For all point pairs `(i, j), i < j`, compute pairwise slope `(y[j]-y[i])/(x[j]-x[i])`.
2. Return the median of all pairwise slopes.

This is the **Theil–Sen estimator**, less sensitive to outliers than OLS regression.

---

### 3.4 `estimate_overall_deg_rates(nonpit_laps, compounds, fuel_track_gain)`

This is the core tyre degradation estimation routine, run per compound.

For each compound `c`:

1. Filter cleaned laps to `CompoundU == c`. Skip if too few samples (`< 6`).
2. Remove race trend first:
   - `AdjLapTime = LapTimeSec - g * (LapNumber - 1)`
3. Outlier filtering on adjusted times using IQR rule:
   - keep `AdjLapTime` in `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`
4. Primary estimator:
   - `d_ts = TheilSenSlope(TyreLap, AdjLapTime)`
5. Secondary estimator (support/fallback):
   - Compute per-stint lap deltas on adjusted time: `AdjLapDelta`
   - Set `d_q70 = 70th percentile(AdjLapDelta)` when enough samples
6. Hybrid degradation estimate:
   - `d_raw = max(d_ts, 0.5 * max(d_q70, 0))`
   - `d_used = max(d_raw, 0)` (force non-negative)
7. Store diagnostics:
   - median observed raw lap delta
   - Theil-Sen estimate
   - q70 adjusted-delta estimate
   - final used degradation

Outputs:

- `raw_deg`, `used_deg`, `observed_delta`, `ts_deg`, `q70_delta` dictionaries by compound.

**Design intent:** Theil–Sen gives robust slope; q70 supports “upper-tail degradation tendency”; hybrid avoids unrealistically zero/negative degradation while controlling noise.

---

### 3.5 `estimate_base_lap_times(nonpit_laps, compounds)`

This estimates `T0` (fresh-tyre base lap time) per compound:

1. Prefer median of laps where `TyreLap == 1`.
2. If unavailable, use `TyreLap <= 2`.
3. If still unavailable, use median of all laps for that compound.

Returns `base_lap_by_compound`.

---

### 3.6 `estimate_pit_loss_from_local_baseline(laps_df, window=4)`

This estimates time lost due to a pit stop from real race data.

For each driver and each pit-in event on lap `k`:

1. Pair pit-in lap `k` with pit-out lap `k+1`.
2. Build non-pit local baselines:
   - `pre_window`: laps `[k-window, ..., k-1]`
   - `post_window`: laps `[k+2, ..., k+1+window]`
3. Compute expected pair time:
   - `expected_pair = median(pre_window) + median(post_window)`
4. Compute actual pair time:
   - `actual_pair = LapTime(k) + LapTime(k+1)`
5. Pit loss event:
   - `loss = actual_pair - expected_pair`
6. Keep only positive losses and aggregate across events.

Final pit loss is `median(losses)` across all valid events.

Outputs:

- scalar `PIT_STOP_LOSS_SECONDS`
- event table `pit_loss_events_df`

---

### 3.7 Part A orchestration and outputs

The notebook then executes:

1. Build cleaned overall laps:  
   `overall_nonpit = prepare_nonpit_laps(all_laps, ['Driver', 'Stint'])`
2. Keep selected compounds only.
3. Estimate `g` with `estimate_fuel_track_gain_from_field`.
4. Estimate degradation dictionaries with `estimate_overall_deg_rates`.
5. Estimate `T0` with `estimate_base_lap_times`.
6. Estimate pit loss with `estimate_pit_loss_from_local_baseline`.
7. Build:
   - `model_inputs = {deg_rate_by_compound, pit_stop_loss_seconds, fuel_track_gain_sec_per_lap}`
   - `summary_df` with diagnostics and decomposition checks
8. Plot bar chart of final degradation by compound.

---

## 4) Part B — AP model and pit strategy optimization

Part B uses the Part A estimates to evaluate complete race plans.

### 4.1 Race and search constraints

From session data:

- `TOTAL_LAPS = max(LapNumber)`

Search settings:

- `MAX_STOPS = 3` (0 to 3 pit stops)
- `MIN_STINT_LAPS = 8` (every stint must be at least 8 laps)
- `REQUIRE_TWO_COMPOUNDS = True`  
  (for multi-stint strategies, at least 2 unique compounds)

`available_compounds` comes from compounds successfully estimated in Part A.

---

### 4.2 AP stint-time formula: `stint_time_ap(t0, d, n_laps)`

Lap-time model per stint:

$$
T_n = T_0 + (n-1)d,\quad n=1,\dots,N
$$

Total stint time (sum of AP):

$$
\sum_{n=1}^{N} T_n = \frac{N}{2}\left(2T_0 + (N-1)d\right)
$$

This is implemented directly in `stint_time_ap`.

---

### 4.3 Full strategy time: `total_strategy_time(...)`

Given:

- stint lengths `[N_1, N_2, ..., N_m]`
- stint compounds `[c_1, c_2, ..., c_m]`

Total race estimate:

$$
T_{\text{strategy}} =
\sum_{i=1}^{m} \text{stint\_time\_ap}(T0_{c_i}, d_{c_i}, N_i)
 + (m-1)L_{\text{pit}}
$$

where `(m-1)` is number of stops.

---

### 4.4 Stint partition generation: `generate_stint_partitions(...)`

This uses recursive backtracking to enumerate all valid ways to split `TOTAL_LAPS` into `num_stints` positive integers, each at least `MIN_STINT_LAPS`.

Conceptually, it enumerates all constrained integer compositions:

$$
N_1 + N_2 + \dots + N_m = \text{TOTAL\_LAPS},\quad N_i \ge \text{MIN\_STINT\_LAPS}
$$

---

### 4.5 Candidate strategy generation and deduplication

For each stop count `stops = 0..MAX_STOPS`:

1. `stints = stops + 1`
2. Generate all valid stint-length partitions.
3. Generate all compound assignments with Cartesian product:
   - `product(available_compounds, repeat=stints)`
4. Enforce compound rule:
   - if multi-stint and `REQUIRE_TWO_COMPOUNDS`, reject single-compound plans.
5. Deduplicate order-only equivalents:
   - signature = `(stops, sorted((compound, length) pairs))`
   - eliminates permutations treated as equivalent in this model.
6. Evaluate `estimated_total_time_s` via `total_strategy_time`.
7. Collect candidate row.

If no candidate remains, the code raises an error.

---

### 4.6 Ranking and output

1. Convert candidates to `results_df`.
2. Sort ascending by `estimated_total_time_s`.
3. Best row is first row.
4. Format human-readable strategy strings like:
   - `HARD-20 | MEDIUM-18 | SOFT-20`
5. Print total laps, best strategy, best estimated total time.
6. Display top 10 strategies.

---

## 5) Important modeling assumptions

1. **Linear in-stint degradation:** lap time rises linearly with tyre age (`AP` model).
2. **Constant per-compound parameters:** one `T0` and one `d` per compound for all drivers/stints.
3. **Constant pit loss:** one median pit penalty used for all pit events.
4. **No traffic/event dynamics (default):** no explicit safety car, VSC, traffic, undercut, overcut, or weather effects.
5. **Global race trend handled in Part A only:** fuel/track trend is removed for degradation estimation but not dynamically re-simulated per strategy.

These assumptions make the model simple, interpretable, and fast for comparative strategy ranking.

---

## 6) Key produced variables (practical reference)

- `deg_rate_by_compound`: final degradation `d` per compound used in strategy search
- `base_lap_by_compound`: base lap time `T0` per compound
- `PIT_STOP_LOSS_SECONDS`: scalar pit penalty
- `fuel_track_gain_sec_per_lap`: race-wide trend estimate from field frontier
- `summary_df`: diagnostics table for Part A
- `results_df`: ranked strategy table for Part B

---

## 7) Why this notebook is structured this way

The design intentionally separates:

- **Estimation from real data (Part A)** and
- **Combinatorial optimization (Part B)**

This gives a transparent workflow:

1. infer physically meaningful parameters from race telemetry-like data,
2. then apply a compact mathematical model to explore strategy space.

It is therefore easy to adapt to another race: change the inputs (`YEAR`, `GRAND_PRIX`, `SESSION`) and rerun.

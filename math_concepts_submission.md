# Mathematics Used in the Tyre Strategy Model

This project models Formula 1 tyre strategy using a mixture of A-level mathematics and a few additional statistical methods. The main aim is to estimate how lap time changes with tyre age, then use that estimate to compare possible pit-stop strategies.

## 1. A-level mathematics used

### 1.1 Arithmetic progressions

The core lap-time model in the strategy section is an arithmetic progression.

If a stint starts with lap time $T_0$ and the lap time increases by a constant amount $d$ each lap, then the $n^{\text{th}}$ lap of the stint is

$$
T_n = T_0 + (n-1)d
$$

This is an arithmetic sequence because the difference between consecutive terms is constant:

$$
T_{n+1} - T_n = d
$$

In context:
- $T_0$ is the estimated base lap time on fresh tyres.
- $d$ is the degradation rate in seconds per lap.
- $n$ is the tyre age within the stint.

### 1.2 Sum of an arithmetic progression

To estimate the total time for a stint, the model adds all lap times in the progression:

$$
S_N = \frac{N}{2}\left(2T_0 + (N-1)d\right)
$$

where $N$ is the number of laps in the stint.

This formula is used because it is faster and cleaner than summing every lap one by one.

### 1.3 Algebra and substitution

The strategy comparison is built by substituting estimated values into formulas. For a full race strategy with several stints,

$$
{\mathcal{T}}_{\text{strategy}} = \sum_{i=1}^{m} S_i + (m-1)L_{\text{pit}}
$$

where:
- $S_i$ is the total time for stint $i$,
- $m$ is the number of stints,
- $L_{\text{pit}}$ is the pit-stop loss time.

This is standard algebraic modelling: define variables, build a formula, and then evaluate it for different inputs.

## 2. Statistics used in the data analysis

### 2.1 Median

The median is used several times because it is less affected by outliers than the mean.

For an ordered data set, the median is the middle value.

If there are an even number of values, it is the average of the two middle values.

The project uses the median to estimate:
- base lap time on fresh tyres,
- pit-stop loss,
- the typical lap-time change across the field.

### 2.2 Quantiles and percentiles

The project uses quantiles to describe the distribution of lap times.

The $p^{\text{th}}$ quantile is the value below which a proportion $p$ of the data lies.

For example, the 20th percentile is the value below which 20% of the lap times lie.

This is used to build a fast-race "frontier" from the field and to estimate how the race pace changes over time.

### 2.3 Interquartile range and outlier filtering

The interquartile range is

$$
\text{IQR} = Q_3 - Q_1
$$

where $Q_1$ is the first quartile and $Q_3$ is the third quartile.

The project removes outliers using the rule

$$
Q_1 - 1.5\,\text{IQR} \le x \le Q_3 + 1.5\,\text{IQR}
$$

This keeps the analysis focused on realistic laps and reduces the effect of unusually slow laps caused by traffic, mistakes, or race incidents.

### 2.4 First differences

The model also uses first differences, which measure change from one value to the next.

If $x_n$ is a sequence, then the first difference is

$$
\Delta x_n = x_n - x_{n-1}
$$

In the notebook, this is used for:
- lap-to-lap changes in lap time,
- changes in the field frontier over race laps.

These differences help estimate how tyre degradation and race conditions affect pace.

## 3. More advanced statistical methods used

These are not usually part of standard A-level mathematics, but they are important to make the model more reliable.

### 3.1 Theil-Sen slope estimator

To estimate tyre degradation, the notebook uses the Theil-Sen method instead of a basic line of best fit.

For data points $(x_i, y_i)$, the method considers the slope between every pair of points:

$$
s_{ij} = \frac{y_j - y_i}{x_j - x_i}
$$

The final slope estimate is the median of all these pairwise slopes.

This is more robust than ordinary least squares because it is less sensitive to outliers.

### 3.2 Robust modelling with adjusted times

The notebook first removes the estimated race-wide trend from lap times:

$$
\text{Adjusted Lap Time} = \text{Lap Time} - g(\text{Lap Number} - 1)
$$

where $g$ is the fuel/track gain term.

This isolates the tyre-age effect more clearly before estimating degradation.

### 3.3 Running medians and baseline comparisons

For pit-stop loss, the notebook compares the actual pit sequence with nearby baseline laps.

The expected time is built from medians of laps before and after the stop, and the pit loss is estimated by

$$
\text{Pit Loss} = \text{Actual Pair Time} - \text{Expected Pair Time}
$$

This is a practical statistical comparison method that reduces noise from race-to-race variation.

## 4. Discrete mathematics used in strategy search

The strategy section also uses discrete mathematics.

### 4.1 Integer partitions / compositions

The race distance is split into stint lengths that must add up to the total number of laps:

$$
N_1 + N_2 + \cdots + N_m = N_{\text{total}}
$$

with each stint length meeting a minimum value.

This is a constrained integer composition problem.

### 4.2 Exhaustive search

The notebook checks many possible strategy combinations and chooses the one with the smallest total estimated time.

This is a brute-force optimisation method over a finite search space.

## 5. Summary

The main A-level mathematics in this project is:
- arithmetic progressions,
- the sum of an arithmetic progression,
- algebraic substitution,
- averages and medians,
- quantiles and interquartile range,
- first differences.

The main additional mathematics is:
- the Theil-Sen robust slope estimator,
- outlier filtering using the IQR rule,
- constrained integer partitioning,
- exhaustive search for the best strategy.

Overall, the project uses mathematics to turn raw race data into a predictive model for lap time, then uses that model to compare pit-stop strategies.
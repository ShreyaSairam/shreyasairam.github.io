# Turnaround: where a blood test loses its hour

An urgent blood test should be back within an hour. This console follows every sample from order to released result, finds which stage makes urgent tests late, and tests fixes before anyone spends money.

**Live console:** [Open it](https://shreyasairam.github.io/lab-turnaround/index.html) · [Case study](https://shreyasairam.github.io/work/lab-turnaround.html)

## Files

| File | Purpose |
|---|---|
| `sim.js` | Discrete event model of a hospital core lab: five wards, porters and pneumatic tube, reception rota, batching centrifuges, analyser QC and maintenance, haemolysed recollects. Pure functions, runs in the browser and in Node |
| `index.html` | The console: turnaround charts, a heatmap of every hour, sample journeys, plain English questions and paired what if runs |
| `media/` | Poster image |

## How it works

- There is no public sample level turnaround dataset, so the month is simulated from real lab processes. 11,800 samples, eight timestamped stages each.
- Every tube waits for the same staff and machines, so a busy morning slows everything down.
- Each what if scenario reuses the same random seed, so the patients and orders are identical and any change comes from the fix alone.

## Results

- 87% of urgent samples met the 60 minute target over the month, but only 60% of those ordered between 06:00 and 09:00.
- Three changes (an earlier reception shift, chemistry QC moved to 05:30 and a second porter overnight) lift the morning from 60% to 83% and urgent ward samples from 52% to 69%. A third centrifuge and wider autoverification changed almost nothing.
- All 133 haemolysed urgent samples missed their target.

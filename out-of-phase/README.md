# Out of Phase

Do batteries that chase the electricity price help or hurt the street they sit on?

A grid battery earns money by charging when power is cheap and releasing it when power is expensive. But the market price is set for a whole state or country. The local wires feel something else: how busy that one street or city is. When the two peaks don't line up, a battery that follows the price can be empty when the street needs it, or even charge while the street is overloaded.

This project tests that with real data from two places.

| | Sydney | Delhi |
|---|---|---|
| Area | City South zone substation (Ausgrid) | Whole city (Delhi SLDC) |
| Day | 29 Feb 2024 | 19 Jun 2024, record demand |
| Price | AEMO NSW spot price | IEX day ahead price |
| Street limit | Busiest 1% of the year: 87.4 MW | Busiest 1% of the year: 7,619 MW |

**Live app:** [Play the day](https://shreyasairam.github.io/out-of-phase/index.html) · [Explore the lab](https://shreyasairam.github.io/out-of-phase/lab.html) · [Case study](https://shreyasairam.github.io/work/out-of-phase.html)

## What I found

- Across 104 Ausgrid zone substations over a full year, a substation's busiest hour fell within an hour of the price peak on only **42%** of days. In summer it was **24%**.
- For Delhi against India's national price, the figure was **40%**.
- On the test days, a large battery run purely for profit made the street **worse** than having no battery: about 64% more overload energy in Sydney and 122% more in Delhi.
- Making the battery care about the street costs very little at first in Sydney, but costs much more in Delhi.
- A payment for every MWh of overload a battery removes (and a charge for every MWh it adds) can change the owner's choice. On these days it takes about $1,300 per MWh to halve the strain in Sydney, and about ₹7,200 in Delhi. These are single day estimates.

## How it works

`code/optimise.py` solves a linear program (SciPy HiGHS) for each city and battery size:

- Battery power is 5%, 10% or 20% of the day's peak load, with 4 hours of storage.
- Round trip efficiency 90%. The battery starts and ends the day full.
- The objective is profit, minus a small wear cost for every MWh moved.
- A cap on overload energy (MWh above the street limit) is tightened in 11 steps, from money only to the least overload possible. Each step is a plan the app can play back.

```
pip install numpy scipy
cd code
python optimise.py --check ../index.html
```

The check compares the rebuilt results with the data inside the live app. All 66 plans match within 0.02%.

## Files

| Path | What it is |
|---|---|
| `index.html` | The app: basics, the problem, the battery game, strategies, findings, fixes |
| `lab.html` | The detailed lab version with every chart and control |
| `code/optimise.py` | The battery optimiser |
| `code/day_inputs.json` | The two real days: load, price and street limit every 15 minutes |
| `media/` | Photos and video used by the app |

## Limits

Two days, one place in each country. Prices are wholesale prices only, with no network charges or ancillary services. The battery knows the whole day in advance, so real results would be a bit worse.

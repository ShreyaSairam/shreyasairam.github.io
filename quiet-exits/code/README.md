# Quiet Exits

Customers rarely say goodbye. Their balances do.

This project follows one banking problem, savings quietly draining out of accounts that still look healthy, through the six teams that turn bank data into a decision.

| Stage | Team | What's here |
|---|---|---|
| 1. Data | Data engineering | `sql/01_build_monthly_view.sql` turns 1,056,320 transactions into 185,615 account months |
| 2. Insight | Analytics | Drift rates, segments, and the months before a drift |
| 3. Model | Data science | LightGBM with an out-of-time test and SHAP explanations |
| 4. Governance | Model risk | Model card, fairness checks by gender and age, PSI monitoring, India and UK rules |
| 5. Action | Front office | Relationship manager call list with reasons, next step, call opener and a live what-if |
| 6. Proof | Business | Backtest against what really happened, plus a control group test design |

## Results (unseen months, Oct 1997 to Jun 1998)

- Calling the top 10% of scores catches 53% of accounts that drifted (5.3x better than random)
- AUC 0.89, against 0.86 for a logistic regression baseline
- One hypothesis failed: transfers to other banks were not a warning sign in this data

## Definition

An account drifts when its average balance over the next 3 months falls below 70% of its 6-month average. Accounts need 8 months of history and a usual balance of at least 10,000 CZK.

## Data

PKDD'99 Financial Data Set (Petr Berka and Marta Sochorova): real anonymised transactions from a Czech bank, 1993 to 1998. Loaded from the public Teradata conversion by Dieter Noeth (github.com/dnoeth/1999_Czech_financial_dataset_Teradata), which shifted dates by 20 years and divided amounts by 10. The SQL restores the originals.

## Run it

```
pip install duckdb lightgbm scikit-learn pandas
# put the fin_*.tsv files in data/
python stage1_run.py      # Stage 1: SQL build
python stages2to6.py      # Stages 2 to 6
python export_model.py    # model for the in-browser what-if
python build.py           # builds quiet-exits.html
```

## Limits

Old data from one country. No record of calls made, so the model predicts drift, not whether a call works. That needs the controlled test described in stage 6.

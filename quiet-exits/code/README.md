# Churn Prediction: code

Two halves: bank customers whose savings quietly drain away (Quiet Exits), and employees likely to leave.

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
pip install duckdb lightgbm scikit-learn pandas numpy pyarrow
# put the fin_*.tsv files in data/ (bank)
# put the IBM HR attrition CSV in data/emp_attrition.csv (employees)

# Bank customers
python stage1_run.py      # Stage 1: SQL build into out/bank.duckdb
python stages2to6.py      # Stages 2 to 6: insight, model, governance, backtest
python export_model.py    # compact model for the in-browser what-if
python exit_type_test.py  # tests whether exit type can be predicted
python prep_tool.py       # data for the customer tool
python build_tool.py      # -> quiet-exits-tool.html, published as ../index.html
python build.py           # -> quiet-exits.html, published as ../report.html

# Employees
python prep_hr.py         # five models compared, live model for the browser
python build_hr.py        # -> employees-tool.html, published as ../employees.html

# Last step, from the site root
python quiet-exits/code/add_guide.py .   # adds the short start-here guide to each tool
```

| File | Purpose |
|---|---|
| `sql/01_build_monthly_view.sql` | Turns raw transactions into account months |
| `stage1_run.py`, `stages2to6.py` | The six stage pipeline |
| `export_model.py`, `prep_tool.py`, `prep_final.py` | Model export and tool data (`prep_tool.py` reuses the training code in `prep_final.py`) |
| `exit_type_test.py` | Hypothesis test on exit type |
| `prep_hr.py` | Employee models |
| `*_template.html`, `tool_engine.js` | Page templates and the in-browser scoring engine |
| `build*.py` | Fill the templates with data |

## Limits

Old data from one country. No record of calls made, so the model predicts drift, not whether a call works. That needs the controlled test described in stage 6.

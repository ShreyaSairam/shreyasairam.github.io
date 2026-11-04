# Genetic Testing Decision Support: code

A GP enters a patient's symptoms. The tool ranks likely genetic conditions, shows the genes behind them and recommends one test: a single gene test, a targeted panel or exome sequencing. Around it sit consent, pseudonymisation, role based views, an overseas transfer check and a SHA-256 chained audit trail.

**Live tool:** [Try it](https://shreyasairam.github.io/genetic-testing/index.html) · [Case study](https://shreyasairam.github.io/work/genetic-testing.html)

## Files

| File | Purpose |
|---|---|
| `prep.py` | Merges duplicate OMIM and Orphanet entries, weights rare symptoms, tests the matcher on simulated patients and calibrates the confidence label on held out cases. Writes `gx_data.json` |
| `gx_template.html` | The tool: matching, recommendation and every privacy safeguard, in the browser |
| `build.py` | Puts the data into the template. Writes `gx-tool.html`, published as `../index.html` |

## Run it

```
pip install pandas numpy
git clone https://github.com/ShreyaSairam/portfolio ../../../portfolio   # matching engine in genomics_dsst/
cd genetic-testing/code
python prep.py
python build.py
```

## Results

Tested on 500 simulated patients per scenario, built from real disease profiles:

- With 5 symptoms, the right condition ranked first 88% of the time and the right gene was in the recommended test 99% of the time.
- The first confidence label said High on 83% of cases but was right only 69% of the time. The recalibrated label is right 88% of the time on unseen cases.

A teaching prototype, not a medical device.

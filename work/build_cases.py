"""Case study pages for the portfolio. Run: python3 cases.py <site root>"""
import sys, html, pathlib

CASES = [
 dict(slug="genetic-testing", kind="Health AI · Privacy and governance", title="Genetic Testing Decision Support",
  hook="Helping a GP pick the right genetic test, with the privacy and safety checks a clinic would need.",
  meta=[("Role","Rebuilt and extended on my own, from a group coursework project where I led the viability assessment"),("When","2026"),("Built with","Python, pandas, JavaScript, SQLite, Human Phenotype Ontology")],
  img="../genetic-testing/media/poster.jpg", try_=("Try the tool","../genetic-testing/index.html"), code="https://github.com/ShreyaSairam/shreyasairam.github.io/tree/main/genetic-testing/code",
  stats=[("577","genetic conditions it can match"),("99%","right gene in the recommended test, with 5 symptoms"),("69% → 88%","confidence label, after testing caught a flaw")],
  problem=["A GP sees a child with heart defects and an eye problem. It might be genetic. But most GPs are not genetics specialists, and there are thousands of possible tests. Pick the wrong one and the family waits months for an answer that was never going to come.",
           "There is a second problem. Genetic data is about the most sensitive data there is. A tool that touches it has to earn trust on privacy, not just on accuracy."],
  built=["A GP enters the patient's symptoms. The tool ranks the most likely conditions, shows the genes behind them, and recommends one test: a single gene test, a targeted panel, or exome sequencing.",
         "Around that sits everything a clinic would need: consent before anything runs, pseudonymised data, different views for a GP, a genetic counsellor, a lab and IT, a check before data goes overseas, and an audit trail chained with SHA-256 so any edited entry shows. You can switch each safeguard off and watch what breaks."],
  steps=[("Code the symptoms","Each symptom is a Human Phenotype Ontology term, the standard vocabulary clinicians use."),
         ("Weight rare symptoms more","A seizure appears in hundreds of conditions. A lens dislocation appears in a few. Rare symptoms narrow the search, so they count for more."),
         ("Score every condition","70% for how much of the patient it explains, 30% for how much of the condition's own profile the patient shows."),
         ("Clean the data first","The same condition was often listed twice, once from each database. Merging them stopped it splitting its own score."),
         ("Recommend one test","A clear leader with few genes gets a targeted test. An uncertain case gets a wider panel and a referral to a specialist.")],
  found=["I tested it on 500 practice patients per scenario, made from real disease profiles, where I already knew the right answer.",
         "With 5 symptoms, the right condition came first 88% of the time, and the right gene was in the recommended test 99% of the time. Add 2 unrelated symptoms, the kind a busy GP might also note, and the top answer dropped to 41%. Messy input is the real risk.",
         "The biggest find was the confidence label. It said High on 83% of cases but was right only 69% of the time. I rebuilt the rule from the test results. Now it says Clear lead on a third of cases and is right 88% of the time on cases it had never seen."],
  lessons=[("The best fix came from a test, not a model.","The overconfident label was invisible until I tested it like a clinician would."),
           ("Data cleaning beat the algorithm.","Merging duplicate conditions changed results more than tuning the score."),
           ("What I'd do next","Validate on real clinical cases, use the full HPO vocabulary, and get regulatory review. It is a teaching prototype, not a medical device.")]),

 dict(slug="churn-prediction", kind="Machine learning · Banking and HR", title="Churn Prediction: Employees to Bank Customers",
  hook="Who is about to leave, why, and what to do about it. First for employees, then for bank customers.",
  meta=[("Role","Solo. The employee half rebuilds my Business Analytics coursework, first done in SPSS"),("When","2026"),("Built with","SQL (DuckDB), Python, LightGBM, scikit-learn, JavaScript")],
  img="../quiet-exits/media/poster.jpg", try_=("Try the bank tool","../quiet-exits/index.html"), try2=("Try the employee tool","../quiet-exits/employees.html"),
  code="https://github.com/ShreyaSairam/shreyasairam.github.io/tree/main/quiet-exits/code",
  stats=[("1.06M","real bank transactions"),("0.89 AUC","3 months ahead, on months it never saw"),("53%","of leavers caught in the top 10% of flags")],
  problem=["Bank customers rarely close their accounts. They drift. Savings move out, the salary stops arriving, and by the time the account is closed, the decision was made months ago.",
           "Employees are the same. By the time someone resigns, it is too late to ask what would have kept them."],
  built=["Two live tools that answer as you change the inputs.",
         "Employees: change overtime, pay, satisfaction or years since promotion, and see the chance they leave, the top three reasons, and a suggested action. Five models are compared underneath.",
         "Bank customers: drag a customer's balance, income and cash withdrawals, and see the chance their money leaves within 3 months, the likely reason (a big purchase, income stopping, or living off savings), and the response that fits."],
  steps=[("Shape the data in SQL","1.06 million raw transactions from an open Czech bank dataset become one row per account per month."),
         ("Define leaving","An account drifts when its next 3 months average under 70% of its last 6 months."),
         ("Build 23 signals","Balance trend, income, share of cash withdrawals, loan payments and more."),
         ("Train on the past, test on the future","LightGBM learns from 1994 to mid 1997 and is tested on late 1997 to 1998, just like real life."),
         ("Guess the reason, then run it live","A second model names the likely reason. Both models are exported so they run in the browser instantly.")],
  found=["The bank model reached 0.89 AUC, against 0.86 for a simple logistic regression. Its top 10% of flags caught 53% of the accounts that drifted. It named the reason correctly 67% of the time, against 48% for always guessing the most common one.",
         "For employees, logistic regression scored best (0.85 AUC), so it runs live because its reasons are easy to explain. Overtime was the strongest single driver, and clustering found groups whose leaving rates ranged from 7% to 28%."],
  lessons=[("Not everyone can be talked out of leaving.","Someone saving for a wedding will move their money whatever you say. So the tool suggests a response that fits the reason, not just 'call them'."),
           ("Test on later months, not random rows.","Random splits flatter a model. Out of time testing gives honest numbers."),
           ("What I'd do next","The employee data is IBM's fictional dataset. Real HR data would need careful privacy handling and fairness checks.")]),

 dict(slug="out-of-phase", kind="Optimisation · Independent research", title="Out of Phase",
  hook="Do batteries that chase the electricity price help or hurt your street? A test with real data from Sydney and Delhi.",
  meta=[("Role","Solo independent research"),("When","2026"),("Built with","Python, optimisation, AEMO, Ausgrid, IEX and Delhi SLDC data")],
  img="../out-of-phase/media/towers.jpg", try_=("Play the day","../out-of-phase/index.html"), try2=("Explore the lab","../out-of-phase/lab.html"), code=None,
  stats=[("42%","of days a Sydney substation peak lines up with the price peak"),("24%","in summer, when the grid is most stretched"),("40%","the same check for Delhi")],
  problem=["Big batteries earn money by following the electricity price, which is set for a whole region. But the strain on the grid happens locally, at the substation on your street.",
           "If the price peak and the local peak happen at different times, a battery chasing the price can make your street worse, not better."],
  built=["A game and a lab built on real data. In the game, you run a real battery for one real day, one hour at a time: charge, hold or release, and try to earn money while keeping the street calm.",
         "In the lab, you design your own plan by dragging when the battery charges and releases, compare Sydney with Delhi, and see the trade off between money and a calm street."],
  steps=[("Gather real data","Sydney: AEMO market prices and 104 Ausgrid zone substations, every 15 minutes. Delhi: IEX exchange prices and Delhi SLDC city load."),
         ("Draw the strain line","The busiest 1% of each place's year marks a network at its hardest."),
         ("Model the battery","4 hours of storage, 90% round trip efficiency, starting and ending the day full."),
         ("Optimise","Find the most money possible while keeping street strain under a chosen limit."),
         ("Score the balance","Combine money kept and calm left on the street into one score out of 100.")],
  found=["Only 42% of the time did a Sydney substation's busiest hour land within an hour of the price peak. In summer, when it matters most, that fell to 24%. Delhi was 40%.",
         "Chasing the price can leave the street worse off than having no battery at all. The cheapest time to charge is often midday, which is exactly when city centres are busiest."],
  lessons=[("Turning research into a game works.","People who would never read a report understood the problem in a minute by playing one day."),
           ("The optimiser shows a best case.","It knows the whole day in advance. Real batteries have to forecast prices and load."),
           ("What would fix it","Pay batteries a small amount for releasing during local peaks, and give local network peaks a place in dispatch rules.")]),

 dict(slug="lumen", kind="Team project · Smart cities · FEIT Hackathon 2026", title="Lumen",
  hook="Making Cremorne's streets readable: privacy safe pedestrian counting, shade modelling and cooler walking routes.",
  meta=[("Role","Team xMyst, five people who met at the FEIT mixer. My part: problem research, the business case and the final pitch"),("When","2026"),("Built with","YOLO computer vision, crowd forecasting, pvlib, OpenStreetMap, route optimisation")],
  img="../out-of-phase/media/syd-day.jpg", try_=("Open the live prototype","https://lumen.yuanhaofeng.com/"), code=None,
  stats=[("Top 5","of 15 finalist teams"),("SMEC","Spot Prize winner"),("304","simulated trips across 76 buildings")],
  problem=["Cremorne's offices compete with the spare room at home. To bring people back, the street experience matters: shade, quiet, safe walking routes.",
           "But most of the precinct is data dark. The council does not know where people walk, or which streets are too hot to use."],
  built=["Lumen turns office windows into privacy safe pedestrian counters. They count people, but never store images or identities.",
         "A digital twin models where the shade falls through the day. Walkers get cooler, quieter routes, and the council gets street fixes ranked by walkers helped per dollar."],
  steps=[("Understand the brief","Research what Cremorne's businesses and council actually need."),
         ("Count, never record","Computer vision counts pedestrians on the device, so no footage leaves the window."),
         ("Model the shade","A digital twin with pvlib shows where the sun hits each street, hour by hour."),
         ("Route people well","Recommend cooler, quieter walks between buildings."),
         ("Make the business case","Rank street improvements by walkers helped per dollar, so the council can act.")],
  found=["Our team placed in the top 5 of 15 finalist teams and won the SMEC Spot Prize.",
         "Testing the approach on 304 simulated trips across 76 buildings showed how much route choice changes once shade and crowding are visible."],
  lessons=[("Privacy first was a selling point.","Counting without storing images answered the first question every judge asked."),
           ("Five strangers can build fast.","We met at the FEIT mixer and split the work by strength: build, data and pitch."),
           ("My part","I owned the problem research, the business case and the final pitch.")]),
]

CSS = r"""
:root{--paper:#F5F4EF;--card:#FFFFFF;--ink:#1D2033;--soft:#5B5F75;--line:#E2E0D8;--navy:#1E2761;--navy-deep:#141B47;--gold:#B88A12;--gold-soft:#E4CD82;--ice:#D6E2FB;
--display:"Fraunces",Georgia,serif;--body:"IBM Plex Sans",-apple-system,"Segoe UI",sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0F1129;--card:#171A3D;--ink:#ECEDF6;--soft:#A7AAC6;--line:#2A2E57;--navy:#232C72;--navy-deep:#0B0E28;--gold:#E2C26A;--ice:#C9D7F7;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0F1129;--card:#171A3D;--ink:#ECEDF6;--soft:#A7AAC6;--line:#2A2E57;--navy:#232C72;--navy-deep:#0B0E28;--gold:#E2C26A;--ice:#C9D7F7;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:16.5px;line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:inherit}:focus-visible{outline:2px solid var(--gold);outline-offset:3px;border-radius:4px}
.wrap{max-width:860px;margin:0 auto;padding-inline:20px}
.top{background:var(--navy-deep);color:var(--ice)}
.top .wrap{max-width:1080px;display:flex;justify-content:space-between;align-items:center;padding-block:14px;font-family:var(--mono);font-size:13px}
.top a{text-decoration:none;opacity:.85}.top a:hover{opacity:1}
.hero{background:linear-gradient(165deg,var(--navy-deep),var(--navy));color:var(--ice);padding-block:46px 120px}
.kind{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-soft)}
h1{font-family:var(--display);font-weight:600;font-size:clamp(34px,5.6vw,52px);line-height:1.05;margin:10px 0 14px;color:#fff;text-wrap:balance}
.hook{font-size:clamp(18px,2.2vw,21px);max-width:44ch;margin:0 0 22px;opacity:.95}
.btns{display:flex;flex-wrap:wrap;gap:10px}
.btn{display:inline-block;font-family:var(--mono);font-size:13px;text-decoration:none;padding:10px 17px;border-radius:8px;border:1px solid var(--gold-soft);color:var(--gold-soft)}
.btn.primary{background:var(--gold-soft);color:var(--navy-deep)}
.btn:hover{background:#fff;color:var(--navy-deep);border-color:#fff}
.shot{margin-top:-90px;border-radius:16px;overflow:hidden;border:1px solid var(--line);box-shadow:0 18px 50px rgba(20,27,71,.18);background:var(--navy-deep);aspect-ratio:16/9}
.shot img{width:100%;height:100%;object-fit:cover;object-position:left top;display:block}
.meta{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-block:30px 10px;padding-bottom:26px;border-bottom:1px solid var(--line)}
.meta div{min-width:0}.meta b{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold);font-weight:500;margin-bottom:4px}
.meta span{font-size:14.5px;color:var(--soft);line-height:1.45;display:block}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-block:30px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.stat b{display:block;font-family:var(--display);font-size:clamp(26px,3.4vw,34px);font-weight:600;line-height:1.05}
.stat span{display:block;font-size:13.5px;color:var(--soft);margin-top:6px;line-height:1.4}
section{padding-block:26px}
.n{font-family:var(--mono);font-size:12px;color:var(--gold);letter-spacing:.12em}
h2{font-family:var(--display);font-weight:600;font-size:clamp(25px,3.2vw,32px);line-height:1.15;margin:4px 0 14px}
section p{margin:0 0 14px;max-width:66ch}
.steps{list-style:none;padding:0;margin:18px 0 0;display:grid;gap:0;counter-reset:s}
.steps li{position:relative;padding:0 0 22px 52px;counter-increment:s}
.steps li::before{content:counter(s);position:absolute;left:0;top:0;width:34px;height:34px;border-radius:50%;background:var(--navy);color:#fff;display:grid;place-items:center;font-family:var(--mono);font-size:14px}
.steps li::after{content:"";position:absolute;left:16.5px;top:38px;bottom:4px;width:1px;background:var(--line)}
.steps li:last-child::after{display:none}
.steps b{display:block;font-size:17px;margin-bottom:2px}.steps span{color:var(--soft)}
.lessons{display:grid;gap:12px;margin-top:16px}
.lesson{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:12px;padding:16px 18px}
.lesson b{display:block;margin-bottom:3px}.lesson span{color:var(--soft)}
.next{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-block:30px 50px}
.next a{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.next a:hover{border-color:var(--gold)}
.next small{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold)}
.next strong{display:block;font-family:var(--display);font-size:19px;margin-top:4px}
.next a.r{text-align:right}
footer{background:var(--navy-deep);color:var(--ice);padding-block:28px;font-size:14px}
footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
@media (max-width:700px){.meta,.stats{grid-template-columns:1fr}.next{grid-template-columns:1fr}.next a.r{text-align:left}.hero{padding-bottom:90px}.shot{margin-top:-64px}}
"""

def esc(s): return html.escape(s, quote=False)
def page(c, prev, nxt):
    btns = f'<a class="btn primary" href="{c["try_"][1]}"{" target=\"_blank\" rel=\"noopener\"" if c["try_"][1].startswith("http") else ""}>{esc(c["try_"][0])}</a>'
    if c.get("try2"): btns += f'<a class="btn" href="{c["try2"][1]}">{esc(c["try2"][0])}</a>'
    if c.get("code"): btns += f'<a class="btn" href="{c["code"]}" target="_blank" rel="noopener">Code</a>'
    P = lambda xs: "".join(f"<p>{esc(x)}</p>" for x in xs)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(c["title"])} · Shreya Sairam</title>
<meta name="description" content="{esc(c["hook"])}">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<meta property="og:title" content="{esc(c["title"])}"><meta property="og:description" content="{esc(c["hook"])}"><meta property="og:image" content="https://shreyasairam.github.io/media/og.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<nav class="top"><div class="wrap"><a href="../index.html#work">← All projects</a><a href="../index.html">Shreya Sairam</a></div></nav>
<header class="hero"><div class="wrap">
<span class="kind">{esc(c["kind"])}</span><h1>{esc(c["title"])}</h1><p class="hook">{esc(c["hook"])}</p>
<div class="btns">{btns}</div></div></header>
<main class="wrap">
<div class="shot"><img src="{c["img"]}" alt="{esc(c["title"])} screenshot"></div>
<div class="meta">{"".join(f"<div><b>{esc(k)}</b><span>{esc(v)}</span></div>" for k,v in c["meta"])}</div>
<div class="stats">{"".join(f'<div class="stat"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a,b in c["stats"])}</div>
<section><span class="n">01</span><h2>The problem</h2>{P(c["problem"])}</section>
<section><span class="n">02</span><h2>What I built</h2>{P(c["built"])}</section>
<section><span class="n">03</span><h2>How it works</h2><ol class="steps">{"".join(f"<li><b>{esc(a)}</b><span>{esc(b)}</span></li>" for a,b in c["steps"])}</ol></section>
<section><span class="n">04</span><h2>What I found</h2>{P(c["found"])}</section>
<section><span class="n">05</span><h2>What I learned</h2><div class="lessons">{"".join(f'<div class="lesson"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a,b in c["lessons"])}</div></section>
<div class="btns" style="margin-top:8px">{btns.replace('class="btn"','class="btn" style="border-color:var(--navy);color:var(--navy)"').replace('class="btn primary"','class="btn primary" style="background:var(--navy);border-color:var(--navy);color:#fff"')}</div>
<div class="next"><a href="{prev["slug"]}.html"><small>← Previous</small><strong>{esc(prev["title"])}</strong></a><a class="r" href="{nxt["slug"]}.html"><small>Next →</small><strong>{esc(nxt["title"])}</strong></a></div>
</main>
<footer><div class="wrap"><span>Shreya Sairam · Curious about the data. Careful with the answer.</span><a href="../index.html">Back to portfolio</a></div></footer>
</body></html>'''

if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1]) / "work"; out.mkdir(exist_ok=True)
    for i, c in enumerate(CASES):
        (out / f'{c["slug"]}.html').write_text(page(c, CASES[i-1], CASES[(i+1) % len(CASES)]))
        print("wrote", c["slug"])

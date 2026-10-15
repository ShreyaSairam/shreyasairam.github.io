import json, sys
TPL = r'''
<!-- start-here guide -->
<style>
.sg-card{position:fixed;right:18px;bottom:18px;z-index:9999;width:min(320px,calc(100vw - 36px));background:#14213D;color:#fff;border-radius:16px;padding:16px 16px 14px;box-shadow:0 12px 36px rgba(20,33,61,.35);font-family:inherit}
.sg-card .sg-k{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:#E4CD82;font-weight:700}
.sg-card b{display:block;font-size:1.05rem;margin:4px 0 4px}
.sg-card p{margin:0;font-size:.9rem;opacity:.9;line-height:1.4}
.sg-row{display:flex;justify-content:space-between;align-items:center;margin-top:12px;gap:8px}
.sg-dots{display:flex;gap:5px}.sg-dots i{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.3)}.sg-dots i.on{background:#E4CD82}
.sg-btn{border:0;border-radius:9px;padding:7px 14px;font-weight:700;cursor:pointer;font:inherit;font-size:.85rem}
.sg-next{background:#E4CD82;color:#14213D}.sg-skip{background:transparent;color:rgba(255,255,255,.7)}
.sg-hl{outline:3px solid #E4CD82!important;outline-offset:4px;border-radius:12px;transition:outline-color .2s}
.sg-open{position:fixed;right:18px;bottom:18px;z-index:9998;border:0;border-radius:999px;background:#14213D;color:#fff;padding:9px 15px;font:inherit;font-weight:700;font-size:.85rem;cursor:pointer;box-shadow:0 6px 18px rgba(20,33,61,.3)}
</style>
<script>
(function(){
  var STEPS = __STEPS__, KEY = "sg-__KEY__", i = 0, card, hl;
  function seen(){ try { return localStorage.getItem(KEY) === "1"; } catch(e){ return false; } }
  function mark(){ try { localStorage.setItem(KEY, "1"); } catch(e){} }
  function clear(){ if(hl){ hl.classList.remove("sg-hl"); hl = null; } }
  function close(){ clear(); if(card){ card.remove(); card = null; } mark(); opener(); }
  function opener(){
    if(document.querySelector(".sg-open")) return;
    var b = document.createElement("button"); b.className = "sg-open"; b.textContent = "How to use";
    b.onclick = function(){ b.remove(); i = 0; show(); }; document.body.appendChild(b);
  }
  function show(){
    clear(); var s = STEPS[i], el = document.querySelector(s.sel);
    if(el){ hl = el; el.classList.add("sg-hl"); el.scrollIntoView({behavior:"smooth", block:"center"}); }
    if(!card){ card = document.createElement("div"); card.className = "sg-card"; card.setAttribute("role","dialog"); card.setAttribute("aria-label","How to use this tool"); document.body.appendChild(card); }
    card.innerHTML = '<div class="sg-k">Try this · step ' + (i+1) + ' of ' + STEPS.length + '</div><b>' + s.t + '</b><p>' + s.d + '</p>' +
      '<div class="sg-row"><div class="sg-dots">' + STEPS.map(function(_,j){ return '<i class="' + (j===i?'on':'') + '"></i>'; }).join('') + '</div>' +
      '<div><button class="sg-btn sg-skip">Skip</button><button class="sg-btn sg-next">' + (i === STEPS.length-1 ? 'Got it' : 'Next') + '</button></div></div>';
    card.querySelector(".sg-skip").onclick = close;
    card.querySelector(".sg-next").onclick = function(){ if(i < STEPS.length-1){ i++; show(); } else close(); };
  }
  window.addEventListener("load", function(){ setTimeout(function(){ seen() ? opener() : show(); }, 600); });
})();
</script>
'''
def snippet(key, steps): return TPL.replace("__STEPS__", json.dumps(steps)).replace("__KEY__", key)
GUIDES = {
 "genetic-testing/index.html": ("gx", [
   {"sel":"#presets","t":"Pick a patient","d":"Start with a clear case, then try the messy one. The recommended test updates instantly."},
   {"sel":"#roles","t":"Switch who's looking","d":"View the same record as a GP, a lab or IT. Each role only sees what it needs."},
   {"sel":"#ctrls","t":"Turn a safeguard off","d":"Switch off consent or pseudonymisation and watch what breaks. The verdict flips to No go."}]),
 "quiet-exits/index.html": ("qe", [
   {"sel":"#presets","t":"Pick a real customer","d":"Each one is a real account from a Czech bank. Start with Big withdrawal coming."},
   {"sel":"#c-bal","t":"Drag the dots","d":"Pull the balance, income or cash withdrawals up or down. The models answer as you drag."},
   {"sel":"#risk","t":"Read the answer","d":"The chance their money leaves in 3 months, the likely reason, and what the bank should do."}]),
 "quiet-exits/employees.html": ("qe-emp", [
   {"sel":"#presets","t":"Pick a real employee","d":"Start with Overworked junior, then compare with Settled senior."},
   {"sel":"#controls","t":"Change their situation","d":"Switch overtime off, raise their pay or change satisfaction, and see the risk move."},
   {"sel":"#why","t":"See what's driving it","d":"The top reasons behind the risk, and a suggested action for each."}]),
}
if __name__ == "__main__":
    root = sys.argv[1]
    for f,(k,steps) in GUIDES.items():
        p = root + "/" + f; t = open(p).read()
        if "start-here guide" in t: t = t[:t.index("\n<!-- start-here guide -->")] + t[t.index("</script>", t.index("start-here guide"))+9:]
        t = t.replace("</body>", snippet(k, steps) + "\n</body>", 1) if "</body>" in t else t + snippet(k, steps)
        open(p, "w").write(t); print("ok", f)

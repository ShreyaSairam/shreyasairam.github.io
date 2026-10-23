/* Turnaround: discrete event model of a hospital core lab.
   Every sample gets real timestamps for each stage. Queues, staff rotas,
   centrifuge batching, analyser downtime and haemolysed recollects are all
   simulated, so a change to the lab (a lever) changes the result honestly.
   Pure functions, no DOM: runs in the browser and in Node. */
(function (root) {
  "use strict";

  var DAYS = 28, START = "2026-10-05", VOL = 2.6; // starts on a Monday
  var WARDS = ["ED", "ICU", "Ward 4 (Medical)", "Ward 7 (Surgical)", "Outpatients"];
  var TESTS = ["Troponin", "Electrolytes", "FBC", "INR", "CRP"];
  var GROUP = { Troponin: "chem", Electrolytes: "chem", CRP: "chem", FBC: "haem", INR: "coag" };
  var SPIN = { Troponin: true, Electrolytes: true, CRP: true, INR: true, FBC: false };
  var ASSAY = { Troponin: 18, Electrolytes: 10, CRP: 12, FBC: 2, INR: 14 };
  var TARGET = { stat: 60, routine: 240 };
  var STAGES = [
    { k: "collect", name: "Collection" }, { k: "recollect", name: "Recollection" }, { k: "transport", name: "Transport" },
    { k: "reception", name: "Reception" }, { k: "spin", name: "Centrifuge" }, { k: "queue", name: "Analyser queue" },
    { k: "assay", name: "Assay" }, { k: "verify", name: "Verification" }
  ];
  var LEVERS = {
    nightPorter: { name: "Second porter overnight", desc: "A second porter from 22:00 to 07:00 halves the wait for a ward pickup at night." },
    rota: { name: "Earlier start for reception", desc: "The second reception officer starts at 06:30 instead of 08:00, so the morning bloods are not booked in by one person." },
    qc: { name: "Run chemistry QC at 05:30", desc: "Daily quality control on the chemistry analyser moves out of the 08:00 morning peak." },
    centrifuge: { name: "Third centrifuge", desc: "Adds a third centrifuge, so a full rack does not wait for a free one." },
    autoverify: { name: "Wider autoverification", desc: "Results inside tighter rules release without a scientist. Raises the auto release rate from 62% to 82%." }
  };

  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function logn(r, median, sigma) { var u = 1 - r(), v = r(); var z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); return median * Math.exp(sigma * z); }
  function poisson(r, lam) { var L = Math.exp(-lam), k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1; }
  function pick(r, items) { var tot = 0, i; for (i = 0; i < items.length; i++) tot += items[i][1]; var x = r() * tot; for (i = 0; i < items.length; i++) { x -= items[i][1]; if (x <= 0) return items[i][0]; } return items[items.length - 1][0]; }
  var H = 60, D = 1440;
  function hourOf(t) { return Math.floor((t % D) / H); }
  function dayOf(t) { return Math.floor(t / D); }
  function dowOf(t) { return dayOf(t) % 7; } // 0 Monday
  function night(t) { var h = hourOf(t); return h >= 22 || h < 7; }

  // expected orders per hour by ward
  function rate(w, h, dow) {
    var wk = dow < 5;
    if (w === "ED") return [1.2, 1, .9, .8, .8, .9, 1.1, 1.4, 1.8, 2.2, 2.5, 2.6, 2.6, 2.5, 2.5, 2.6, 2.7, 2.8, 2.8, 2.7, 2.5, 2.2, 1.8, 1.5][h] * (wk ? 1 : 1.1);
    if (w === "ICU") return [.6, .5, .5, .5, .6, 2.6, 2.8, .9, .8, .8, .8, .8, .8, .7, .7, .8, .8, .8, .7, .7, .6, .6, .6, .6][h];
    if (w === "Ward 4 (Medical)") return [.3, .2, .2, .2, .3, 5, 8.5, 6, 1.6, 1.4, 1.4, 1.3, 1.2, 1.2, 1.2, 1.2, 1.1, 1, .9, .8, .7, .6, .5, .4][h] * (wk ? 1 : .8);
    if (w === "Ward 7 (Surgical)") return [.2, .2, .2, .2, .2, 4, 7, 5, 1.2, 1.1, 1.1, 1, 1, 1, 1, 1, .9, .8, .7, .6, .5, .4, .3, .3][h] * (wk ? 1 : .7);
    if (w === "Outpatients") return wk && h >= 8 && h < 16 ? [5, 6.5, 6, 4, 4.5, 5.5, 5, 3][h - 8] : 0;
    return 0;
  }
  var MIX = {
    "ED": [["Troponin", 34], ["Electrolytes", 34], ["FBC", 20], ["INR", 8], ["CRP", 4]],
    "ICU": [["Electrolytes", 36], ["FBC", 28], ["INR", 18], ["CRP", 14], ["Troponin", 4]],
    "Ward 4 (Medical)": [["Electrolytes", 34], ["FBC", 30], ["CRP", 18], ["INR", 12], ["Troponin", 6]],
    "Ward 7 (Surgical)": [["FBC", 36], ["Electrolytes", 32], ["CRP", 16], ["INR", 14], ["Troponin", 2]],
    "Outpatients": [["FBC", 34], ["Electrolytes", 30], ["CRP", 16], ["INR", 18], ["Troponin", 2]]
  };
  var STATP = { "ED": .86, "ICU": .6, "Ward 4 (Medical)": .1, "Ward 7 (Surgical)": .12, "Outpatients": 0 };

  // pneumatic tube outage (unplanned): Friday 16 Oct 11:00 to 16:30
  var TUBE_DOWN = [[11 * D + 11 * H, 11 * D + 16.5 * H]];
  function tubeDown(t) { return TUBE_DOWN.some(function (w) { return t >= w[0] && t < w[1]; }); }

  // Staff and equipment rotas, as on-duty windows within a day [start, end) in minutes.
  function windowsFor(daily, extraDown) {
    // daily: list of [start,end] for every day (end may exceed 1440); returns absolute windows across DAYS+1
    var out = [];
    for (var d = -1; d <= DAYS + 1; d++) daily.forEach(function (w) { out.push([d * D + w[0], d * D + w[1]]); });
    out.sort(function (a, b) { return a[0] - b[0]; });
    if (extraDown) out = subtract(out, extraDown);
    return out;
  }
  function subtract(wins, downs) {
    var out = [];
    wins.forEach(function (w) {
      var segs = [w];
      downs.forEach(function (dn) {
        var next = [];
        segs.forEach(function (s) {
          if (dn[1] <= s[0] || dn[0] >= s[1]) { next.push(s); return; }
          if (dn[0] > s[0]) next.push([s[0], dn[0]]);
          if (dn[1] < s[1]) next.push([dn[1], s[1]]);
        });
        segs = next;
      });
      out = out.concat(segs);
    });
    return out.sort(function (a, b) { return a[0] - b[0]; });
  }
  function daily(list) { var out = []; for (var d = -1; d <= DAYS + 1; d++) list.forEach(function (w) { out.push([d * D + w[0], d * D + w[1]]); }); return out; }
  function nextOn(wins, t) { for (var i = 0; i < wins.length; i++) { if (t < wins[i][1]) return { at: Math.max(t, wins[i][0]), end: wins[i][1] }; } return { at: t, end: Infinity }; }

  // Multi-server queue with priority. jobs: {arr, pri (lower first), svc, ...}; servers: list of on-duty window lists.
  // Returns start times written to job[key].
  function serve(jobs, servers, key, svcOf, priOf) {
    priOf = priOf || function (j) { return j.pri; };
    var order = jobs.slice().sort(function (a, b) { return a.arr - b.arr; });
    var free = servers.map(function () { return -Infinity; }), pending = [], i = 0, n = order.length, t = -Infinity;
    while (i < n || pending.length) {
      if (!pending.length) { t = Math.max(t, order[i].arr); while (i < n && order[i].arr <= t) pending.push(order[i++]); }
      var best = 0, bt = Infinity;
      for (var s = 0; s < servers.length; s++) { var on = nextOn(servers[s], Math.max(free[s], t)).at; if (on < bt) { bt = on; best = s; } }
      while (i < n && order[i].arr <= bt) pending.push(order[i++]);
      var j = 0;
      for (var q = 1; q < pending.length; q++) { var pq = priOf(pending[q]), pj = priOf(pending[j]); if (pq < pj || (pq === pj && pending[q].arr < pending[j].arr)) j = q; }
      var job = pending.splice(j, 1)[0];
      job[key] = bt; free[best] = bt + svcOf(job); t = bt;
    }
  }

  function centrifuges(jobs, units) {
    // batch: start when 12+ waiting, a STAT has waited 3 min, or oldest waited 8 min. 10 min spin + 1 min load.
    var q = jobs.slice().sort(function (a, b) { return a.arr - b.arr; });
    var free = []; for (var u = 0; u < units; u++) free.push(-Infinity);
    var i = 0, wait = [];
    var t = q.length ? q[0].arr : 0;
    while (i < q.length || wait.length) {
      if (!wait.length) { t = Math.max(t, q[i].arr); }
      while (i < q.length && q[i].arr <= t) wait.push(q[i++]);
      var unit = 0; for (u = 1; u < units; u++) if (free[u] < free[unit]) unit = u;
      var tFree = Math.max(t, free[unit]);
      // trigger time for current waiting set
      var oldest = wait[0].arr, stat = Infinity;
      wait.forEach(function (j) { if (j.pri === 0 && j.arr < stat) stat = j.arr; });
      var trig = Math.min(oldest + 8, stat + 3);
      if (wait.length >= 12) trig = Math.min(trig, t);
      var nextArr = i < q.length ? q[i].arr : Infinity;
      var go = Math.max(tFree, trig);
      if (nextArr < go && wait.length < 24) { t = nextArr; continue; }
      var batch = wait.splice(0, 24);
      batch.forEach(function (j) { j.spinStart = go; j.spinEnd = go + 11; });
      free[unit] = go + 11;
      t = go;
    }
  }

  function simulate(opts) {
    opts = opts || {};
    var L = opts.levers || {};
    var r = rng(opts.seed || 20261005);
    var samples = [], id = 0;
    // ---------- orders, collection, transport ----------
    function porterRound(t, w) {
      // routine pickups: every 30 min by day (07-22), every 60 min overnight unless the second porter is on
      var nt = night(t) && !L.nightPorter ? 60 : 30;
      var base = Math.ceil((t + 1) / nt) * nt;
      return base + logn(r, 8, .3);
    }
    function porterCall(t) { return t + logn(r, night(t) && !L.nightPorter ? 27 : 13, .45); }
    function transport(s, t) {
      if (s.ward === "ED" || s.ward === "ICU") {
        if (tubeDown(t)) { s.tubeOut = true; return porterCall(t); }
        return t + logn(r, 4, .25);
      }
      if (s.ward === "Outpatients") return porterRound(t);
      return s.pri === 0 ? porterCall(t) : porterRound(t, s.ward);
    }
    function collectDelay(s, t) {
      if (s.ward === "ED") return logn(r, s.pri === 0 ? (night(t) ? 12 : 9) : 22, .5);
      if (s.ward === "ICU") return logn(r, s.pri === 0 ? 7 : 14, .45);
      if (s.ward === "Outpatients") return logn(r, 11, .5);
      var h = hourOf(t);
      if (s.pri === 0) return logn(r, night(t) ? 18 : 12, .5);
      return logn(r, h >= 5 && h < 8 ? 16 : 38, .55);
    }
    for (var d = 0; d < DAYS; d++) for (var h = 0; h < 24; h++) WARDS.forEach(function (w) {
      var n = poisson(r, rate(w, h, d % 7) * VOL);
      for (var k = 0; k < n; k++) {
        var t = d * D + h * H + r() * H;
        var s = { id: ++id, ward: w, test: pick(r, MIX[w]), order: t };
        s.pri = r() < STATP[w] ? 0 : 1;
        if (s.test === "Troponin" && w === "ED") s.pri = 0;
        s.collect = t + collectDelay(s, t);
        s.recv = transport(s, s.collect);
        var hz = (s.test === "Electrolytes" || s.test === "Troponin") ? (w === "ED" ? .055 : .02) : 0;
        s.haem = r() < hz;
        s.seen = r() < .65; // a STAT bag is spotted at reception and jumps the queue
        s.auto = r() < (L.autoverify ? .82 : .62) * (s.test === "Troponin" ? .8 : 1);
        s.crit = r() < (s.pri === 0 ? .06 : .02);
        s.recollectDelay = logn(r, w === "ED" ? 17 : night(s.collect) ? 42 : 28, .45);
        samples.push(s);
      }
    });

    // ---------- lab pipeline (two passes for haemolysed recollects) ----------
    var recW = [
      [L.rota ? 22.5 * H : 22.5 * H, 31 * H], // night: 22:30 to 07:00 next day
      [7 * H, 15 * H], [(L.rota ? 6.5 : 8) * H, (L.rota ? 14.5 : 16) * H], [15 * H, 23 * H], [15.5 * H, 23.5 * H]
    ].map(function (w) { return daily([w]); });
    var recServers = [recW[0], recW[1], recW[2], recW[3], recW[4]];
        var maint = []; for (var w = 0; w < 5; w++) maint.push([(w * 7 + 2) * D + 10 * H, (w * 7 + 2) * D + 11.5 * H]); // Wednesdays
    var always = [[-2 * D, (DAYS + 3) * D]];
    var qcAll = L.qc ? [5.5 * H, 6.1 * H] : [8 * H, 8.6 * H];
    var chem = [subtract(always, daily([qcAll])), subtract(subtract(always, daily([qcAll])), maint)];
    var haem = [subtract(always, daily([[7.5 * H, 7.75 * H]]))];
    var coag = [subtract(always, daily([[8 * H, 8.33 * H]]))];
    var sci = [daily([[0, 24 * H]]), daily([[7 * H, 21 * H]])];

    function pipeline(tubes) {
      tubes.forEach(function (j) { j.arr = j.recv; });
      serve(tubes, recServers, "acc0", function () { return 1.7 + r() * .8; }, function (j) { return j.pri === 0 && j.seen ? 0 : 1; });
      tubes.forEach(function (j) { j.acc = j.acc0 + 1.0; });
      var spin = tubes.filter(function (j) { return SPIN[j.test]; });
      spin.forEach(function (j) { j.arr = j.acc; });
      centrifuges(spin, L.centrifuge ? 3 : 2);
      tubes.forEach(function (j) { if (!SPIN[j.test]) { j.spinStart = j.spinEnd = j.acc; } j.arr = j.spinEnd; });
      ["chem", "haem", "coag"].forEach(function (g) {
        var js = tubes.filter(function (j) { return GROUP[j.test] === g; });
        serve(js, g === "chem" ? chem : g === "haem" ? haem : coag, "load", function () { return g === "chem" ? .5 : g === "haem" ? .8 : .7; });
      });
      tubes.forEach(function (j) { j.analysed = j.load + ASSAY[j.test]; });
    }
    var tubes = samples.map(function (s) { return s; });
    pipeline(tubes);
    // haemolysed: rejected when the result flags, a new tube is collected and goes round again
    var redo = samples.filter(function (s) { return s.haem; });
    redo.forEach(function (s) {
      s.firstCollect = s.collect;
      s.collect = s.analysed + 2 + s.recollectDelay;
      s.recv = transport(s, s.collect);
    });
    if (redo.length) {
      // re-run the whole lab with the new tubes in place so they queue with everything else
      pipeline(samples);
    }
    // verification
    var man = samples.filter(function (s) { return !s.auto; });
    man.forEach(function (s) { s.arr = s.analysed; });
    serve(man, sci, "vstart", function (j) { return 1.6 + (j.crit ? 4 : 0); });
    samples.forEach(function (s) { s.result = s.auto ? s.analysed + .3 : s.vstart + 1.6 + (s.crit ? 4 : 0); });

    // ---------- tidy up ----------
    samples.forEach(function (s) {
      var c0 = s.firstCollect !== undefined ? s.firstCollect : s.collect;
      s.st = {
        collect: c0 - s.order,
        recollect: s.firstCollect !== undefined ? s.collect - s.firstCollect : 0,
        transport: s.recv - s.collect,
        reception: s.acc - s.recv,
        spin: s.spinEnd - s.acc,
        queue: s.load - s.spinEnd,
        assay: s.analysed - s.load,
        verify: s.result - s.analysed
      };
      s.tat = s.result - s.order;
      s.lab = s.result - s.recv;
      s.target = s.pri === 0 ? TARGET.stat : TARGET.routine;
      s.late = s.tat > s.target;
      delete s.arr; delete s.acc0; delete s.vstart; delete s.recollectDelay;
    });
    return samples;
  }

  // ---------- analysis helpers ----------
  function pct(xs, p) { if (!xs.length) return null; var a = xs.slice().sort(function (x, y) { return x - y; }); return a[Math.min(a.length - 1, Math.max(0, Math.ceil(p * a.length) - 1))]; }
  function mean(xs) { return xs.length ? xs.reduce(function (a, b) { return a + b; }, 0) / xs.length : null; }
  function summary(list) {
    var tats = list.map(function (s) { return s.tat; }), stat = list.filter(function (s) { return s.pri === 0; });
    return {
      n: list.length, stat: stat.length,
      onTime: list.length ? list.filter(function (s) { return !s.late; }).length / list.length : null,
      statOnTime: stat.length ? stat.filter(function (s) { return !s.late; }).length / stat.length : null,
      median: pct(tats, .5), p90: pct(tats, .9),
      recollect: list.filter(function (s) { return s.haem; }).length
    };
  }
  // Which stage makes late samples late: mean minutes per stage for late vs on-time samples of the same priority.
  function bottleneck(list) {
    var late = list.filter(function (s) { return s.late; }), ok = list.filter(function (s) { return !s.late; });
    return STAGES.map(function (st) {
      var a = mean(late.map(function (s) { return s.st[st.k]; })), b = mean(ok.map(function (s) { return s.st[st.k]; }));
      var all = list.map(function (s) { return s.st[st.k]; });
      return { k: st.k, name: st.name, late: a, ok: b, excess: a === null || b === null ? null : a - b, median: pct(all, .5), p90: pct(all, .9), mean: mean(all) };
    });
  }

  // ---------- plain English questions -> a query ----------
  var DOW = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  function parseQuestion(q) {
    var t = " " + q.toLowerCase().replace(/[?.!,]/g, " ") + " ", f = { wards: [], tests: [], pri: null, hours: null, dows: [], date: null }, why = [];
    if (/\b(ed|emergency|a&e|a and e)\b/.test(t)) f.wards.push("ED");
    if (/\b(icu|intensive)\b/.test(t)) f.wards.push("ICU");
    if (/\b(ward 4|medical|medicine)\b/.test(t)) f.wards.push("Ward 4 (Medical)");
    if (/\b(ward 7|surgical|surgery)\b/.test(t)) f.wards.push("Ward 7 (Surgical)");
    if (/\b(outpatient|outpatients|clinic|opd)\b/.test(t)) f.wards.push("Outpatients");
    if (/\bwards?\b/.test(t) && !f.wards.length && !/\bwhich ward\b/.test(t)) f.wards = ["Ward 4 (Medical)", "Ward 7 (Surgical)"];
    if (/\btrop\w*/.test(t)) f.tests.push("Troponin");
    if (/\b(electrolyte\w*|potassium|sodium|u&e|ue|k\+?)\b/.test(t)) f.tests.push("Electrolytes");
    if (/\b(fbc|full blood|cbc|blood count|haemoglobin|hemoglobin)\b/.test(t)) f.tests.push("FBC");
    if (/\b(inr|coag\w*|clotting|pt)\b/.test(t)) f.tests.push("INR");
    if (/\b(crp|c reactive)\b/.test(t)) f.tests.push("CRP");
    if (/\b(stat|urgent|priority|emergency samples)\b/.test(t)) f.pri = 0;
    if (/\broutine\b/.test(t)) f.pri = 1;
    if (/\b(night|overnight)\b/.test(t)) f.hours = [22, 7];
    else if (/\b(early morning|morning bloods|morning rounds)\b/.test(t)) f.hours = [5, 9];
    else if (/\bmorning\b/.test(t)) f.hours = [6, 12];
    else if (/\bafternoon\b/.test(t)) f.hours = [12, 17];
    else if (/\bevening\b/.test(t)) f.hours = [17, 22];
    var hm = t.match(/\b(\d{1,2})\s*(?::00)?\s*(am|pm)?\s*(?:to|-|and)\s*(\d{1,2})\s*(?::00)?\s*(am|pm)?\b/);
    if (hm && /\b(between|from)\b/.test(t)) { var a = +hm[1] % 12 + (hm[2] === "pm" ? 12 : 0), b = +hm[3] % 12 + ((hm[4] || hm[2]) === "pm" ? 12 : 0); if (!hm[2] && !hm[4]) { a = +hm[1]; b = +hm[3]; } f.hours = [a, b]; }
    DOW.forEach(function (d, i) { if (new RegExp("\\b" + d + "s?\\b").test(t)) f.dows.push(i); });
    if (/\bweekends?\b/.test(t)) f.dows = f.dows.concat([5, 6]);
    if (/\bweekdays?\b/.test(t)) f.dows = f.dows.concat([0, 1, 2, 3, 4]);
    var dm = t.match(/\b(\d{1,2})(?:st|nd|rd|th)?\s+(oct\w*|nov\w*)\b/) || t.match(/\b(oct\w*|nov\w*)\s+(\d{1,2})\b/);
    if (dm) { var dd = +(/\d/.test(dm[1]) ? dm[1] : dm[2]), mon = /\d/.test(dm[1]) ? dm[2] : dm[1]; var idx = mon.indexOf("nov") === 0 ? 26 + dd : dd - 5; if (idx >= 0 && idx < DAYS) { f.date = idx; f.dows = []; } }
    var intent = /\bwhich ward\b/.test(t) ? "ward" : /\bwhich test\b/.test(t) ? "test" : /\b(when|what time|which hour|worst time)\b/.test(t) ? "hour" : /\b(which day|worst day)\b/.test(t) ? "day" : "why";
    return { filter: f, intent: intent };
  }
  function hourIn(h, rg) { return rg[0] <= rg[1] ? h >= rg[0] && h < rg[1] : h >= rg[0] || h < rg[1]; }
  function applyFilter(samples, f) {
    return samples.filter(function (s) {
      if (f.wards && f.wards.length && f.wards.indexOf(s.ward) < 0) return false;
      if (f.tests && f.tests.length && f.tests.indexOf(s.test) < 0) return false;
      if (f.pri !== null && f.pri !== undefined && s.pri !== f.pri) return false;
      if (f.hours && !hourIn(hourOf(s.order), f.hours)) return false;
      if (f.dows && f.dows.length && f.dows.indexOf(dowOf(s.order)) < 0) return false;
      if (f.date !== null && f.date !== undefined && dayOf(s.order) !== f.date) return false;
      if (f.cell && (dayOf(s.order) !== f.cell[0] || hourOf(s.order) !== f.cell[1])) return false;
      return true;
    });
  }
  function dateLabel(d) { var dt = new Date(START + "T00:00:00Z"); dt.setUTCDate(dt.getUTCDate() + d); return DOW[dt.getUTCDay() === 0 ? 6 : dt.getUTCDay() - 1].slice(0, 3).replace(/^./, function (c) { return c.toUpperCase(); }) + " " + dt.getUTCDate() + " " + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][dt.getUTCMonth()]; }
  function clock(t) { var m = Math.round(t % D); if (m < 0) m += D; return String(Math.floor(m / 60) % 24).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); }

  root.LabTAT = { DAYS: DAYS, START: START, WARDS: WARDS, TESTS: TESTS, STAGES: STAGES, LEVERS: LEVERS, TARGET: TARGET, TUBE_DOWN: TUBE_DOWN,
    simulate: simulate, summary: summary, bottleneck: bottleneck, pct: pct, mean: mean, parseQuestion: parseQuestion, applyFilter: applyFilter,
    hourOf: hourOf, dayOf: dayOf, dowOf: dowOf, dateLabel: dateLabel, clock: clock, hourIn: hourIn };
  if (typeof module !== "undefined") module.exports = root.LabTAT;
})(typeof window !== "undefined" ? window : globalThis);

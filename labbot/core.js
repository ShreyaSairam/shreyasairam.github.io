/* LabBot core: the lab map, A* path planning and the command parser.
   Pure functions, no DOM, so they can be tested on their own. */
(function (root) {
  "use strict";

  // 24 x 15 grid. '#' wall, '.' floor.
  var MAP = [
    "########################",
    "#......#.......#.......#",
    "#......#.......#.......#",
    "#......#.......#.......#",
    "#......###.##.####.##.##",
    "#......................#",
    "#......................#",
    "####.####......####.####",
    "#.......#......#.......#",
    "#.......#......#.......#",
    "#.......#......#.......#",
    "#..............#.......#",
    "#.......#..............#",
    "#.......#......#.......#",
    "########################"
  ];
  var W = MAP[0].length, H = MAP.length;

  // Stations: 'cell' is the object itself (blocked), 'at' is where the robot stops.
  var STATIONS = {
    A: { name: "Analyser A", short: "A", kind: "analyser", tests: "Blood count", cell: [17, 1], at: [17, 2] },
    B: { name: "Analyser B", short: "B", kind: "analyser", tests: "Chemistry", cell: [19, 1], at: [19, 2] },
    C: { name: "Analyser C", short: "C", kind: "analyser", tests: "Urine", cell: [21, 1], at: [21, 2] },
    centrifuge: { name: "Centrifuge", short: "Spin", kind: "centrifuge", cell: [11, 1], at: [11, 2] },
    fridge: { name: "Fridge", short: "Fridge", kind: "fridge", cell: [22, 10], at: [21, 10] },
    dock: { name: "Charging dock", short: "Dock", kind: "dock", cell: [1, 13], at: [2, 13] }
  };
  // Sample rack in reception: slot k sits at (k, 1), robot picks from (k, 2).
  var TEST_TO = { "Blood count": "A", "Chemistry": "B", "Urine": "C" };

  function makeSample(id, bed, test, urgent, slot) {
    return { id: id, bed: bed, test: test, urgent: urgent, slot: slot, where: "rack", spun: false, needsSpin: test === "Chemistry", done: false };
  }
  function freshSamples() {
    return [
      [1, "Blood count", false], [2, "Chemistry", true], [3, "Urine", false],
      [4, "Blood count", true], [5, "Chemistry", false], [6, "Urine", false]
    ].map(function (r) { return makeSample(r[0], r[0], r[1], r[2], r[0]); });
  }
  function byId(samples, id) { for (var i = 0; i < samples.length; i++) if (samples[i].id === id) return samples[i]; return null; }
  // Waiting to be dealt with: not tested yet and not already on an analyser.
  function pendingOf(samples) { return samples.filter(function (s) { return !s.done && !/^[ABC]$/.test(s.where); }); }

  function isWall(x, y) { return x < 0 || y < 0 || x >= W || y >= H || MAP[y][x] === "#"; }
  function fixedBlocked() {
    var b = {};
    Object.keys(STATIONS).forEach(function (k) { var c = STATIONS[k].cell; b[c[0] + "," + c[1]] = 1; });
    for (var k = 1; k <= 6; k++) b[k + ",1"] = 1;
    return b;
  }
  var FIXED = fixedBlocked();

  // A* on a 4-connected grid. blocked: {"x,y":1}. Returns {path, explored}.
  function astar(start, goal, blocked) {
    var key = function (p) { return p[0] + "," + p[1]; };
    var h = function (p) { return Math.abs(p[0] - goal[0]) + Math.abs(p[1] - goal[1]); };
    var open = [{ p: start, g: 0, f: h(start) }], came = {}, g = {}, closed = {}, explored = [];
    g[key(start)] = 0;
    while (open.length) {
      var bi = 0;
      for (var i = 1; i < open.length; i++) if (open[i].f < open[bi].f || (open[i].f === open[bi].f && open[i].g > open[bi].g)) bi = i;
      var cur = open.splice(bi, 1)[0], ck = key(cur.p);
      if (closed[ck]) continue;
      closed[ck] = 1; explored.push(cur.p);
      if (cur.p[0] === goal[0] && cur.p[1] === goal[1]) {
        var path = [cur.p], k = ck;
        while (came[k]) { path.unshift(came[k]); k = key(came[k]); }
        return { path: path, explored: explored };
      }
      [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(function (d) {
        var n = [cur.p[0] + d[0], cur.p[1] + d[1]], nk = key(n);
        if (isWall(n[0], n[1]) || FIXED[nk] || (blocked && blocked[nk]) || closed[nk]) return;
        var ng = cur.g + 1;
        if (g[nk] === undefined || ng < g[nk]) { g[nk] = ng; came[nk] = cur.p; open.push({ p: n, g: ng, f: ng + h(n) }); }
      });
    }
    return { path: null, explored: explored };
  }

  // ---------- Command parser ----------
  // Turns plain English into tool calls: move(sample, to) and goto(place).
  // 'to' can be "auto", meaning: the right analyser for that test, spinning first if needed.
  function placeIn(text) {
    var m = text.match(/analy[sz]er\s*([abc])\b/) || text.match(/\b(?:machine|station)\s*([abc])\b/);
    if (m) return m[1].toUpperCase();
    if (/\b(fridge|refrigerat\w*|storage|store it|cold)\b/.test(text)) return "fridge";
    if (/\b(centrifuge|spin)\b/.test(text)) return "centrifuge";
    if (/\b(dock|charg\w*|recharge|battery)\b/.test(text)) return "dock";
    if (/\b(reception|rack|front desk)\b/.test(text)) return "rack";
    if (/\b(right|correct|proper) (analy[sz]er|machine|place)\b/.test(text)) return "auto";
    return null;
  }
  function samplesIn(text, samples) {
    var pending = pendingOf(samples), ids = [], m;
    var addBed = function (n) {
      var hit = pending.filter(function (s) { return s.bed === n; })[0] || samples.filter(function (s) { return s.bed === n; })[0];
      if (hit && ids.indexOf(hit.id) < 0) ids.push(hit.id);
    };
    var re = /\b(?:bed|sample|tube|patient)\s*#?\s*(\d{1,2})\b/g;
    while ((m = re.exec(text))) addBed(+m[1]);
    var many = text.match(/\b(?:beds|samples|tubes|patients)\s+((?:\d{1,2}|,|and|&|\s)+)/);
    if (many) (many[1].match(/\d{1,2}/g) || []).forEach(function (d) { addBed(+d); });
    var pick = function (fn) { return pending.filter(fn).map(function (s) { return s.id; }); };
    if (!ids.length) {
      if (/\burgent\b/.test(text)) ids = pick(function (s) { return s.urgent; });
      ["blood count", "chemistry", "urine"].forEach(function (t) {
        var short = t.split(" ")[0];
        if (!ids.length && new RegExp("\\b" + short).test(text)) ids = pick(function (s) { return s.test.toLowerCase() === t; });
      });
    }
    if (!ids.length && /\b(all|every|everything|each)\b/.test(text)) ids = pick(function () { return true; });
    if (!ids.length && /\b(rest|remaining|others|leftover)\b/.test(text)) ids = ["REST"];
    return ids;
  }

  function parse(input, samples) {
    var text = (" " + input.toLowerCase() + " ").replace(/[.!?]/g, " ");
    var clauses = text.split(/\bthen\b|;|,\s*(?=(?:and\s+)?(?:take|bring|move|deliver|carry|put|go|send|drop|run|process|charge|spin|store))|\band\s+(?=(?:take|bring|move|deliver|carry|put|go|send|drop|run|process|charge|spin|store)\b)/);
    var steps = [], notes = [], claimed = {};
    clauses.forEach(function (c) {
      c = c.trim(); if (!c) return;
      var to = placeIn(c), ids = samplesIn(c, samples);
      var isGo = /\b(go|head|drive|return|park)\b/.test(c) && !ids.length;
      if ((/\b(charge|recharge|dock)\b/.test(c) && !ids.length) || (isGo && to === "dock")) { steps.push({ op: "goto", to: "dock" }); return; }
      if (isGo && to) { steps.push({ op: "goto", to: to }); return; }
      if (ids[0] === "REST") {
        ids = pendingOf(samples).filter(function (s) { return !claimed[s.id]; }).map(function (s) { return s.id; });
      }
      if (!ids.length) { if (c.length > 2) notes.push(c); return; }
      // urgent first when moving several
      var u = function (id) { var x = byId(samples, id); return x && x.urgent ? 1 : 0; };
      ids.sort(function (a, b) { return u(b) - u(a); });
      ids.forEach(function (id) { claimed[id] = 1; steps.push({ op: "move", sample: id, to: to && to !== "rack" ? to : (to === "rack" ? "rack" : "auto") }); });
    });
    return { steps: steps, unknown: notes };
  }

  function describe(step, samples) {
    if (step.op === "goto") return "Drive to " + (step.to === "rack" ? "reception" : STATIONS[step.to].name);
    var s = byId(samples, step.sample), dest;
    if (step.to === "auto") dest = STATIONS[TEST_TO[s.test]].name + " (right analyser for " + s.test.toLowerCase() + ")";
    else if (step.to === "rack") dest = "reception";
    else dest = STATIONS[step.to].name;
    return "Bed " + s.bed + " " + s.test.toLowerCase() + (s.urgent ? " (urgent)" : "") + " → " + dest;
  }

  root.LabCore = { MAP: MAP, W: W, H: H, STATIONS: STATIONS, TEST_TO: TEST_TO, freshSamples: freshSamples, makeSample: makeSample, byId: byId, pendingOf: pendingOf, isWall: isWall, FIXED: FIXED, astar: astar, parse: parse, describe: describe };
  if (typeof module !== "undefined") module.exports = root.LabCore;
})(typeof window !== "undefined" ? window : globalThis);

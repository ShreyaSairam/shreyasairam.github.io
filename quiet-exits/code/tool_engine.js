// Shared engine: turn a customer's 12 months into model inputs, then run both models.
const Engine = (() => {
  const sum = (a, i, j) => a.slice(i, j).reduce((s, v) => s + v, 0);
  const mean = (a, i, j) => sum(a, i, j) / (j - i);
  function trees(T, x, nclass) {
    const out = new Array(nclass).fill(0);
    T.forEach((t, k) => { const f = t[0], th = t[1], l = t[2], r = t[3], v = t[4]; let i = 0;
      while (f[i] >= 0) i = (x[f[i]] <= th[i]) ? l[i] : r[i]; out[k % nclass] += v[i]; });
    return out;
  }
  // c = {bal, inn, out(neg), cash(neg), salary, x (base drift features), tf (base type features), cash_ratio,
  //      overdraft6, pension, loanTrouble, hasLoan}
  function features(c, FEAT, TFEAT) {
    const b = c.bal, n = b.length, L = n - 1;
    const past6 = mean(b, n - 6, n), past3 = mean(b, n - 3, n), prior3 = mean(b, n - 6, n - 3);
    const E = c.end || b; const peak = Math.max(...E.slice(Math.max(0, n - 12)));
    const in3 = sum(c.inn, n - 3, n), inp3 = sum(c.inn, n - 6, n - 3), out3 = sum(c.out, n - 3, n);
    const cash3 = sum(c.cash, n - 3, n), sal3 = sum(c.salary, n - 3, n);
    let msc = 0; for (let i = L; i >= 0 && c.inn[i] <= 0; i--) msc++;
    const x = c.x.slice(), set = (name, v) => { const i = FEAT.indexOf(name); if (i >= 0) x[i] = v; };
    set("log_balance", Math.log10(Math.max(1, past6)));
    set("balance_trend", past3 / (prior3 + 1));
    set("balance_vs_peak", E[L] / (peak + 1));
    set("net_flow_3", (in3 - out3) / (past6 + 1));
    set("cash_share", cash3 / (out3 + 1));
    set("income_change", in3 / (inp3 + 1));
    set("regular_income", sal3 / (past6 + 1));
    set("months_since_credit", msc);
    set("overdraft_6", c.overdraft6);
    set("pension_6", c.pension ? 1 : 0);
    set("has_loan", c.hasLoan ? 1 : 0);
    set("loan_in_trouble", c.hasLoan && c.loanTrouble ? 1 : 0);
    const t = c.tf.slice(), tset = (name, v) => { const i = TFEAT.indexOf(name); if (i >= 0) t[i] = v; };
    const maxCash = Math.max(...c.cash.slice(n - 3, n).map(Math.abs)) * c.cash_ratio;
    tset("log_bal", Math.log10(Math.max(1, past6)));
    tset("bal_trend", past3 / (prior3 + 1));
    tset("bal_vs_peak", E[L] / (peak + 1));
    tset("in_vs_bal", in3 / (past6 + 1));
    tset("in_change", in3 / (inp3 + 1));
    tset("cash_share", Math.abs(cash3) / (Math.abs(out3) + 1));
    tset("max_cash_vs_bal", maxCash / (past6 + 1));
    tset("out_vs_in", Math.abs(out3) / (in3 + 1));
    tset("pension", c.pension ? 1 : 0);
    tset("overdraft", Math.min(c.overdraft6, 3));
    tset("loan_pay", c.loanPay ? 1 : 0);
    return { x, t, past6 };
  }
  function predict(M, c) {
    const { x, t, past6 } = features(c, M.feat, M.tfeat);
    const z = trees(M.drift_trees, x, 1)[0], p = 1 / (1 + Math.exp(-z));
    const s = trees(M.type_trees, t, 3), mx = Math.max(...s), e = s.map(v => Math.exp(v - mx)), es = e.reduce((a, b) => a + b, 0);
    return { p, pt: e.map(v => v / es), past6, atRisk: p * past6 * M.drop_frac };
  }
  return { features, predict };
})();
if (typeof module !== "undefined") module.exports = Engine;

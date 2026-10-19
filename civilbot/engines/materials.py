"""Concrete mix design (DoE / BRE, BS practice) and sieve analysis with BS 882 grading limits."""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt

# ---------------------------------------------------------------- DoE mix design (BRE "Design of normal concrete mixes", 1997)
# Table 2: approx. 28-day cube strength (MPa) at free w/c 0.5, OPC / CEM I 42.5
T2 = {"uncrushed": 42.0, "crushed": 49.0}
# Table 3: free-water content (kg/m³) by slump class [0–10, 10–30, 30–60, 60–180 mm] and max aggregate size
T3 = {10: {"uncrushed": [150, 180, 205, 225], "crushed": [180, 205, 230, 250]},
      20: {"uncrushed": [135, 160, 180, 195], "crushed": [170, 190, 210, 225]},
      40: {"uncrushed": [115, 140, 160, 175], "crushed": [155, 175, 190, 205]}}
SLUMP = [10, 30, 60, 180]


def _slump_class(slump):
    for k, lim in enumerate(SLUMP):
        if slump <= lim:
            return k
    return 3


def mix_design(fcu, slump=50, nmsa=20, agg="crushed", p600=50.0, rd=2.65, s=None, wc_max=None, c_min=None, fa=None,
               mc_fa=0.0, abs_fa=0.0, mc_ca=0.0, abs_ca=0.0, k=1.64) -> Result:
    if nmsa not in T3:
        raise InputError("المقاس الأكبر للركام في طريقة DoE لازم 10 أو 20 أو 40 mm")
    agg = agg.lower()
    if agg not in T2:
        raise InputError("agg = crushed (مكسّر) أو uncrushed (طبيعي)")
    if not 15 <= p600 <= 100:
        raise InputError("نسبة المار من منخل 600 µm لازم بين 15 و 100 %")
    r = Result("mix", "Concrete mix design (DoE / BRE method, BS)",
               inputs=dict(fcu=f"{fmt(fcu)} MPa (characteristic cube)", slump=f"{fmt(slump)} mm", max_agg=f"{fmt(nmsa)} mm {agg}",
                           fines=f"{fmt(p600)} % passing 600 µm", RD=f"{fmt(rd)} (SSD)",
                           moisture=f"sand MC {mc_fa}% / abs {abs_fa}% ; gravel MC {mc_ca}% / abs {abs_ca}%"))
    sd = s or 8.0
    fm = fcu + k * sd
    r.add("Target mean strength", "fm = fc + k·s (k = 1.64 for 5 % defectives)", f"s = {fmt(sd)} MPa" + ("" if s else " (fewer than 20 results)"),
          f"fm = {fmt(fm, 1)} MPa", "DoE Stage 1 / Fig. 3")
    f50 = T2[agg]
    wc = 0.5 - math.log10(fm / f50)
    r.add("Free water/cement ratio", "curve through Table 2 value at w/c 0.5: f = f₀.₅·10^(0.5 − w/c)", f"f₀.₅ = {fmt(f50)} MPa ({agg})",
          f"w/c = {fmt(wc, 3)}", "DoE Table 2 / Fig. 4 (curve approximation)")
    if wc_max and wc > wc_max:
        wc = wc_max
        r.warnings.append(f"تم تقليل w/c إلى الحد الأقصى للديمومة {fmt(wc_max, 2)}")
    if wc < 0.3:
        r.warnings.append("w/c أقل من 0.3: خارج نطاق طريقة DoE، استخدم ملدنات وخلطة تجريبية")
    W = T3[nmsa][agg][_slump_class(slump)]
    r.add("Free-water content", "Table 3 by slump class and aggregate", f"slump {fmt(slump)} mm , {nmsa} mm {agg}", f"W = {W} kg/m³", "DoE Table 3")
    C = W / wc
    if c_min and C < c_min:
        C = c_min
        r.warnings.append(f"تم رفع الأسمنت للحد الأدنى {fmt(c_min)} kg/m³")
    r.add("Cement content", "C = W/(w/c)", f"{W}/{fmt(wc, 3)}", f"C = {fmt(C, 1)} kg/m³", "DoE Stage 3")
    air = 0.01
    Vw, Vc = W / 1000, C / 3150
    TA = (1 - Vw - Vc - air) * rd * 1000
    D = C + W + TA
    r.add("Wet density & total aggregate", "TA = (1 − W/1000 − C/3150 − 1 % air)·RD·1000 ; D = C + W + TA",
          f"RD = {fmt(rd)}", f"TA = {fmt(TA, 1)} kg/m³ , D ≈ {fmt(D, 0)} kg/m³", "DoE Fig. 5 (absolute volume)")
    if fa is None:
        pf = 23 + 32 * math.exp(-p600 / 30) + 15 * (wc - 0.5) + 2.0 * _slump_class(slump) + {10: 8, 20: 0, 40: -5}[nmsa]
        pf = min(max(pf, 20), 60)
        r.add("Fine aggregate proportion", "estimated from Fig. 6 (fines %, w/c, slump, max size)", f"passing 600 µm = {fmt(p600)} %",
              f"fine = {fmt(pf, 1)} % of total aggregate (أدخل fa= لقيمة من المنحنى)", "DoE Fig. 6 (approx.)")
    else:
        pf = fa
        r.add("Fine aggregate proportion", "from Fig. 6 (user value)", "", f"fine = {fmt(pf, 1)} %", "DoE Fig. 6")
    FA = TA * pf / 100
    CA = TA - FA
    split = {10: "10 mm: 100 %", 20: "10 mm ⅓ , 20 mm ⅔", 40: "10 mm ⅙ , 20 mm ⅓ , 40 mm ½"}[nmsa]
    r.add("Fine & coarse aggregate (SSD)", "FA = TA × fine % ; CA = TA − FA", "", f"FA = {fmt(FA, 1)} , CA = {fmt(CA, 1)} kg/m³ ({split})", "DoE Stage 5")
    FAw = FA * (1 + (mc_fa - abs_fa) / 100)
    CAw = CA * (1 + (mc_ca - abs_ca) / 100)
    Wadj = W - FA * (mc_fa - abs_fa) / 100 - CA * (mc_ca - abs_ca) / 100
    r.add("Batch quantities after moisture correction", "W,batch = W − FA(MC − abs) − CA(MC − abs)", "",
          f"water {fmt(Wadj, 1)} , cement {fmt(C, 1)} , sand {fmt(FAw, 1)} , gravel {fmt(CAw, 1)} kg/m³")
    r.add("Proportions by weight (cement = 1)", "", f"fresh density ≈ {fmt(Wadj + C + FAw + CAw, 0)} kg/m³",
          f"1 : {fmt(FAw / C, 2)} : {fmt(CAw / C, 2)}  , w/c = {fmt(wc, 2)}")
    r.add("Per m³ (site)", "", "", f"{fmt(C / 50, 1)} cement bags (50 kg) , {fmt(FAw / 1600, 2)} m³ sand , {fmt(CAw / 1500, 2)} m³ gravel (loose)")
    r.warnings.append("طريقة DoE تعطي خلطة أولية: لازم خلطة تجريبية (trial mix) وتعديلها قبل التنفيذ")
    r.outputs = dict(fcr=fm, W=Wadj, C=C, FA=FAw, CA=CAw, wc=wc, air=air * 100,
                     vols=dict(water=Vw, cement=Vc, coarse=CA / (rd * 1000), fine=FA / (rd * 1000), air=air))
    return r


STD_SIEVES = [37.5, 20, 10, 5, 2.36, 1.18, 0.6, 0.3, 0.15]  # BS sieves for FM
# BS 882:1992 Table 5 (fine aggregate overall limits + grading zones C / M / F) and Table 4 (graded coarse)
BS882_FINE = {10: (100, 100), 5: (89, 100), 2.36: (60, 100), 1.18: (30, 100), 0.6: (15, 100), 0.3: (5, 70), 0.15: (0, 15)}
ZONES = {"C": {2.36: (60, 100), 1.18: (30, 90), 0.6: (15, 54), 0.3: (5, 40)},
         "M": {2.36: (65, 100), 1.18: (45, 100), 0.6: (25, 80), 0.3: (5, 48)},
         "F": {2.36: (80, 100), 1.18: (70, 100), 0.6: (55, 100), 0.3: (5, 70)}}
BS882_20 = {37.5: (100, 100), 20: (90, 100), 14: (40, 80), 10: (30, 60), 5: (0, 10)}
BS882_10 = {14: (100, 100), 10: (85, 100), 5: (0, 25), 2.36: (0, 5)}
LIMITS = {"fine": BS882_FINE, "20": BS882_20, "10": BS882_10, "57": BS882_20, "67": BS882_10}


def sieve(sizes, retained, spec="fine") -> Result:
    if len(sizes) != len(retained) or len(sizes) < 3:
        raise InputError("عدد المناخل لازم يساوي عدد الأوزان (3 على الأقل)")
    order = np.argsort(sizes)[::-1]
    sizes = [float(sizes[i]) for i in order]
    retained = [float(retained[i]) for i in order]
    total = sum(retained)
    if total <= 0:
        raise InputError("مجموع الأوزان صفر")
    cum = np.cumsum(retained)
    pret = cum / total * 100
    passing = 100 - pret
    r = Result("sieve", "Sieve analysis & gradation",
               inputs=dict(sieves=", ".join(fmt(s) for s in sizes) + " mm", retained=", ".join(fmt(m) for m in retained) + " g", spec=spec))
    rows = [f"{fmt(s)} mm: retained {fmt(m)} g , cum {fmt(c, 1)} % , passing {fmt(p, 1)} %" for s, m, c, p in zip(sizes, retained, pret, passing)]
    r.add("Gradation table", "\n".join(rows))
    fm_sum = sum(float(np.interp(math.log(s), np.log(sizes[::-1]), pret[::-1])) for s in STD_SIEVES if min(sizes) <= s <= max(sizes))
    fm = fm_sum / 100
    r.add("Fineness modulus", "FM = Σ(cumulative % retained on standard sieves)/100", "", f"FM = {fmt(fm, 3)}")

    def D(pct):
        ls = np.log10(sizes[::-1]); pp = passing[::-1]
        if pct < pp.min() or pct > pp.max():
            return None
        return float(10 ** np.interp(pct, pp, ls))
    D10, D30, D60 = D(10), D(30), D(60)
    cls = ""
    if D10 and D30 and D60:
        Cu, Cc = D60 / D10, D30**2 / (D10 * D60)
        p4 = float(np.interp(math.log(4.75), np.log(sizes[::-1]), passing[::-1])) if min(sizes) <= 4.75 <= max(sizes) else None
        sand = p4 is not None and p4 > 50
        good = (Cu >= 6 and 1 <= Cc <= 3) if sand else (Cu >= 4 and 1 <= Cc <= 3)
        cls = ("SW (well-graded sand)" if good else "SP (poorly-graded sand)") if sand else ("GW (well-graded gravel)" if good else "GP (poorly-graded gravel)")
        r.add("Grain-size parameters", "Cu = D60/D10 ; Cc = D30²/(D10·D60)", f"D10 = {fmt(D10, 3)} , D30 = {fmt(D30, 3)} , D60 = {fmt(D60, 3)} mm",
              f"Cu = {fmt(Cu, 2)} , Cc = {fmt(Cc, 2)} → {cls} (assuming fines < 5%)")
    lim = LIMITS.get(spec)
    fails = []
    if lim:
        for s, (lo, hi) in lim.items():
            if min(sizes) <= s <= max(sizes):
                p = float(np.interp(math.log(s), np.log(sizes[::-1]), passing[::-1]))
                if not lo - 1e-6 <= p <= hi + 1e-6:
                    fails.append(f"{fmt(s)} mm: {fmt(p, 1)}% (limit {lo}–{hi})")
        r.add(f"BS 882 compliance ({'fine aggregate, overall limits' if spec == 'fine' else spec + ' mm graded coarse aggregate'})", "", "",
              "✔ within limits" if not fails else "✘ " + " ; ".join(fails), "BS 882 Table 4 / 5")
        if fails:
            r.warnings.append("التدرج خارج حدود المواصفة")
        if spec == "fine":
            pp = lambda s_: float(np.interp(math.log(s_), np.log(sizes[::-1]), passing[::-1])) if min(sizes) <= s_ <= max(sizes) else None
            zone = next((z for z, lz in ZONES.items() if all(pp(k_) is None or lo <= pp(k_) <= hi for k_, (lo, hi) in lz.items())), None)
            p6 = pp(0.6)
            r.add("Grading zone", "C (coarse) / M (medium) / F (fine)", f"passing 600 µm = {fmt(p6, 1) if p6 is not None else '-'} %",
                  f"zone {zone}" if zone else "✘ لا يقع في أي منطقة", "BS 882 Table 5")
    r.outputs = dict(sizes=sizes, passing=list(passing), fm=fm, D10=D10, D30=D30, D60=D60, cls=cls, spec=spec, limits=lim)
    return r

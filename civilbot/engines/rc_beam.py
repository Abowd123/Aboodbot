"""Reinforced-concrete rectangular beam design to BS 8110-1:1997 (SI units).

Flexure (singly / doubly reinforced, clause 3.4.4.4), shear links (3.4.5), span/effective-depth check (3.4.6)
and bar selection. Inputs: b, h [mm], cover [mm] (nominal, to links), fcu (cube), fy, fyv [MPa], M [kN.m], V [kN].
"""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

BARS = [8, 10, 12, 16, 20, 25, 32, 40]                        # BS 4449 preferred sizes
AREA = {d: math.pi * d * d / 4 for d in range(6, 41)}        # any diameter (legacy callers)
AGG = 20.0          # max aggregate size, mm
KP = 0.156          # K' for redistribution ≤ 10 %  (BS 8110 3.4.4.4)
GM_S = 1.05         # γm steel (1997 amendment → 0.95fy)


def vc_bs(As, b, d, fcu, links=True):
    """Design concrete shear stress vc (BS 8110 Table 3.8), MPa."""
    p = min(100 * As / (b * d), 3.0)
    p = max(p, 0.15)
    depth = max(400 / d, 1.0) if links else 400 / d
    return 0.79 * p ** (1 / 3) * depth ** 0.25 / 1.25 * (min(fcu, 40) / 25) ** (1 / 3)


def as_min_ratio(fy):
    """Minimum tension steel, rectangular section (BS 8110 Table 3.25)."""
    return 0.0013 if fy >= 460 else 0.0024


def _fits(n, db, b, cover, ds):
    if n < 2:
        return False
    clear = (b - 2 * cover - 2 * ds - n * db) / (n - 1)
    return clear >= max(AGG + 5, db)                         # BS 8110 3.12.11.1: hagg + 5 mm


def select_bars(As_req, b, cover, ds, min_n=2):
    """Pick bar size & count (single layer if possible, else two layers)."""
    best = None
    for layers in (1, 2):
        for db in BARS[2:]:
            n = max(min_n, math.ceil(As_req / AREA[db]))
            per_layer = math.ceil(n / layers)
            if not _fits(per_layer, db, b, cover, ds):
                continue
            prov = n * AREA[db]
            cand = (prov, layers, db, n)
            if best is None or (cand[1], cand[0]) < (best[1], best[0]):
                best = cand
        if best:
            break
    if not best:
        return None
    prov, layers, db, n = best
    return {"n": n, "db": db, "As": prov, "layers": layers}


def _flexure(r, b, h, d, dp, fcu, fy, M, cover, ds):
    r.add("Effective depth", "d = h − cover − Ø_link − Ø_bar/2 (− layer offset)",
          f"h = {fmt(h)} , cover = {fmt(cover)} , Ø_link = {fmt(ds)}", f"d = {fmt(d)} mm")
    K = M * 1e6 / (fcu * b * d * d)
    r.add("Moment factor K", "K = M/(fcu·b·d²) ; K' = 0.156 (≤ 10 % redistribution)",
          f"K = {fmt(M)}×10⁶ / ({fmt(fcu)}×{fmt(b)}×{fmt(d)}²)", f"K = {fmt(K, 4)} {'≤' if K <= KP else '>'} K' = {KP}", "BS 8110 3.4.4.4")
    rho_min = as_min_ratio(fy)
    doubly, As_comp = False, 0.0
    if K <= KP:
        z = min(d * (0.5 + math.sqrt(0.25 - K / 0.9)), 0.95 * d)
        As_req = M * 1e6 / (0.95 * fy * z)
        r.add("Lever arm", "z = d[0.5 + √(0.25 − K/0.9)] ≤ 0.95d", f"d = {fmt(d)} mm", f"z = {fmt(z)} mm", "BS 8110 Eq. 9")
        r.add("Tension steel", "As = M/(0.95·fy·z)", f"{fmt(M)}×10⁶ / (0.95×{fmt(fy)}×{fmt(z)})", f"As = {fmt(As_req)} mm²", "BS 8110 Eq. 8")
    else:
        doubly = True
        r.warnings.append("K > K': القطاع يحتاج حديد ضغط (Doubly reinforced). يفضّل زيادة العمق إذا أمكن")
        z = d * (0.5 + math.sqrt(0.25 - KP / 0.9))
        x = (d - z) / 0.45
        As_comp = (K - KP) * fcu * b * d * d / (0.95 * fy * (d - dp))
        As_req = KP * fcu * b * d * d / (0.95 * fy * z) + As_comp
        r.add("Lever arm at K'", "z = d[0.5 + √(0.25 − K'/0.9)] ; x = (d − z)/0.45", "", f"z = {fmt(z)} mm , x = {fmt(x)} mm")
        r.add("Compression steel", "As' = (K − K')fcu·b·d²/(0.95fy(d − d'))", f"d' = {fmt(dp)} mm", f"As' = {fmt(As_comp)} mm²", "BS 8110 Eq. 10")
        r.add("Tension steel", "As = K'fcu·b·d²/(0.95fy·z) + As'", "", f"As = {fmt(As_req)} mm²", "BS 8110 Eq. 11")
        if dp / x > 0.37:
            r.warnings.append("d'/x > 0.37: حديد الضغط لا يصل للخضوع، اجهاده أقل من 0.95fy (BS 8110 3.4.4.4)")
    As_min = rho_min * b * h
    if As_req < As_min:
        r.warnings.append("الحديد المطلوب أقل من الحد الأدنى، تم استخدام As,min")
    As_use = max(As_req, As_min)
    r.add("Minimum / maximum steel", f"As,min = {rho_min*100:g}%·b·h ; As,max = 4%·b·h", "",
          f"As,min = {fmt(As_min)} mm² , As,max = {fmt(0.04*b*h)} mm²", "BS 8110 Table 3.25 / 3.12.6.1")
    sel = select_bars(As_use, b, cover, ds)
    if not sel:
        raise InputError("ما قدرت أرتب الحديد داخل عرض الكمرة حتى على طبقتين. زد العرض b")
    if sel["As"] > 0.04 * b * h:
        r.warnings.append("الحديد أكبر من 4% من مساحة القطاع: كبّر القطاع")
    r.add("Bar selection", "n = ⌈As / A_bar⌉ ; clear spacing ≥ hagg + 5 mm",
          f"use {sel['n']}Ø{sel['db']} in {sel['layers']} layer(s)", f"As,prov = {fmt(sel['As'])} mm²", "BS 8110 3.12.11.1")
    comp = None
    if doubly:
        comp = select_bars(As_comp, b, cover, ds)
        if comp:
            r.add("Compression bars", "", "", f"use {comp['n']}Ø{comp['db']} top , As',prov = {fmt(comp['As'])} mm²")
    hangers = comp or {"n": 2, "db": 12, "As": 2 * AREA[12], "layers": 1}
    return sel, hangers, doubly, As_use, As_comp, rho_min


def design(b, h, fcu, fy, M, V=0.0, cover=30.0, ds=10.0, fyv=None, d_prime=None, span=None, support="ss") -> Result:
    fyv = fyv or min(fy, 460)
    for name, v in dict(b=b, h=h, fcu=fcu, fy=fy).items():
        if v is None or v <= 0:
            raise InputError(f"القيمة {name} لازم تكون موجبة")
    if not 20 <= fcu <= 60:
        raise InputError("مقاومة المكعب fcu خارج مدى BS 8110 (20–60 MPa)")
    if fy not in (250, 460) and not 240 <= fy <= 500:
        raise InputError("إجهاد خضوع الحديد fy لازم 250 أو 460 MPa (BS 4449)")
    if h <= b / 4 or h > 3000 or b < 150:
        raise InputError("أبعاد الكمرة غير منطقية (b ≥ 150 mm)")
    M, V = abs(M), abs(V)
    r = Result("rc_beam", "RC rectangular beam design (BS 8110-1:1997)",
               inputs=dict(b=f"{fmt(b)} mm", h=f"{fmt(h)} mm", cover=f"{fmt(cover)} mm", fcu=f"{fmt(fcu)} MPa",
                           fy=f"{fmt(fy)} MPa", fyv=f"{fmt(fyv)} MPa", M=f"{fmt(M)} kN·m", V=f"{fmt(V)} kN"))
    base_steps = list(r.steps)
    d = h - cover - ds - 10.0
    dp = d_prime or (cover + ds + 8)
    for _it in range(4):
        r.steps = list(base_steps)
        r.warnings = []
        sel, hangers, doubly, As_req, As_comp, rho_min = _flexure(r, b, h, d, dp, fcu, fy, M, cover, ds)
        d_act = h - cover - ds - sel["db"] / 2 - (0 if sel["layers"] == 1 else (sel["db"] / 2 + 12.5))
        if abs(d_act - d) < 1.0:
            break
        d = d_act
    d = d_act
    # capacity with provided steel (rectangular stress block 0.45fcu over 0.9x)
    As = sel["As"]
    Asp = hangers["As"] if doubly else 0.0
    x = (0.95 * fy * (As - Asp)) / (0.45 * fcu * 0.9 * b)
    x = max(x, 1e-6)
    z = min(d - 0.45 * x, 0.95 * d)
    Mu_cap = (0.95 * fy * (As - Asp) * z + 0.95 * fy * Asp * (d - dp)) / 1e6
    r.add("Capacity with provided steel", "x = 0.95fy(As − As')/(0.405fcu·b) ; Mu = 0.95fy(As − As')z + 0.95fy·As'(d − d')",
          f"x = {fmt(x)} mm (x/d = {fmt(x/d, 3)}) , z = {fmt(z)} mm",
          f"Mu = {fmt(Mu_cap)} kN·m {'≥' if Mu_cap >= M else '<'} M = {fmt(M)} kN·m {'✔' if Mu_cap >= M * 0.999 else '✘'}", "BS 8110 Fig. 3.3")
    if Mu_cap < M * 0.999:
        r.warnings.append("السعة أقل من المطلوب بعد اختيار الحديد. زد عدد الأسياخ أو العمق")
    if x / d > 0.5:
        r.warnings.append("x/d > 0.5: تجاوز حد الليونة (BS 8110 3.4.4.4)")
    # ---------- shear (3.4.5) ----------
    sh = {}
    if V > 0:
        v = V * 1e3 / (b * d)
        vmax = min(0.8 * math.sqrt(fcu), 5.0)
        vc = vc_bs(As, b, d, fcu)
        r.add("Design shear stress", "v = V/(b·d) ≤ min(0.8√fcu , 5 MPa)", f"{fmt(V)}×1000/({fmt(b)}×{fmt(d)})",
              f"v = {fmt(v, 3)} MPa ≤ {fmt(vmax, 3)} {'✔' if v <= vmax else '✘'}", "BS 8110 3.4.5.2")
        if v > vmax:
            raise InputError(f"القص كبير جداً: v = {fmt(v, 3)} > {fmt(vmax, 3)} MPa. كبّر القطاع")
        r.add("Concrete shear stress", "vc = 0.79(100As/bd)^⅓(400/d)^¼/γm × (fcu/25)^⅓",
              f"100As/bd = {fmt(min(100*As/(b*d), 3), 3)} , 400/d = {fmt(max(400/d, 1), 3)}", f"vc = {fmt(vc, 3)} MPa", "BS 8110 Table 3.8")
        Asv = 2 * AREA[int(round(ds))]
        s_max = 0.75 * d
        if v <= vc + 0.4:
            s_req = Asv * 0.95 * fyv / (0.4 * b)
            note = "v ≤ vc + 0.4 → minimum links: Asv/sv = 0.4b/(0.95fyv)"
        else:
            s_req = Asv * 0.95 * fyv / (b * (v - vc))
            note = "v > vc + 0.4 → Asv/sv = b(v − vc)/(0.95fyv)"
        s = min(s_req, s_max)
        s_use = max(75, math.floor(s / 25) * 25)
        r.add("Shear links", "sv ≤ min(required , 0.75d)", f"{note} ; s,req = {fmt(s_req)} mm , 0.75d = {fmt(s_max)} mm",
              f"Use Ø{int(ds)} @ {s_use} mm (2 legs)", "BS 8110 Table 3.7 / 3.4.5.5")
        sh = dict(v=v, vc=vc, Vc=vc * b * d / 1e3, s=s_use, Asv=Asv)
    # ---------- deflection (3.4.6) ----------
    if span:
        basic = {"ss": 20, "cont": 26, "cant": 7}.get(support, 20)
        fs = 2 * fy * As_req / (3 * As)
        mf = min(2.0, 0.55 + (477 - fs) / (120 * (0.9 + M * 1e6 / (b * d * d))))
        mfc = min(1.5, 1 + (100 * Asp / (b * d)) / (3 + 100 * Asp / (b * d))) if Asp else 1.0
        allow = basic * mf * mfc * (1 if span <= 10 else 10 / span)
        actual = span * 1000 / d
        r.add("Span / effective depth", "L/d ≤ basic × MF(tension) × MF(comp.) ; MF = 0.55 + (477 − fs)/(120(0.9 + M/bd²)) ≤ 2",
              f"basic = {basic} , fs = {fmt(fs)} MPa , MF = {fmt(mf, 3)}",
              f"L/d = {fmt(actual, 2)} ≤ {fmt(allow, 2)} {'✔' if actual <= allow else '✘'}", "BS 8110 Tables 3.9–3.11")
        if actual > allow:
            r.warnings.append("نسبة البحر/العمق أكبر من المسموح: زد العمق أو الحديد")
    r.outputs = dict(d=d, As_req=As_req, bars=sel, top_bars=hangers, doubly=doubly, As_comp=As_comp,
                     x=x, z=z, Mu_cap=Mu_cap, phiMn=Mu_cap, rho_min=rho_min,
                     stirrup_d=ds, stirrup_s=sh.get("s"), shear=sh, b=b, h=h, cover=cover)
    return r

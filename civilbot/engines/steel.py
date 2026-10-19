"""Structural steel to BS 5950-1:2000: beams (4.2–4.3, Annex B), struts and beam-columns (4.7–4.8, Annex C),
bolted fin-plate shear connection (6.3) and column base plate (4.13). SI units (mm, N, MPa).
Section library: IPE / HEA / HEB, properties computed from plate dimensions + root fillets."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

E = 205000.0          # BS 5950 3.1.3
G_ = 77200.0
# h, b, tw, tf (mm)
LIB = {}
for k, v in {100: (100, 55, 4.1, 5.7), 120: (120, 64, 4.4, 6.3), 140: (140, 73, 4.7, 6.9), 160: (160, 82, 5.0, 7.4), 180: (180, 91, 5.3, 8.0),
             200: (200, 100, 5.6, 8.5), 220: (220, 110, 5.9, 9.2), 240: (240, 120, 6.2, 9.8), 270: (270, 135, 6.6, 10.2), 300: (300, 150, 7.1, 10.7),
             330: (330, 160, 7.5, 11.5), 360: (360, 170, 8.0, 12.7), 400: (400, 180, 8.6, 13.5), 450: (450, 190, 9.4, 14.6), 500: (500, 200, 10.2, 16.0),
             550: (550, 210, 11.1, 17.2), 600: (600, 220, 12.0, 19.0)}.items():
    LIB[f"IPE{k}"] = v
for k, v in {100: (96, 100, 5.0, 8.0), 120: (114, 120, 5.0, 8.0), 140: (133, 140, 5.5, 8.5), 160: (152, 160, 6.0, 9.0), 180: (171, 180, 6.0, 9.5),
             200: (190, 200, 6.5, 10.0), 220: (210, 220, 7.0, 11.0), 240: (230, 240, 7.5, 12.0), 260: (250, 260, 7.5, 12.5), 280: (270, 280, 8.0, 13.0),
             300: (290, 300, 8.5, 14.0)}.items():
    LIB[f"HEA{k}"] = v
for k, v in {100: (100, 100, 6.0, 10.0), 120: (120, 120, 6.5, 11.0), 140: (140, 140, 7.0, 12.0), 160: (160, 160, 8.0, 13.0), 180: (180, 180, 8.5, 14.0),
             200: (200, 200, 9.0, 15.0), 220: (220, 220, 9.5, 16.0), 240: (240, 240, 10.0, 17.0), 260: (260, 260, 10.0, 17.5), 280: (280, 280, 10.5, 18.0),
             300: (300, 300, 11.0, 19.0)}.items():
    LIB[f"HEB{k}"] = v


RADII = {"IPE": {100: 7, 120: 7, 140: 7, 160: 9, 180: 9, 200: 12, 220: 12, 240: 15, 270: 15, 300: 15, 330: 18, 360: 18, 400: 21,
                  450: 21, 500: 21, 550: 24, 600: 24},
         "HE": {100: 12, 120: 12, 140: 12, 160: 15, 180: 15, 200: 18, 220: 18, 240: 21, 260: 24, 280: 24, 300: 27}}


def props(h, b, tw, tf, r=0.0):
    hw = h - 2 * tf
    af = (1 - math.pi / 4) * r * r          # one root fillet
    yf = h / 2 - tf - 0.2234 * r            # its centroid from the x-axis
    A = 2 * b * tf + hw * tw + 4 * af
    Ix = (b * h**3 - (b - tw) * hw**3) / 12 + 4 * af * yf**2
    Iy = (2 * tf * b**3 + hw * tw**3) / 12 + 4 * af * (tw / 2 + 0.2234 * r) ** 2
    Sx, Sy = Ix / (h / 2), Iy / (b / 2)
    Zx = b * tf * (h - tf) + tw * hw**2 / 4 + 4 * af * yf
    Zy = tf * b**2 / 2 + hw * tw**2 / 4 + 4 * af * (tw / 2 + 0.2234 * r)
    J = (2 * b * tf**3 + (h - tf) * tw**3) / 3
    ho = h - tf
    Cw = Iy * ho**2 / 4
    rts = math.sqrt(math.sqrt(Iy * Cw) / Sx)
    return dict(h=h, b=b, tw=tw, tf=tf, hw=hw, A=A, Ix=Ix, Iy=Iy, Sx=Sx, Sy=Sy, Zx=Zx, Zy=Zy, rx=math.sqrt(Ix / A), ry=math.sqrt(Iy / A),
                J=J, Cw=Cw, ho=ho, rts=rts, mass=A * 7850e-6)


def section(name=None, h=None, b=None, tw=None, tf=None):
    if name:
        key = name.upper().replace(" ", "")
        if key not in LIB:
            raise InputError(f"مقطع غير موجود: {name}. المتاح IPE100–600 / HEA100–300 / HEB100–300 أو أدخل h b tw tf")
        fam = "IPE" if key.startswith("IPE") else "HE"
        return key, props(*LIB[key], r=RADII[fam][int(key[3:])])
    if None in (h, b, tw, tf):
        raise InputError("أدخل اسم المقطع (مثل IPE300) أو أبعاده h b tw tf")
    return f"I {fmt(h)}×{fmt(b)}×{fmt(tw)}×{fmt(tf)}", props(h, b, tw, tf)



ROBERTSON = {"a": 2.0, "b": 3.5, "c": 5.5, "d": 8.0}


def py_of(grade, t):
    """Design strength py (BS 5950 Table 9) from nominal grade 275/355 and thickness."""
    g = 355 if grade >= 300 else 275
    for lim, dv in ((16, 0), (40, 10), (63, 20), (80, 30), (100, 40)):
        if t <= lim:
            return g - dv
    return g - 50


def classify(p, py):
    eps = math.sqrt(275 / py)
    bT = (p["b"] / 2) / p["tf"]
    dt = p["hw"] / p["tw"]
    fl = 1 if bT <= 9 * eps else 2 if bT <= 10 * eps else 3 if bT <= 15 * eps else 4
    wb = 1 if dt <= 80 * eps else 2 if dt <= 100 * eps else 3 if dt <= 120 * eps else 4
    return max(fl, wb), bT, dt, eps


def perry(py, lam, lam0, alpha):
    """Perry-Robertson strength (Annex B / C)."""
    if lam <= 0:
        return py
    pE = math.pi**2 * E / lam**2
    eta = max(0.0, alpha * (lam - lam0) / 1000)
    phi = (py + (eta + 1) * pE) / 2
    return pE * py / (phi + math.sqrt(phi**2 - pE * py))


def _flexure(p, py, LE, mLT=1.0, Fv=0.0):
    cls, bT, dt, eps = classify(p, py)
    S, Z = p["Zx"], p["Sx"]                 # plastic / elastic modulus (p uses AISC letters)
    Av = p["h"] * p["tw"]
    Pv = 0.6 * py * Av
    if cls <= 2:
        Mc = min(py * S, 1.2 * py * Z)
        if Fv > 0.6 * Pv:
            rho = (2 * Fv / Pv - 1) ** 2
            Sv = p["tw"] * p["h"] ** 2 / 4
            Mc = min(py * (S - rho * Sv), 1.2 * py * Z)
    else:
        Mc = py * Z
    bw = 1.0 if cls <= 2 else Z / S
    lam = LE / p["ry"]
    x = p["h"] / p["tf"]
    v = 1 / (1 + 0.05 * (lam / x) ** 2) ** 0.25
    lamLT = 0.9 * v * lam * math.sqrt(bw)
    lamL0 = 0.4 * math.sqrt(math.pi**2 * E / py)
    pb = perry(py, lamLT, lamL0, 7.0)
    Mb = pb * (S if cls <= 2 else Z)
    return dict(cls=cls, bT=bT, dt=dt, eps=eps, Mc=Mc, Mb=Mb / mLT, pb=pb, lam=lam, lamLT=lamLT, lamL0=lamL0, v=v, Pv=Pv, Av=Av,
                Mcap=min(Mc, Mb / mLT))


def beam(M, V, Lb, Fy=355.0, mLT=1.0, name=None, dims=None, L=None, w_service=None, defl_lim=360, family="IPE") -> Result:
    """M kN·m, V kN, Lb m (effective length for LTB), optional L m + w_service (imposed) kN/m for deflection."""
    r = Result("steel_beam", "Steel beam design (BS 5950-1:2000)",
               inputs=dict(M=f"{fmt(M)} kN·m", V=f"{fmt(V)} kN", LE=f"{fmt(Lb)} m", grade=f"S{355 if Fy >= 300 else 275}", mLT=fmt(mLT),
                           deflection=f"L = {fmt(L)} m , w = {fmt(w_service)} kN/m , L/{defl_lim}" if L and w_service else "-"))
    cands = [name] if name or dims else [k for k in LIB if k.startswith(family.upper())]
    chosen = None
    for nm in cands:
        key, p = section(None, *dims) if dims else section(nm)
        py = py_of(Fy, p["tf"])
        f = _flexure(p, py, Lb * 1000, mLT, V * 1e3)
        Mcap = f["Mcap"] / 1e6
        Pv = f["Pv"] / 1e3
        dmax = 5 * w_service * (L * 1000) ** 4 / (384 * E * p["Ix"]) if L and w_service else None
        ok = Mcap >= M and Pv >= V and f["cls"] <= 3 and (dmax is None or dmax <= L * 1000 / defl_lim)
        chosen = (key, p, f, Mcap, Pv, dmax, py)
        if ok or name or dims:
            break
    else:
        raise InputError("ما في مقطع في المكتبة يحقق المطلوب. جرب HEB أو قلل LE")
    key, p, f, Mcap, Pv, dmax, py = chosen
    r.inputs["section"] = key
    r.add("Section", "A, Ix, S (plastic), Z (elastic), ry", f"{key}: D = {fmt(p['h'])} , B = {fmt(p['b'])} , t = {fmt(p['tw'])} , T = {fmt(p['tf'])}",
          f"A = {fmt(p['A'], 0)} mm² , Ix = {fmt(p['Ix']/1e6, 2)}×10⁶ mm⁴ , Sx = {fmt(p['Zx']/1e3, 1)}×10³ mm³ , {fmt(p['mass'], 1)} kg/m")
    r.add("Design strength", "py from grade & flange thickness T", f"T = {fmt(p['tf'])} mm", f"py = {fmt(py)} MPa", "BS 5950 Table 9")
    r.add("Section classification", "b/T ≤ 9ε (class 1), 10ε (2), 15ε (3) ; d/t ≤ 80ε / 100ε / 120ε ; ε = √(275/py)",
          f"b/T = {fmt(f['bT'], 2)} , d/t = {fmt(f['dt'], 2)} , ε = {fmt(f['eps'], 3)}", f"Class {f['cls']}", "BS 5950 Table 11")
    if f["cls"] == 4:
        r.warnings.append("المقطع Class 4 (نحيف): يلزم خصائص فعالة (BS 5950 3.6)")
    r.add("Shear capacity", "Pv = 0.6·py·Av , Av = t·D", f"Av = {fmt(f['Av'], 0)} mm²",
          f"Pv = {fmt(Pv, 2)} kN {'≥' if Pv >= V else '<'} Fv = {fmt(V)} kN" + (" (high shear)" if V * 1e3 > 0.6 * f["Pv"] else ""), "BS 5950 4.2.3")
    r.add("Moment capacity (restrained)", "Mc = py·S ≤ 1.2py·Z (class 1/2) ; py·Z (class 3)", "", f"Mc = {fmt(f['Mc']/1e6, 2)} kN·m", "BS 5950 4.2.5")
    r.add("Lateral-torsional buckling", "λLT = u·v·λ·√βw (u = 0.9) ; pb from Annex B.2.1 (αLT = 7.0) ; Mb = pb·S",
          f"λ = LE/ry = {fmt(f['lam'], 1)} , v = {fmt(f['v'], 3)} , λLT = {fmt(f['lamLT'], 1)} (λL0 = {fmt(f['lamL0'], 1)})",
          f"pb = {fmt(f['pb'], 1)} MPa → Mb/mLT = {fmt(f['Mb']/1e6, 2)} kN·m", "BS 5950 4.3.6 / Annex B")
    r.add("Bending check", "M ≤ min(Mc , Mb/mLT)", "", f"capacity = {fmt(Mcap, 2)} kN·m {'≥' if Mcap >= M else '<'} M = {fmt(M)} {'✔' if Mcap >= M else '✘'}")
    if dmax is not None:
        r.add("Deflection under imposed load", "δ = 5wL⁴/384EI ≤ L/360", "",
              f"δ = {fmt(dmax, 2)} mm vs {fmt(L*1000/defl_lim, 2)} mm {'✔' if dmax <= L*1000/defl_lim else '✘'}", "BS 5950 Table 8")
    if f["dt"] > 70 * f["eps"]:
        r.warnings.append("d/t > 70ε: افحص انبعاج القص للجذع (BS 5950 4.4.5)")
    for cond, msg in ((Mcap < M, "مقاومة الانحناء غير كافية"), (Pv < V, "مقاومة القص غير كافية"),
                      (dmax is not None and dmax > L * 1000 / defl_lim, "الترخيم أكبر من المسموح")):
        if cond:
            r.warnings.append(msg)
    r.outputs = dict(section=key, p=p, phiMn=Mcap, phiVn=Pv, Mc=Mcap, Pv=Pv, util=max(M / Mcap, V / Pv))
    return r


def _curves(key):
    """Strut curves (BS 5950 Table 23): rolled H (HE) x-x b / y-y c ; rolled I (IPE) x-x a / y-y b."""
    return ("b", "c") if key.startswith("HE") else ("a", "b")


def column(N, LEy, Fy=355.0, Mx=0.0, Lb=None, name=None, dims=None, LEx=None, family="HEB", mLT=1.0) -> Result:
    """N kN (compression), LEy weak-axis effective length m, LEx strong axis (default = LEy), Mx kN·m."""
    r = Result("steel_col", "Steel column / beam-column (BS 5950-1:2000)",
               inputs=dict(N=f"{fmt(N)} kN", LEy=f"{fmt(LEy)} m", LEx=f"{fmt(LEx or LEy)} m", Mx=f"{fmt(Mx)} kN·m",
                           grade=f"S{355 if Fy >= 300 else 275}"))
    cands = [name] if name or dims else [k for k in LIB if k.startswith(family.upper())]
    res = None
    for nm in cands:
        key, p = section(None, *dims) if dims else section(nm)
        py = py_of(Fy, p["tf"])
        cx, cy = _curves(key)
        lx, ly = (LEx or LEy) * 1000 / p["rx"], LEy * 1000 / p["ry"]
        lam0 = 0.2 * math.sqrt(math.pi**2 * E / py)
        pcx, pcy = perry(py, lx, lam0, ROBERTSON[cx]), perry(py, ly, lam0, ROBERTSON[cy])
        Pc = min(pcx, pcy) * p["A"] / 1e3
        cls = classify(p, py)[0]
        ratio = N / Pc
        f = None
        if Mx:
            f = _flexure(p, py, (Lb or LEy) * 1000, mLT)
            ratio = max(N / Pc + Mx * 1e6 / (py * p["Sx"]), N / (min(pcy, pcx) * p["A"] / 1e3) + Mx * 1e6 / f["Mb"],
                        N * 1e3 / (p["A"] * py) + Mx * 1e6 / f["Mc"])
        ok = max(lx, ly) <= 180 and ratio <= 1.0 and cls <= 3
        res = (key, p, py, lx, ly, pcx, pcy, Pc, ratio, f, cx, cy, cls)
        if ok or name or dims:
            break
    else:
        raise InputError("ما في مقطع يحقق المطلوب. جرب family=HEB أو قلل الطول")
    key, p, py, lx, ly, pcx, pcy, Pc, ratio, f, cx, cy, cls = res
    r.inputs["section"] = key
    r.add("Section", "", f"{key} , py = {fmt(py)} MPa (Table 9)", f"A = {fmt(p['A'], 0)} mm² , rx = {fmt(p['rx'], 1)} , ry = {fmt(p['ry'], 1)} mm , {fmt(p['mass'], 1)} kg/m")
    r.add("Slenderness", "λ = LE/r ≤ 180", f"λx = {fmt(lx, 1)} , λy = {fmt(ly, 1)}", f"governing λ = {fmt(max(lx, ly), 1)}", "BS 5950 4.7.3")
    r.add("Compressive strength (Perry-Robertson)", "pc from Annex C ; η = a(λ − λ0)/1000",
          f"curves x-x '{cx}' , y-y '{cy}' (Table 23)", f"pcx = {fmt(pcx, 1)} , pcy = {fmt(pcy, 1)} MPa", "BS 5950 Table 24 / Annex C")
    r.add("Compression resistance", "Pc = Ag·pc", "", f"Pc = {fmt(Pc, 1)} kN {'≥' if Pc >= N else '<'} Fc = {fmt(N)}", "BS 5950 4.7.4")
    if cls == 4:
        r.warnings.append("المقطع Class 4 للضغط: يلزم مساحة فعالة (BS 5950 4.7.4)")
    if f is not None:
        r.add("Combined compression + bending (simplified)", "Fc/Pc + Mx/(py·Zx) ≤ 1 ; Fc/Pcy + mLT·Mx/Mb ≤ 1 ; Fc/(Ag·py) + Mx/Mcx ≤ 1",
              f"Mb = {fmt(f['Mb']/1e6, 1)} kN·m , Mc = {fmt(f['Mc']/1e6, 1)} kN·m", f"interaction = {fmt(ratio, 3)} {'✔' if ratio <= 1 else '✘'}",
              "BS 5950 4.8.3.2 / 4.8.3.3.1")
    r.outputs = dict(section=key, p=p, phiPn=Pc, Pc=Pc, ratio=ratio)
    return r


BOLT_PS = {"4.6": (160, 460), "8.8": (375, 1000), "10.9": (400, 1300)}       # shear ps , bearing pbb (Tables 30–31)
AS_TENSILE = {12: 84.3, 16: 157, 20: 245, 22: 303, 24: 353, 27: 459, 30: 561}


def shear_tab(V, d=20, grade="8.8", tp=10, Fy=275, tw_beam=7.1, weld=6, pbs_beam=460) -> Result:
    """Fin-plate (single row of bolts, standard 2 mm clearance holes, pitch 3d, end distance 1.5d)."""
    g = str(grade).upper().replace("N", "").replace("X", "")
    g = {"A325": "8.8", "A490": "10.9"}.get(g, g)
    if g not in BOLT_PS or d not in AS_TENSILE:
        raise InputError("درجة البراغي 4.6 / 8.8 / 10.9 ، والقطر من 12–30 mm")
    ps, pbb = BOLT_PS[g]
    py = py_of(Fy, tp)
    pbs = 460 if Fy < 300 else 550
    pw = 220 if Fy < 300 else 250
    dh = d + (2 if d <= 24 else 3)
    s = math.ceil(3 * d / 5) * 5
    Le = math.ceil(max(1.5 * d, 1.25 * dh) / 5) * 5
    r = Result("shear_tab", "Bolted fin-plate shear connection (BS 5950-1:2000)",
               inputs=dict(V=f"{fmt(V)} kN", bolts=f"M{d} grade {g}", plate=f"t = {fmt(tp)} mm , py = {fmt(py)} MPa",
                           beam_web=f"t = {fmt(tw_beam)} mm", weld=f"{fmt(weld)} mm fillet , pw = {pw} MPa"))

    def caps(n):
        Lp = 2 * Le + (n - 1) * s
        bolt = n * ps * AS_TENSILE[d] / 1e3
        bb = n * d * min(tp, tw_beam) * pbb / 1e3
        bp = min(n * d * tp * pbs, 0.5 * n * Le * tp * pbs) / 1e3
        bw = n * d * tw_beam * pbs_beam / 1e3
        Av = 0.9 * Lp * tp
        sh = 0.6 * py * Av / 1e3
        Avnet = (Lp - n * dh) * tp
        net = 0.7 * py * 1.2 * Avnet / 1e3
        Lv = Lp - Le
        bs = 0.6 * py * tp * (Lv + 1.2 * (Le - 0.5 * dh)) / 1e3
        wcap = 2 * 0.7 * weld * pw * Lp / 1e3
        return dict(Lp=Lp, bolt=bolt, bb=bb, bp=bp, bw=bw, sh=sh, net=net, bs=bs, weld=wcap)
    n = 2
    while True:
        c = caps(n)
        cap = min(v for k, v in c.items() if k != "Lp")
        if cap >= V or n >= 12:
            break
        n += 1
    Lp = c["Lp"]
    r.add("Geometry", "pitch 3d ≥ 2.5d ; end distance ≥ 1.25D_hole ; hole = d + 2", f"s = {s} , e = {Le} , hole = {dh} mm",
          f"n = {n} bolts , plate {fmt(Lp)} × {fmt(2*Le + 10)} × {fmt(tp)} mm", "BS 5950 6.2")
    r.add("Bolt shear", "Ps = ps·As per bolt", f"ps = {ps} MPa , As = {AS_TENSILE[d]} mm²", f"{fmt(c['bolt'], 1)} kN", "BS 5950 6.3.2 / Table 30")
    r.add("Bearing", "Pbb = d·tp·pbb (bolt) ; Pbs = d·tp·pbs ≤ ½·e·tp·pbs (ply)", f"pbb = {pbb} , pbs = {pbs} MPa",
          f"bolt {fmt(c['bb'], 1)} , plate {fmt(c['bp'], 1)} , web {fmt(c['bw'], 1)} kN", "BS 5950 6.3.3 / Tables 31–32")
    r.add("Plate shear (gross & net)", "Pv = 0.6py·0.9A ; Pv,net = 0.7py·Ke·Av,net (Ke = 1.2)", "", f"gross {fmt(c['sh'], 1)} , net {fmt(c['net'], 1)} kN", "BS 5950 6.2.3–6.2.4")
    r.add("Block shear", "Pr = 0.6py·t[Lv + Ke(Lt − kDt)] , k = 0.5", "", f"Pr = {fmt(c['bs'], 1)} kN", "BS 5950 6.2.4")
    r.add("Fillet welds to support (both sides)", "Pw = 2 × 0.7s·pw·L", f"s = {weld} mm , L = {fmt(Lp)} mm", f"Pw = {fmt(c['weld'], 1)} kN", "BS 5950 6.8.7")
    r.add("Connection capacity", "min of all checks", "", f"capacity = {fmt(cap, 1)} kN {'≥' if cap >= V else '<'} V = {fmt(V)} {'✔' if cap >= V else '✘'}")
    if cap < V:
        r.warnings.append("الوصلة غير كافية: زد سمك اللوح أو عدد البراغي")
    if tp > 0.5 * d:
        r.warnings.append("سمك اللوح > 0.5d: الوصلة قد لا تكون مرنة كفاية (SCI P212)")
    r.outputs = dict(n=n, d=d, s=s, Le=Le, dh=dh, Lp=Lp, tp=tp, weld=weld, cap=cap, width=2 * Le + 10)
    return r


def base_plate(N, d, bf, fcu=30.0, Fy=275.0, tf=None, tw=None) -> Result:
    """Concentric base plate by the effective area method (BS 5950 4.13.2.2)."""
    tf = tf or 0.063 * d
    tw = tw or 0.037 * d
    w = 0.6 * fcu
    r = Result("base_plate", "Column base plate (BS 5950-1:2000 4.13, effective area)",
               inputs=dict(N=f"{fmt(N)} kN", column=f"D = {fmt(d)} , B = {fmt(bf)} , T ≈ {fmt(tf, 1)} , t ≈ {fmt(tw, 1)} mm",
                           fcu=f"{fmt(fcu)} MPa", grade=f"S{355 if Fy >= 300 else 275}"))
    Areq = N * 1e3 / w

    def aeff(c):
        return 2 * (bf + 2 * c) * (tf + 2 * c) + max(d - 2 * tf - 2 * c, 0) * (tw + 2 * c)
    lo, hi = 0.0, max(d, bf)
    for _ in range(80):
        c = (lo + hi) / 2
        lo, hi = (c, hi) if aeff(c) < Areq else (lo, c)
    c = hi
    Lp = math.ceil((d + 2 * c + 20) / 10) * 10
    Bp = math.ceil((bf + 2 * c + 20) / 10) * 10
    Lp, Bp = max(Lp, d + 100), max(Bp, bf + 100)
    r.add("Bearing strength", "w = 0.6fcu ; Aeff ≥ N/w", f"w = {fmt(w)} MPa", f"Aeff ≥ {Areq:,.0f} mm²", "BS 5950 4.13.1")
    r.add("Effective projection", "Aeff = 2(B + 2c)(T + 2c) + (D − 2T − 2c)(t + 2c)", "", f"c = {fmt(c, 1)} mm → plate {fmt(Lp)} × {fmt(Bp)} mm")
    t = c * math.sqrt(3 * w / py_of(Fy, 40))
    t_use = max(math.ceil(t / 5) * 5, tf)
    pyp = py_of(Fy, t_use)
    t = c * math.sqrt(3 * w / pyp)
    t_use = max(math.ceil(t / 5) * 5, math.ceil(tf / 5) * 5)
    r.add("Plate thickness", "tp = c·√(3w/pyp) ≥ T", f"pyp = {fmt(pyp)} MPa", f"tp,req = {fmt(t, 1)} mm → use {t_use} mm", "BS 5950 4.13.2.2")
    r.outputs = dict(N=Lp, B=Bp, t=t_use, d=d, bf=bf, m=c, n=c)
    return r

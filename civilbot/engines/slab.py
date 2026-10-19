"""RC slabs to BS 8110-1:1997: one-way (Table 3.12), two-way restrained panels (Table 3.14), punching shear (3.7.7).
The elastic plate solver (finite differences) is kept only to draw the moment contour map."""
from __future__ import annotations
import math
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from ..core import Result, InputError, fmt
from .rc_beam import vc_bs, as_min_ratio

BARS = [8, 10, 12, 16, 20]
AR = {d: math.pi * d * d / 4 for d in range(6, 41)}
GC = 24.0          # concrete unit weight kN/m³


def flexure_strip(M, h, d, fcu, fy, b=1000.0):
    """As per metre width (mm²/m) for M (kN·m/m) by BS 8110 3.4.4.4 — returns (As_req, As_min)."""
    K = abs(M) * 1e6 / (fcu * b * d * d)
    if K > 0.156:
        raise InputError("سماكة البلاطة غير كافية لهذا العزم (K > 0.156). زد h")
    z = min(d * (0.5 + math.sqrt(0.25 - K / 0.9)), 0.95 * d)
    return abs(M) * 1e6 / (0.95 * fy * z), as_min_ratio(fy) * b * h


def pick_spacing(As, h, prefer=None, d=None):
    smax = min(3 * (d or h - 25), 750, 300)     # BS 8110 3.12.11.2.7 (≤ 3d , 750) ; 300 practical cap
    for dd in ([prefer] if prefer else []) + BARS:
        s = 1000 * AR[dd] / As
        s = math.floor(min(s, smax) / 25) * 25
        if s >= 100:
            return dd, int(s), 1000 * AR[dd] / s
    dd = 20
    s = max(75, math.floor(1000 * AR[dd] / As / 25) * 25)
    return dd, int(s), 1000 * AR[dd] / s


def _n(gk, qk):
    return 1.4 * gk + 1.6 * qk


def _span_depth(r, L, d, basic, fy, As_req, As_prov, M):
    fs = 2 * fy * As_req / (3 * As_prov)
    mf = min(2.0, 0.55 + (477 - fs) / (120 * (0.9 + abs(M) * 1e6 / (1000 * d * d))))
    allow = basic * mf
    act = L * 1000 / d
    r.add("Span / effective depth", "L/d ≤ basic × MF ; MF = 0.55 + (477 − fs)/(120(0.9 + M/bd²)) ≤ 2",
          f"basic = {basic} , fs = {fmt(fs)} MPa , MF = {fmt(mf, 3)}", f"L/d = {fmt(act, 2)} ≤ {fmt(allow, 2)} {'✔' if act <= allow else '✘'}",
          "BS 8110 3.5.7 / Table 3.9–3.10")
    if act > allow:
        r.warnings.append("نسبة البحر/العمق أكبر من المسموح: زد السماكة")
    return act <= allow


def one_way(L, h, fcu, fy, gk, qk, cover=25.0, support="ss") -> Result:
    """L in m, loads in kN/m² (gk = superimposed dead, self weight added)."""
    coef = {"ss": (0.125, 0.0, 0.5, 20), "one": (0.086, -0.086, 0.6, 26), "both": (0.063, -0.063, 0.5, 26), "cant": (0.0, -0.5, 1.0, 7)}
    if support not in coef:
        raise InputError("support لازم يكون ss / one / both / cant")
    cp, cn, cv, basic = coef[support]
    r = Result("slab1", "One-way slab design (BS 8110-1:1997)",
               inputs=dict(L=f"{fmt(L)} m", support=support, fcu=f"{fmt(fcu)} MPa", fy=f"{fmt(fy)} MPa",
                           gk=f"{fmt(gk)} kN/m² (superimposed)", qk=f"{fmt(qk)} kN/m²"))
    if not h:
        h = max(125, math.ceil((L * 1000 / (basic * 1.2) + cover + 6) / 10) * 10)
        r.add("Trial thickness", f"d ≈ L/(basic × 1.2) , basic = {basic}", "", f"h = {fmt(h)} mm")
    sw = GC * h / 1000
    n = _n(gk + sw, qk)
    F = n * L
    r.add("Ultimate load", "n = 1.4gk + 1.6qk ; F = n·L", f"1.4×({fmt(gk)} + {fmt(sw)}) + 1.6×{fmt(qk)}",
          f"n = {fmt(n)} kN/m² , F = {fmt(F)} kN/m", "BS 8110 Table 2.1")
    Mpos, Mneg = cp * F * L, cn * F * L
    tab = {"ss": "simply supported: M = FL/8", "one": "end span: +0.086FL , first interior support −0.086FL",
           "both": "interior span: +0.063FL , interior support −0.063FL", "cant": "cantilever: M = −FL/2"}[support]
    r.add("Design moments per metre", "M = coefficient × F·L", tab, f"M+ = {fmt(Mpos)} , M− = {fmt(Mneg)} kN·m/m", "BS 8110 Table 3.12")
    if qk > 1.25 * (gk + sw) or qk > 5:
        r.warnings.append("شروط Table 3.12 غير محققة (qk ≤ 1.25gk و qk ≤ 5 kN/m²): يلزم تحليل مرن")
    d = h - cover - 6
    out = {}
    As_main, prov_main, Mmain = None, None, 0
    for name, M in (("bottom", Mpos), ("top", Mneg)):
        if abs(M) < 1e-9:
            continue
        As, Asmin = flexure_strip(M, h, d, fcu, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h, d=d)
        out[name] = (db, s)
        if abs(M) >= abs(Mmain):
            As_main, prov_main, Mmain = max(As, Asmin), prov, M
        r.add(f"{name.title()} main steel", "K = M/(fcu·b·d²) ; As = M/(0.95fy·z) ≥ As,min",
              f"d = {fmt(d)} mm , As = {fmt(As)} , As,min = {fmt(Asmin)} mm²/m",
              f"Ø{db} @ {s} mm ({fmt(1000*AR[db]/s, 0)} mm²/m)", "BS 8110 3.4.4.4 / Table 3.25")
    As_t = as_min_ratio(fy) * 1000 * h
    dbt, st, _ = pick_spacing(As_t, h, prefer=8 if h <= 150 else 10, d=d)
    r.add("Distribution steel", f"As = {as_min_ratio(fy)*100:g}%·b·h", f"{fmt(As_t)} mm²/m", f"Ø{dbt} @ {st} mm", "BS 8110 Table 3.25")
    V = cv * F
    v = V * 1e3 / (1000 * d)
    vc = vc_bs(prov_main or As_t, 1000, d, fcu, links=False)
    r.add("Shear", "v = V/(b·d) ≤ vc (no links in slabs)", f"V = {fmt(cv)}F = {fmt(V)} kN/m",
          f"v = {fmt(v, 3)} MPa ≤ vc = {fmt(vc, 3)} MPa {'✔' if v <= vc else '✘'}", "BS 8110 3.5.5 / Table 3.8")
    if v > vc:
        r.warnings.append("القص أكبر من مقاومة الخرسانة: زد السماكة")
    _span_depth(r, L, d, basic, fy, As_main, prov_main, Mmain)
    r.outputs = dict(h=h, d=d, wu=n, Mpos=Mpos, Mneg=Mneg, bars=out, temp=(dbt, st), L=L, kind="one")
    return r


def plate_fd(Lx, Ly, edges="SSSS", nu=0.2, n=24):
    """Kirchhoff plate under unit uniform load, D = 1. edges: left,right,bottom,top each S/F/E(free not supported).
    Returns coefficient grids: w, Mx, My (multiply by q·Lx² for moments)."""
    nx, ny = n, max(6, int(round(n * Ly / Lx)))
    hx, hy = Lx / nx, Ly / ny
    # interior unknowns i=1..nx-1, j=1..ny-1 ; boundary w = 0 ; ghost via edge condition
    N = (nx - 1) * (ny - 1)
    idx = lambda i, j: (i - 1) * (ny - 1) + (j - 1)
    A = lil_matrix((N, N))
    b = np.full(N, 1.0)
    el, er, eb, et = [edges[k].upper() for k in range(4)]

    def val(i, j):
        """return list of (index, coef) representing w(i,j) incl. boundary/ghost."""
        if 1 <= i <= nx - 1 and 1 <= j <= ny - 1:
            return [(idx(i, j), 1.0)]
        if i in (0, nx) or j in (0, ny):
            return []
        # ghost nodes
        if i == -1:
            return [(k, (1.0 if el == "F" else -1.0) * c) for k, c in val(1, j)]
        if i == nx + 1:
            return [(k, (1.0 if er == "F" else -1.0) * c) for k, c in val(nx - 1, j)]
        if j == -1:
            return [(k, (1.0 if eb == "F" else -1.0) * c) for k, c in val(i, 1)]
        if j == ny + 1:
            return [(k, (1.0 if et == "F" else -1.0) * c) for k, c in val(i, ny - 1)]
        return []
    ax, ay = 1 / hx**4, 1 / hy**4
    axy = 1 / (hx**2 * hy**2)
    stencil = [((0, 0), 6 * ax + 6 * ay + 8 * axy), ((1, 0), -4 * ax - 4 * axy), ((-1, 0), -4 * ax - 4 * axy),
               ((0, 1), -4 * ay - 4 * axy), ((0, -1), -4 * ay - 4 * axy), ((2, 0), ax), ((-2, 0), ax),
               ((0, 2), ay), ((0, -2), ay), ((1, 1), 2 * axy), ((1, -1), 2 * axy), ((-1, 1), 2 * axy), ((-1, -1), 2 * axy)]
    for i in range(1, nx):
        for j in range(1, ny):
            row = idx(i, j)
            for (di, dj), c in stencil:
                for k, cc in val(i + di, j + dj):
                    A[row, k] += c * cc
    w_in = spsolve(A.tocsr(), b)
    W = np.zeros((nx + 3, ny + 3))  # offset by 1 for ghosts
    def getw(i, j):
        return sum(w_in[k] * c for k, c in val(i, j))
    for i in range(-1, nx + 2):
        for j in range(-1, ny + 2):
            W[i + 1, j + 1] = getw(i, j)
    wxx = (W[2:, 1:-1] - 2 * W[1:-1, 1:-1] + W[:-2, 1:-1]) / hx**2
    wyy = (W[1:-1, 2:] - 2 * W[1:-1, 1:-1] + W[1:-1, :-2]) / hy**2
    Mx = -(wxx + nu * wyy)
    My = -(wyy + nu * wxx)
    return W[1:-1, 1:-1], Mx, My, nx, ny


# BS 8110 Table 3.14 — bending moment coefficients for rectangular panels supported on four sides
# with provision for torsion at corners. ly/lx = 1.0 1.1 1.2 1.3 1.4 1.5 1.75 2.0 ; long span (independent of ratio)
RATIOS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]
T314 = {
    1: ("Interior panel", [0.031, 0.037, 0.042, 0.046, 0.050, 0.053, 0.059, 0.063], [0.024, 0.028, 0.032, 0.035, 0.037, 0.040, 0.044, 0.048], 0.032, 0.024),
    2: ("One short edge discontinuous", [0.039, 0.044, 0.048, 0.052, 0.055, 0.058, 0.063, 0.067], [0.029, 0.033, 0.036, 0.039, 0.041, 0.043, 0.047, 0.050], 0.037, 0.028),
    3: ("One long edge discontinuous", [0.039, 0.049, 0.056, 0.062, 0.068, 0.073, 0.082, 0.089], [0.030, 0.036, 0.042, 0.047, 0.051, 0.055, 0.062, 0.067], 0.037, 0.028),
    4: ("Two adjacent edges discontinuous", [0.047, 0.056, 0.063, 0.069, 0.074, 0.078, 0.087, 0.093], [0.036, 0.042, 0.047, 0.051, 0.055, 0.059, 0.065, 0.070], 0.045, 0.034),
    5: ("Two short edges discontinuous", [0.046, 0.050, 0.054, 0.057, 0.060, 0.062, 0.067, 0.070], [0.034, 0.038, 0.040, 0.043, 0.045, 0.047, 0.050, 0.053], None, 0.034),
    6: ("Two long edges discontinuous", None, [0.034, 0.046, 0.056, 0.065, 0.072, 0.078, 0.091, 0.100], 0.045, 0.034),
    7: ("Three edges discontinuous (one long edge continuous)", [0.057, 0.065, 0.071, 0.076, 0.081, 0.084, 0.092, 0.098], [0.043, 0.048, 0.053, 0.057, 0.060, 0.063, 0.069, 0.074], None, 0.044),
    8: ("Three edges discontinuous (one short edge continuous)", None, [0.042, 0.054, 0.063, 0.071, 0.078, 0.084, 0.096, 0.105], 0.058, 0.044),
    9: ("Four edges discontinuous", None, [0.055, 0.065, 0.074, 0.081, 0.087, 0.092, 0.103, 0.111], None, 0.056),
}
CASE = {(0, 0): 1, (0, 1): 2, (1, 0): 3, (1, 1): 4, (0, 2): 5, (2, 0): 6, (1, 2): 7, (2, 1): 8, (2, 2): 9}


def two_way(Lx, Ly, h, fcu, fy, gk, qk, edges="SSSS", cover=25.0) -> Result:
    """edges = left,right,bottom,top (F = continuous, S = discontinuous). Lx short span along x."""
    if Lx > Ly:
        raise InputError("خلي Lx الاتجاه القصير (Lx ≤ Ly)")
    E = edges.upper()
    if len(E) != 4 or set(E) - {"F", "S"}:
        raise InputError("edges = 4 حروف من F/S (يسار،يمين،أسفل،أعلى)")
    if Ly / Lx > 2:
        r = one_way(Lx, h, fcu, fy, gk, qk, cover, "ss")
        r.warnings.insert(0, "Ly/Lx > 2: البلاطة تعمل في اتجاه واحد، تم التصميم كبلاطة اتجاه واحد")
        return r
    r = Result("slab2", "Two-way restrained slab design (BS 8110-1:1997 Table 3.14)",
               inputs=dict(Lx=f"{fmt(Lx)} m", Ly=f"{fmt(Ly)} m", edges=f"{E} (left,right,bottom,top: S=discontinuous, F=continuous)",
                           fcu=f"{fmt(fcu)} MPa", fy=f"{fmt(fy)} MPa", gk=f"{fmt(gk)} kN/m²", qk=f"{fmt(qk)} kN/m²"))
    # left/right edges run along y (length Ly) → long edges ; bottom/top → short edges
    long_disc = E[0:2].count("S")
    short_disc = E[2:4].count("S")
    case = CASE[(long_disc, short_disc)]
    name, neg_x, pos_x, neg_y, pos_y = T314[case]
    ratio = Ly / Lx
    bsx_n = float(np.interp(ratio, RATIOS, neg_x)) if neg_x else None
    bsx_p = float(np.interp(ratio, RATIOS, pos_x))
    nF = E.count("F")
    basic = 26 if nF >= 2 else 20
    if not h:
        h = max(125, math.ceil((Lx * 1000 / (basic * 1.3) + cover + 6) / 10) * 10)
        r.add("Trial thickness", f"d ≈ Lx/(basic × 1.3)", "", f"h = {fmt(h)} mm")
    sw = GC * h / 1000
    n = _n(gk + sw, qk)
    r.add("Ultimate load", "n = 1.4gk + 1.6qk", f"1.4×({fmt(gk)} + {fmt(sw)}) + 1.6×{fmt(qk)}", f"n = {fmt(n)} kN/m²", "BS 8110 Table 2.1")
    r.add("Panel case & coefficients", "msx = βsx·n·lx² ; msy = βsy·n·lx²",
          f"case {case}: {name} , ly/lx = {fmt(ratio, 3)}",
          f"βsx+ = {fmt(bsx_p, 4)}" + (f" , βsx− = {fmt(bsx_n, 4)}" if bsx_n else "") + f" , βsy+ = {pos_y}" + (f" , βsy− = {neg_y}" if neg_y else ""),
          "BS 8110 Table 3.14")
    Mxp, Myp = bsx_p * n * Lx**2, pos_y * n * Lx**2
    d_x = h - cover - 6
    d_y = d_x - 12
    outs = {}
    r.add("Positive (mid-span) moments", "msx = βsx·n·lx² ; msy = βsy·n·lx²", "", f"msx = {fmt(Mxp)} , msy = {fmt(Myp)} kN·m/m")
    As_main = prov_main = None
    for nm, M, d in (("short (x) bottom", Mxp, d_x), ("long (y) bottom", Myp, d_y)):
        As, Asmin = flexure_strip(M, h, d, fcu, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h, d=d)
        outs[nm] = (db, s)
        if As_main is None:
            As_main, prov_main = max(As, Asmin), prov
        r.add(f"Steel {nm}", "As = M/(0.95fy·z) ≥ As,min ; s ≤ 3d", f"d = {fmt(d)} , As = {fmt(As)} , As,min = {fmt(Asmin)} mm²/m",
              f"Ø{db} @ {s} mm", "BS 8110 3.5.3.5 / 3.12.11.2.7")
    neg = {}
    sides = {"left": (E[0], bsx_n, d_x), "right": (E[1], bsx_n, d_x), "bottom": (E[2], neg_y, d_y), "top": (E[3], neg_y, d_y)}
    for side, (kind, beta, d) in sides.items():
        if kind != "F" or not beta:
            continue
        M = -beta * n * Lx**2
        As, Asmin = flexure_strip(M, h, d, fcu, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h, d=d)
        neg[side] = M
        outs[f"top at {side} edge"] = (db, s)
        r.add(f"Support moment at {side} edge", "ms− = β−·n·lx²", f"β− = {fmt(beta, 4)}", f"M− = {fmt(M)} kN·m/m → Ø{db} @ {s} mm top")
    if case != 1:
        r.add("Torsion reinforcement at discontinuous corners", "0.75 × steel for max mid-span moment, in 4 layers over lx/5", "",
              "provide U-bars/mesh top & bottom at corners", "BS 8110 3.5.3.5")
    # shear (Table 3.15 conservative: 0.5·n·lx at continuous edge)
    V = 0.5 * n * Lx
    v = V * 1e3 / (1000 * d_x)
    vc = vc_bs(prov_main, 1000, d_x, fcu, links=False)
    r.add("Shear at support", "vsx ≈ 0.5·n·lx (upper bound of Table 3.15) ; v = V/bd ≤ vc", f"V = {fmt(V)} kN/m",
          f"v = {fmt(v, 3)} ≤ vc = {fmt(vc, 3)} MPa {'✔' if v <= vc else '✘'}", "BS 8110 3.5.3.7 / Table 3.15")
    if v > vc:
        r.warnings.append("القص أكبر من مقاومة الخرسانة: زد السماكة")
    _span_depth(r, Lx, d_x, basic, fy, As_main, prov_main, Mxp)
    # elastic plate field only for the contour picture, scaled to the Table 3.14 positive moment
    W, Mx, My, nx, ny = plate_fd(Lx, Ly, E)
    sc_x = Mxp / max(Mx.max(), 1e-9)
    sc_y = Myp / max(My.max(), 1e-9)
    r.outputs = dict(h=h, wu=n, Mx=Mxp, My=Myp, neg=neg, bars=outs, Lx=Lx, Ly=Ly, case=case,
                     edges=E, kind="two", Mgrid=(Mx * sc_x, My * sc_y))
    return r


def punching(c1, c2, h, d, fcu, V, position="interior", Mu=0.0, pct=None) -> Result:
    """BS 8110 3.7.7: face check + first critical perimeter at 1.5d. pct = 100As/bd of slab tension steel."""
    feff = {"interior": 1.15, "edge": 1.4, "corner": 1.25}
    if position not in feff:
        raise InputError("position = interior / edge / corner")
    pct = pct or 0.5
    r = Result("punch", "Punching shear check (BS 8110-1:1997 3.7.7)",
               inputs=dict(c1=f"{fmt(c1)} mm", c2=f"{fmt(c2)} mm", h=f"{fmt(h)} mm", d=f"{fmt(d)} mm", fcu=f"{fmt(fcu)} MPa",
                           V=f"{fmt(V)} kN", position=position, steel=f"100As/bd = {fmt(pct)} %"))
    Veff = feff[position] * V
    r.add("Effective shear (moment transfer)", "Veff = k·V (interior 1.15 , corner 1.25 , edge 1.4)", "",
          f"Veff = {fmt(Veff)} kN", "BS 8110 3.7.6.2–3.7.6.3")
    u0 = {"interior": 2 * (c1 + c2), "edge": 2 * c1 + c2, "corner": c1 + c2}[position]
    vmax = min(0.8 * math.sqrt(fcu), 5.0)
    v0 = Veff * 1e3 / (u0 * d)
    r.add("Maximum shear at column face", "v0 = Veff/(u0·d) ≤ min(0.8√fcu , 5)", f"u0 = {fmt(u0)} mm",
          f"v0 = {fmt(v0, 3)} ≤ {fmt(vmax, 3)} MPa {'✔' if v0 <= vmax else '✘'}", "BS 8110 3.7.7.2")

    def perim(dd):
        return {"interior": 2 * (c1 + c2) + 12 * dd, "edge": 2 * c1 + c2 + 9 * dd, "corner": c1 + c2 + 6 * dd}[position]
    u = perim(d)
    vc = vc_bs(pct * 1000 * d / 100, 1000, d, fcu, links=False)
    v = Veff * 1e3 / (u * d)
    ok = v <= vc and v0 <= vmax
    r.add("First critical perimeter at 1.5d", "u = column perimeter + 12d (interior)", f"d = {fmt(d)} mm", f"u = {fmt(u)} mm", "BS 8110 3.7.7.6")
    r.add("Concrete shear stress", "vc = 0.79(100As/bd)^⅓(400/d)^¼/1.25 × (fcu/25)^⅓", f"100As/bd = {fmt(pct)} %", f"vc = {fmt(vc, 3)} MPa", "BS 8110 Table 3.8")
    r.add("Check", "v = Veff/(u·d) ≤ vc", f"v = {fmt(Veff)}×1000/({fmt(u)}×{fmt(d)})",
          f"v = {fmt(v, 3)} MPa {'≤' if v <= vc else '>'} vc = {fmt(vc, 3)} MPa {'✔' if v <= vc else '✘'}")
    if not ok:
        dreq = d
        while dreq < 3 * d:
            dreq += 5
            vc2 = vc_bs(pct * 1000 * dreq / 100, 1000, dreq, fcu, links=False)
            if Veff * 1e3 / (perim(dreq) * dreq) <= vc2 and Veff * 1e3 / (u0 * dreq) <= vmax:
                break
        if v <= 2 * vc:
            r.warnings.append(f"القص الثاقب غير محقق. d المطلوب ≈ {fmt(dreq)} mm، أو حديد قص (v ≤ 2vc مسموح بحديد قص، BS 8110 3.7.7.5)")
        else:
            r.warnings.append(f"القص الثاقب غير محقق و v > 2vc: لازم زيادة السماكة (d ≈ {fmt(dreq)} mm) أو drop panel")
    r.outputs = dict(bo=u, vc=vc, vu=v, ok=ok, u0=u0, Veff=Veff)
    return r

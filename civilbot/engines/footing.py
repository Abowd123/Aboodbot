"""Isolated pad footing design to BS 8110-1:1997 (3.11) with optional uniaxial moment."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt
from .slab import flexure_strip
from .rc_beam import AREA, vc_bs


def anchorage(fy, fcu, db, beta=0.5):
    """Tension anchorage length (BS 8110 3.12.8.4): l = 0.87fy·Ø/(4·β√fcu), deformed type 2 bars."""
    return 0.87 * fy * db / (4 * beta * math.sqrt(fcu))


def design(Gk, Qk, qa, c1, c2, fcu, fy, M=0.0, Df=1.5, gamma_s=18.0, ratio=1.0, cover=50.0, db=None) -> Result:
    """Gk, Qk service kN; qa allowable gross kPa; c1 (along L, moment direction), c2 mm; Df m."""
    if qa <= 0 or Gk <= 0:
        raise InputError("qa و Gk لازم يكونوا موجبين")
    r = Result("footing", "Pad footing design (BS 8110-1:1997)",
               inputs=dict(Gk=f"{fmt(Gk)} kN", Qk=f"{fmt(Qk)} kN", M=f"{fmt(M)} kN·m (service)", qa=f"{fmt(qa)} kPa (gross allowable)",
                           column=f"{fmt(c1)}×{fmt(c2)} mm", Df=f"{fmt(Df)} m", fcu=f"{fmt(fcu)} MPa", fy=f"{fmt(fy)} MPa"))
    P = Gk + Qk
    h = 400.0
    for _ in range(40):
        qnet = qa - (24 * h / 1000 + gamma_s * (Df - h / 1000))
        if qnet <= 0:
            raise InputError("qa صغير جداً مقارنة بوزن التربة فوق القاعدة")
        e = abs(M) / P
        L = math.sqrt(P / qnet * ratio)
        for _ in range(200):
            B = L / ratio
            qmax = P / (B * L) * (1 + 6 * e / L) if e <= L / 6 else 2 * P / (3 * B * (L / 2 - e))
            if qmax <= qnet * 1.0001:
                break
            L += 0.05
        L = math.ceil(L * 20) / 20
        B = math.ceil(L / ratio * 20) / 20
        N = 1.4 * Gk + 1.6 * Qk
        Mu = abs(M) * N / P
        pu = N / (B * L)
        pu_max = pu * (1 + 6 * (Mu / N) / L)
        dbb = db or 16
        d = h - cover - dbb
        # punching at 1.5d (perimeter 2(c1+c2) + 12d) and face check
        u = 2 * (c1 + c2) + 12 * d
        side1, side2 = c1 + 3 * d, c2 + 3 * d
        Vp = N - pu * side1 * side2 / 1e6
        vc = vc_bs(0.0015 * 1000 * d, 1000, d, fcu, links=False)      # assume ≥ 0.15 % steel
        vp = max(Vp, 0) * 1e3 / (u * d)
        v0 = N * 1e3 / (2 * (c1 + c2) * d)
        ok_p = vp <= vc and v0 <= min(0.8 * math.sqrt(fcu), 5)
        # vertical line shear at d from the column face (3.11.3.4), long direction, pu_max
        x = (L * 1000 - c1) / 2 - d
        V1 = pu_max * B * max(x, 0) / 1000
        v1 = V1 * 1e3 / (B * 1000 * d)
        ok_1 = v1 <= vc
        if ok_p and ok_1:
            break
        h += 50
    r.add("Net allowable pressure", "qnet = qa − 24h − γs(Df − h)", f"{fmt(qa)} − 24×{fmt(h/1000)} − {fmt(gamma_s)}×{fmt(Df - h/1000)}", f"qnet = {fmt(qnet)} kPa")
    r.add("Plan size (service loads)", "qmax = P/A·(1 + 6e/L) ≤ qnet", f"P = Gk + Qk = {fmt(P)} kN , e = {fmt(e, 3)} m",
          f"L × B = {fmt(L)} × {fmt(B)} m , qmax = {fmt(P/(B*L)*(1+6*e/L) if e <= L/6 else 2*P/(3*B*(L/2-e)))} kPa")
    if e > L / 6:
        r.warnings.append("e > L/6: جزء من القاعدة لا يلامس التربة (توزيع مثلثي)")
    r.add("Ultimate loads", "N = 1.4Gk + 1.6Qk ; pu = N/A", f"N = {fmt(N)} kN", f"pu = {fmt(pu)} kPa , pu,max = {fmt(pu_max)} kPa", "BS 8110 Table 2.1")
    r.add("Punching at 1.5d", "u = 2(c1 + c2) + 12d ; V = N − pu(c1 + 3d)(c2 + 3d) ; v = V/(u·d) ≤ vc",
          f"h = {fmt(h)} mm , d = {fmt(d)} mm , u = {fmt(u)} mm", f"v = {fmt(vp, 3)} ≤ vc = {fmt(vc, 3)} MPa {'✔' if vp <= vc else '✘'}", "BS 8110 3.11.3.4 / 3.7.7")
    r.add("Face shear", "v0 = N/(u0·d) ≤ min(0.8√fcu , 5)", f"u0 = {fmt(2*(c1+c2))} mm", f"v0 = {fmt(v0, 3)} MPa ✔" if v0 <= min(0.8*math.sqrt(fcu), 5) else f"v0 = {fmt(v0, 3)} MPa ✘",
          "BS 8110 3.7.7.2")
    r.add("Vertical line shear at d from face", "V = pu,max·B·x ; v = V/(B·d) ≤ vc", f"x = {fmt(x)} mm",
          f"v = {fmt(v1, 3)} ≤ vc = {fmt(vc, 3)} MPa {'✔' if ok_1 else '✘'}", "BS 8110 3.11.3.4")
    bars = {}
    for name, span, width, cc in (("long (L)", L, B, c1), ("short (B)", B, L, c2)):
        arm = (span * 1000 - cc) / 2 / 1000
        q_use = pu_max if name.startswith("long") else pu
        Mface = q_use * width * arm**2 / 2
        dd = d if name.startswith("long") else d - dbb
        As, Asmin = flexure_strip(Mface / width, h, dd, fcu, fy)
        As_tot = max(As, Asmin) * width
        for dia in ([db] if db else [12, 16, 20, 25]):
            n = math.ceil(As_tot / AREA[dia])
            s = (width * 1000 - 2 * cover - dia) / (n - 1) if n > 1 else 0
            if 125 <= s <= min(3 * dd, 300):
                break
        n = max(n, math.ceil((width * 1000 - 2 * cover) / min(3 * dd, 300)) + 1)
        s = (width * 1000 - 2 * cover - dia) / (n - 1)
        bars[name] = (n, dia, s)
        r.add(f"Moment at column face, {name} direction", "M = pu·B·ℓ²/2 , ℓ = (L − c)/2 ; As = M/(0.95fy·z)", f"ℓ = {fmt(arm, 3)} m , d = {fmt(dd)} mm",
              f"M = {fmt(Mface)} kN·m → As = {fmt(As_tot)} mm² → {n}Ø{dia} @ {fmt(s, 0)} mm", "BS 8110 3.11.2.2 / 3.4.4.4")
    lc = max(L * 1000, B * 1000)
    if lc / 2 > 0.75 * c1 + 4.5 * d:
        r.add("Distribution of bars", "lc > (3c/4 + 9d/4)·2 → 2/3 of bars within 1.5d each side of column", "",
              "concentrate 2/3 of the steel in the central zone", "BS 8110 3.11.3.2")
    la = anchorage(fy, fcu, bars["long (L)"][1])
    avail = (min(L * 1000 - c1, B * 1000 - c2)) / 2 - cover
    r.add("Anchorage of bottom bars", "ℓ = 0.87fy·Ø/(4·0.5√fcu)", f"ℓ ≈ {fmt(la, 0)} mm",
          f"available = {fmt(avail, 0)} mm {'✔' if avail >= la else '✘ use bends / hooks'}", "BS 8110 3.12.8.4 / Table 3.27")
    r.outputs = dict(L=L, B=B, h=h, d=d, c1=c1, c2=c2, Df=Df, bars=bars, cover=cover, qu=pu, Pu=N)
    return r

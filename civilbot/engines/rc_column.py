"""Rectangular RC column design to BS 8110-1:1997 clause 3.8 (SI).

N–M interaction about the strong axis from strain compatibility (εcu = 0.0035, 0.45fcu over 0.9x, 0.95fy),
braced short/slender classification (3.8.1.3), additional moment for slender columns (3.8.3), nominal minimum
eccentricity (3.8.2.4) and automatic bar selection.
"""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt
from .rc_beam import AREA

ES, ECU = 200000.0, 0.0035


def layout(n, b, h, cover, dt, db):
    """Bar coordinates (y measured from top / compression face along h)."""
    if n < 4 or n % 2:
        raise InputError("عدد الأسياخ لازم يكون زوجي و ≥ 4")
    nt = max(2, round((n / 2) * b / (b + h)) + 1)
    nt = min(nt, n // 2)
    ns = (n - 2 * nt) // 2
    if 2 * nt + 2 * ns != n:
        nt += 1; ns = (n - 2 * nt) // 2
    e = cover + dt + db / 2
    xs_t = np.linspace(e, b - e, nt)
    ys = [e] * nt + [h - e] * nt
    xs = list(xs_t) * 2
    if ns > 0:
        yi = np.linspace(e, h - e, ns + 2)[1:-1]
        for y in yi:
            ys += [y, y]; xs += [e, b - e]
    clear_t = (xs_t[1] - xs_t[0] - db) if nt > 1 else 1e9
    clear_s = (h - 2 * e) / (ns + 1) - db
    return np.array(xs), np.array(ys), nt, ns, min(clear_t, clear_s)


def interaction(b, h, fcu, fy, ys, Ab, npts=120):
    """Arrays (N, M, 1.0, x, εs) in kN, kN·m from x large → small. Returns (arr, Nuz)."""
    Ac = b * h
    Asc = Ab * len(ys)
    Nuz = (0.45 * fcu * (Ac - Asc) + 0.95 * fy * Asc) / 1e3
    dt = ys.max()
    out = []
    xs_ = np.concatenate([np.geomspace(5 * h, h, 20), np.linspace(h, 0.02 * h, npts)])
    for x in xs_:
        a = min(0.9 * x, h)
        Cc = 0.45 * fcu * a * b
        N = Cc
        M = Cc * (h / 2 - a / 2)
        for y in ys:
            eps = ECU * (x - y) / x
            fs = max(-0.95 * fy, min(0.95 * fy, ES * eps))
            if y < a:
                fs -= 0.45 * fcu
            F = fs * Ab
            N += F
            M += F * (h / 2 - y)
        out.append((N / 1e3, M / 1e6, 1.0, x, ECU * (dt - x) / x))
    out.append((-0.95 * fy * Asc / 1e3, 0.0, 1.0, 0, 1))
    return np.array(out), Nuz


def Mu_at(arr, N):
    Ns, Ms = arr[:, 0], arr[:, 1]
    best = None
    for k in range(len(Ns) - 1):
        p1, p2 = Ns[k], Ns[k + 1]
        if (p1 - N) * (p2 - N) <= 0 and p1 != p2:
            t = (N - p1) / (p2 - p1)
            m = Ms[k] + t * (Ms[k + 1] - Ms[k])
            best = m if best is None else max(best, m)
    return best or 0.0


def design(b, h, fcu, fy, N, M, cover=40.0, dt=10.0, lu=None, k=1.0, M1M2=1.0, beta_dns=None,
           n=None, db=None, braced=True) -> Result:
    """N ultimate axial (kN), M = larger end moment M2 (kN·m), lu = clear height lo (m), k = β (Table 3.19)."""
    if min(b, h) < 200:
        raise InputError("أقل بعد للعمود 200 mm")
    if N < 0:
        raise InputError("N لازم يكون ضغط موجب")
    if not 25 <= fcu <= 60:
        raise InputError("مقاومة المكعب fcu خارج المدى (25–60 MPa) للأعمدة")
    r = Result("rc_column", "RC column design (BS 8110-1:1997)",
               inputs=dict(b=f"{fmt(b)} mm", h=f"{fmt(h)} mm (bending direction)", fcu=f"{fmt(fcu)} MPa", fy=f"{fmt(fy)} MPa",
                           N=f"{fmt(N)} kN", M=f"{fmt(M)} kN·m", cover=f"{fmt(cover)} mm",
                           lo=f"{fmt(lu)} m" if lu else "-", beta=fmt(k)))
    Ac = b * h
    M = abs(M)
    emin = min(0.05 * h, 20.0)
    Mmin = N * emin / 1e3
    r.add("Nominal minimum eccentricity", "emin = 0.05h ≤ 20 mm ; Mmin = N·emin", f"emin = {fmt(emin)} mm",
          f"Mmin = {fmt(Mmin)} kN·m", "BS 8110 3.8.2.4")
    Mt = max(M, Mmin)
    slender = False
    Madd_unit = 0.0
    if lu:
        le = k * lu
        lim = 15 if braced else 10
        ratio = le * 1000 / h
        ratio_b = le * 1000 / b
        sl = max(ratio, ratio_b)
        slender = sl > lim
        r.add("Slenderness (braced)" if braced else "Slenderness (unbraced)", f"le = β·lo ; le/h ≤ {lim} → short",
              f"le = {fmt(k)}×{fmt(lu)} = {fmt(le)} m , le/h = {fmt(ratio, 2)} , le/b = {fmt(ratio_b, 2)}",
              "Short column" if not slender else "Slender → additional moment", "BS 8110 3.8.1.3 / Table 3.19")
        if sl > 60 * min(b, h) / min(b, h) and sl > 60:
            raise InputError("le/b > 60: العمود نحيف جداً (BS 8110 3.8.1.7). كبّر المقطع")
        if slender:
            bprime = h if ratio >= ratio_b else b
            beta_a = (le * 1000 / bprime) ** 2 / 2000
            Madd_unit = N * beta_a * h / 1e3          # × K (applied after Nuz known)
            r.add("Additional moment (K = 1 first)", "βa = (le/b')²/2000 ; au = βa·K·h ; Madd = N·au",
                  f"βa = {fmt(beta_a, 4)}", f"Madd = {fmt(Madd_unit)}·K kN·m", "BS 8110 Eq. 34–35")
    cands = []
    sizes = [db] if db else [12, 16, 20, 25, 32, 40]
    counts = [n] if n else list(range(4, 41, 2))
    for d_ in sizes:
        for n_ in counts:
            Asc = n_ * AREA[d_]
            rho = Asc / Ac
            if rho < 0.004 - 1e-9 and not n:
                continue
            if rho > 0.06:
                break
            try:
                xs, ys, nt, ns, clear = layout(n_, b, h, cover, dt, d_)
            except InputError:
                continue
            if clear < max(25, d_):
                continue
            arr, Nuz = interaction(b, h, fcu, fy, ys, AREA[d_])
            Mdes = max(M, Mmin)
            Kf = 1.0
            if slender:
                Nbal = 0.25 * fcu * b * (h - cover - dt - d_ / 2) / 1e3
                Kf = min(1.0, max(0.0, (Nuz - N) / (Nuz - Nbal))) if Nuz > Nbal else 1.0
                Madd = Madd_unit * Kf
                M1 = M1M2 * M
                Mi = max(0.4 * M1 + 0.6 * M, 0.4 * M)
                Mdes = max(M, Mi + Madd, M1 + Madd / 2, Mmin)
            Nmax = (0.4 * fcu * (Ac - Asc) + 0.8 * fy * Asc) / 1e3      # BS 8110 Eq. 38
            mu = Mu_at(arr, N)
            if N <= Nmax and mu >= Mdes:
                cands.append((Asc, n_, d_, arr, Nuz, mu, Nmax, xs, ys, rho, nt, ns, Mdes, Kf))
                break
    if not cands:
        raise InputError("ما في تسليح يحقق المطلوب ضمن 6%. كبّر مقطع العمود أو fcu")
    cands.sort(key=lambda c: c[0] * (1 + 0.02 * (c[1] - 4)))      # least steel, with a penalty for many small bars (buildability)
    Asc, n_, d_, arr, Nuz, mu, Nmax, xs, ys, rho, nt, ns, Mt, Kf = cands[0]
    if slender:
        r.add("Design moment (braced slender)", "Mt = max(M2 , Mi + Madd , M1 + Madd/2 , N·emin) ; Mi = 0.4M1 + 0.6M2 ≥ 0.4M2",
              f"K = (Nuz − N)/(Nuz − Nbal) = {fmt(Kf, 3)}", f"Mt = {fmt(Mt)} kN·m", "BS 8110 3.8.3.2 / Eq. 36")
    else:
        r.add("Design moment", "Mt = max(M , N·emin)", "", f"Mt = {fmt(Mt)} kN·m")
    r.add("Axial capacity", "Nuz = 0.45fcu·Ac + 0.95fy·Asc ; N ≤ 0.4fcu·Ac + 0.8fy·Asc",
          f"Ac = {fmt(Ac)} mm² , Asc = {fmt(Asc)} mm²", f"Nuz = {fmt(Nuz)} kN , Nmax = {fmt(Nmax)} kN ≥ N = {fmt(N)} kN ✔",
          "BS 8110 Eq. 33 / 38")
    r.add("N–M interaction (εcu = 0.0035, 0.45fcu over 0.9x)", "N = 0.45fcu·0.9x·b + ΣAs·fs ; M = Σ forces × arm",
          f"{len(arr)} points", f"at N = {fmt(N)} kN: Mu = {fmt(mu)} kN·m ≥ Mt = {fmt(Mt)} kN·m ✔", "BS 8110 3.8.4 / Fig. 2.2")
    r.add("Selected longitudinal steel", "0.4% ≤ 100Asc/Ac ≤ 6%", f"ρ = {fmt(rho*100, 3)} %",
          f"{n_}Ø{d_} ({nt} bars per face × 2 + {ns} intermediate per side)", "BS 8110 3.12.5.2 / 3.12.6.2")
    tie = max(6, math.ceil(d_ / 4 / 2) * 2) if d_ > 24 else 8
    s_tie = math.floor(min(12 * d_, min(b, h)) / 25) * 25
    r.add("Links", "Ø ≥ max(6 , Ø_bar/4) ; s ≤ 12Ø_bar", f"min(12×{d_}, {fmt(min(b,h))})",
          f"Ø{tie} @ {s_tie} mm", "BS 8110 3.12.7.1")
    util = max(Mt / mu if mu else 9, N / Nmax)
    r.outputs = dict(n=n_, db=d_, Ast=Asc, rho=rho, xs=xs, ys=ys, b=b, h=h, cover=cover, tie=tie, s_tie=s_tie,
                     curve=arr, P0=Nuz, Pu=N, Mc=Mt, phiMn=mu, phiPmax=Nmax, util=util)
    return r

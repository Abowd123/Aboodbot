"""Random engineering problems (FE / PE style) with auto-grading and worked solutions from the engines."""
from __future__ import annotations
import math
import random
from ..core import fmt
from . import beam as bm, rc_beam, geotech, hydraulics, steel


def _r(a, b, step=1):
    return round(random.uniform(a, b) / step) * step


def q_ss_moment():
    L, w, P = _r(4, 10), _r(10, 40), _r(10, 80, 5)
    a = _r(1, L - 1, 0.5)
    res = bm.analyze(bm.Beam(L, [bm.Support("pin", 0), bm.Support("roller", L)], [bm.PointLoad(P, a)], [bm.DistLoad(w, w, 0, L)]))
    ans = res.Mmax_pos[0]
    return dict(topic="Structural analysis", q=f"كمرة بسيطة طولها {fmt(L)} m عليها حمل موزع {fmt(w)} kN/m وحمل مركز {fmt(P)} kN على بعد {fmt(a)} m من اليسار. احسب أقصى عزم موجب (kN·m).",
                ans=ans, unit="kN·m", sol=f"R_A = {fmt(res.reactions[0]['Ry'], 3)} kN ; V = 0 at x = {fmt(res.Mmax_pos[1], 3)} m → Mmax = {fmt(ans, 3)} kN·m")


def q_cant_defl():
    L, P = _r(1.5, 4, 0.5), _r(5, 40, 5)
    I = random.choice([2.0e-5, 4.0e-5, 8.36e-5, 1.2e-4])
    E = 200e6
    ans = P * L**3 / (3 * E * I) * 1000
    return dict(topic="Mechanics of materials", q=f"كابولي فولاذي طوله {fmt(L)} m، E = 200 GPa، I = {fmt(I*1e8, 0)} cm⁴، عليه حمل {fmt(P)} kN في الطرف الحر. احسب ترخيم الطرف (mm).",
                ans=ans, unit="mm", sol=f"δ = PL³/3EI = {fmt(P)}×{fmt(L)}³/(3×200e6×{I:g}) = {fmt(ans, 3)} mm")


def q_euler():
    L, K = _r(3, 8, 0.5), random.choice([0.5, 0.7, 1.0, 2.0])
    I = random.choice([8e-6, 1.6e-5, 2.5e-5, 5.0e-5])
    ans = math.pi**2 * 200e6 * I / (K * L) ** 2
    return dict(topic="Columns", q=f"عمود فولاذي طوله {fmt(L)} m، K = {K}، I = {fmt(I*1e8, 0)} cm⁴، E = 200 GPa. احسب حمل أويلر الحرج Pcr (kN).",
                ans=ans, unit="kN", sol=f"Pcr = π²EI/(KL)² = π²×200e6×{I:g}/({K}×{fmt(L)})² = {fmt(ans, 2)} kN")


def q_rc_as():
    b, h = random.choice([250, 300, 350]), random.choice([450, 500, 600, 700])
    fcu, fy = random.choice([30, 35, 40]), 460
    d = h - 50
    M = _r(60, 0.156 * fcu * b * d * d * 0.8 / 1e6, 5)
    K = M * 1e6 / (fcu * b * d * d)
    z = min(d * (0.5 + math.sqrt(0.25 - K / 0.9)), 0.95 * d)
    ans = max(M * 1e6 / (0.95 * fy * z), 0.0013 * b * h)
    return dict(topic="Reinforced concrete", q=f"كمرة {b}×{h} mm، d = {d} mm، fcu = {fcu} MPa، fy = 460 MPa، M = {fmt(M)} kN·m. احسب مساحة حديد الشد As (mm²) حسب BS 8110.",
                ans=ans, unit="mm²", sol=f"K = M/(fcu·b·d²) = {fmt(K, 4)} ≤ 0.156 ; z = d[0.5 + √(0.25 − K/0.9)] = {fmt(z, 1)} mm ≤ 0.95d ; As = M/(0.95fy·z) = {fmt(ans, 1)} mm²")


def q_bearing():
    B, Df, phi, g = _r(1.5, 3, 0.5), _r(1, 2, 0.5), random.choice([25, 30, 35]), 18
    r = geotech.bearing(B, B, Df, 0, phi, g, "terzaghi")
    ans = r.outputs["qu"]
    return dict(topic="Geotechnical", q=f"قاعدة مربعة عرضها {fmt(B)} m على عمق {fmt(Df)} m في رمل c = 0، φ = {phi}°، γ = 18 kN/m³. احسب قدرة التحمل القصوى qu (kPa) بطريقة Terzaghi.",
                ans=ans, unit="kPa", sol=f"Nq = {fmt(r.outputs['Nq'], 2)} , Nγ = {fmt(r.outputs['Ng'], 2)} ; qu = q·Nq + 0.4γBNγ = {fmt(ans, 1)} kPa")


def q_manning():
    b, y, n, S = _r(1, 4, 0.5), _r(0.5, 2, 0.1), random.choice([0.013, 0.015, 0.02, 0.025]), random.choice([0.0005, 0.001, 0.002])
    ans = hydraulics.manning_Q("rect", y, n, S, b=b)
    return dict(topic="Hydraulics", q=f"قناة مستطيلة عرضها {fmt(b)} m وعمق الماء {fmt(y)} m، n = {n}، S = {S}. احسب التصريف Q (m³/s).",
                ans=ans, unit="m³/s", sol=f"A = {fmt(b*y, 3)} , P = {fmt(b+2*y, 3)} , R = {fmt(b*y/(b+2*y), 4)} ; Q = (1/n)AR^(2/3)S^(1/2) = {fmt(ans, 4)} m³/s")


def q_mohr():
    sx, sy, t = _r(-60, 120, 5), _r(-60, 80, 5), _r(-50, 50, 5)
    ans = (sx + sy) / 2 + math.hypot((sx - sy) / 2, t)
    return dict(topic="Mechanics of materials", q=f"عنصر عليه σx = {fmt(sx)} MPa، σy = {fmt(sy)} MPa، τxy = {fmt(t)} MPa. احسب الإجهاد الرئيسي الأكبر σ1 (MPa).",
                ans=ans, unit="MPa", sol=f"C = {fmt((sx+sy)/2, 2)} , R = {fmt(math.hypot((sx-sy)/2, t), 3)} → σ1 = C + R = {fmt(ans, 3)} MPa")


def q_steel_col():
    name = random.choice(["HEB160", "HEB200", "HEA200", "HEB240", "HEA260"])
    LE = _r(2.5, 6, 0.5)
    key, p = steel.section(name)
    py = steel.py_of(355, p["tf"])
    lam = LE * 1000 / p["ry"]
    lam0 = 0.2 * math.sqrt(math.pi**2 * steel.E / py)
    pc = steel.perry(py, lam, lam0, steel.ROBERTSON["c"])
    ans = pc * p["A"] / 1e3
    return dict(topic="Steel design", q=f"عمود {name} (A = {fmt(p['A'], 0)} mm²، ry = {fmt(p['ry'], 1)} mm) طول فعال LE = {fmt(LE)} m حول المحور الضعيف، S355 (py = {fmt(py)} MPa). احسب مقاومة الضغط Pc (kN) حسب BS 5950 (منحنى c).",
                ans=ans, unit="kN", sol=f"λ = LE/ry = {fmt(lam, 2)} ; λ0 = {fmt(lam0, 2)} ; η = 5.5(λ − λ0)/1000 ; pc = {fmt(pc, 1)} MPa ; Pc = A·pc = {fmt(ans, 1)} kN")


TOPICS = {"analysis": [q_ss_moment], "mechanics": [q_cant_defl, q_mohr], "columns": [q_euler, q_steel_col],
          "concrete": [q_rc_as], "geotech": [q_bearing], "hydraulics": [q_manning], "steel": [q_steel_col]}
TOPIC_AR = {"analysis": "التحليل الإنشائي", "mechanics": "مقاومة المواد", "columns": "الأعمدة", "concrete": "الخرسانة",
            "geotech": "ميكانيكا التربة", "hydraulics": "الهيدروليكا", "steel": "المنشآت المعدنية", "mixed": "مختلط"}


def new_question(topic="mixed"):
    pool = [g for gs in TOPICS.values() for g in gs] if topic == "mixed" else TOPICS.get(topic)
    if not pool:
        pool = [g for gs in TOPICS.values() for g in gs]
    return random.choice(pool)()


def grade(q, value, tol=0.02):
    ok = abs(value - q["ans"]) <= tol * max(abs(q["ans"]), 1e-9)
    return ok

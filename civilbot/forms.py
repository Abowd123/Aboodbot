"""Structured input forms for every tool (Telegram-free).

One schema drives three things:
  1. the tool card in the bot (clear list of inputs with units, defaults and an example line),
  2. the step-by-step input wizard in the bot (one question per field, buttons for choices/defaults),
  3. the labelled input form in the web/APK app (served through /api/tools).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict


@dataclass
class F:
    key: str                     # parameter name exactly as typed (b, Mu, fc …)
    label: str                   # Arabic label
    unit: str = ""
    req: bool = False            # required
    default: str | None = None   # shown to the user; skipping = engine default
    ex: str = ""                 # typical value (quick-fill button + placeholder)
    kind: str = "num"            # num | text | choice
    options: list = field(default_factory=list)   # [(value, label)]; value "" = do not send the key
    ask: bool = True             # asked in the wizard (False = advanced, one-line only)
    when: tuple | None = None    # (other_key, (values…)) show only when that field has one of the values
    multi: bool = False          # text: several values separated by spaces -> repeated key (P=40@2 P=30@4)
    hint: str = ""               # short extra explanation
    pos: bool = False            # must be > 0

    def to_dict(self):
        d = asdict(self)
        d["options"] = [list(o) for o in self.options]
        d["when"] = list(self.when[:1]) + [list(self.when[1])] if self.when else None
        return d


@dataclass
class Form:
    desc: str
    fields: list
    example: str
    note: str = ""
    any_of: tuple = ()           # at least one of these keys must be given by the user


def _n(key, label, unit="", ex="", default=None, req=None, **k):
    return F(key, label, unit, req=(default is None) if req is None else req, default=default, ex=ex, **k)


def _c(key, label, options, default=None, **k):
    return F(key, label, "", req=False, default=default, kind="choice", options=options, ex="", **k)


def _t(key, label, unit="", ex="", default=None, req=None, **k):
    return F(key, label, unit, req=(default is None) if req is None else req, default=default, ex=ex, kind="text", **k)


FC = lambda d="35": _n("fcu", "مقاومة المكعب fcu", "MPa", d, d, hint="مكعب 150 mm (C35 = 35)")
FY = lambda d="460": _n("fy", "إجهاد خضوع الحديد fy", "MPa", d, d, hint="460 (T) أو 250 (R)")

FORMS: dict[str, Form] = {
    "beam": Form("رسم القص والعزم والترخيم لأي كمرة", [
        _n("L", "طول الكمرة", "m", "6", pos=True),
        _c("type", "نوع الركائز", [("ss", "بسيطة"), ("cant", "كابولي"), ("ff", "مثبتة الطرفين"), ("prop", "مثبتة + بسيطة")], "ss"),
        _n("w", "حمل موزع على كامل الطول", "kN/m", "20", "0", hint="لأسفل موجب"),
        _t("P", "أحمال مركزة (القيمة@المسافة)", "kN@m", "40@2", "بدون", multi=True, hint="أكثر من حمل: 40@2 30@4"),
        _n("EI", "الجساءة EI للترخيم", "kN·m²", "50000", "-", ask=False),
    ], "L=6 type=ss w=20 P=40@2", "ركائز مخصصة وأحمال جزئية من «الشرح الكامل»", any_of=("w", "P")),
    "rc": Form("تصميم كمرة خرسانية BS 8110 (مفرد/مزدوج + قص + بحر/عمق)", [
        _n("b", "عرض الكمرة", "mm", "300", pos=True), _n("h", "الارتفاع الكلي", "mm", "600", pos=True),
        FC(), FY(), _n("M", "العزم الأقصى (ultimate)", "kN·m", "250", pos=True),
        _n("V", "قوة القص (ultimate)", "kN", "180", "0"),
        _n("span", "البحر (فحص البحر/العمق والرسم)", "m", "6", "-"),
        _n("cover", "الغطاء الخرساني", "mm", "30", "30", ask=False), _n("link", "قطر الكانة", "mm", "10", "10", ask=False),
    ], "b=300 h=600 fcu=35 fy=460 M=250 V=180 span=6"),
    "truss": Form("تحليل جمالون جاهز (Pratt/Howe/Warren)", [
        _c("type", "نوع الجمالون", [("pratt", "Pratt"), ("howe", "Howe"), ("warren", "Warren")], "pratt"),
        _n("span", "البحر", "m", "12", pos=True), _n("h", "الارتفاع", "m", "3", pos=True),
        _n("n", "عدد الألواح", "", "6", "4"), _n("P", "حمل كل عقدة سفلية", "kN", "20", "10"),
    ], "type=pratt span=12 h=3 n=6 P=20", "جمالون مخصص بالعقد والأعضاء من «الشرح الكامل»"),
    "frame": Form("تحليل إطار 2D جاهز (Portal/Gable)", [
        _c("type", "نوع الإطار", [("portal", "Portal"), ("gable", "Gable جملوني")], "portal"),
        _n("L", "البحر", "m", "6", pos=True), _n("H", "ارتفاع العمود", "m", "4", pos=True),
        _n("w", "حمل موزع على الكمرة", "kN/m", "15", "0"), _n("P", "حمل أفقي أعلى العمود الأيسر", "kN", "20", "0"),
        _c("base", "نوع القاعدة", [("fixed", "مثبتة Fixed"), ("pin", "مفصلية Pin")], "fixed"),
        _n("rise", "ارتفاع الجملون", "m", "1.5", "1.5", when=("type", ("gable",))),
    ], "type=portal L=6 H=4 w=15 P=20 base=fixed", "إطار مخصص بالعقد والمفصلات من «الشرح الكامل»"),
    "column": Form("تصميم عمود خرساني BS 8110 + منحنى التفاعل N-M والنحافة", [
        _n("b", "عرض العمود", "mm", "400", pos=True), _n("h", "عمق العمود (اتجاه العزم)", "mm", "500", pos=True), FC(), FY(),
        _n("N", "الحمل المحوري (ultimate)", "kN", "1800", pos=True), _n("M", "العزم الأكبر M2", "kN·m", "220", "0"),
        _n("lo", "الارتفاع الحر بين الركائز", "m", "3.5", "-"),
        _n("beta", "معامل الطول الفعال β", "", "0.85", "1", ask=False, hint="Table 3.19"),
        _n("bars", "عدد الأسياخ (تثبيت)", "", "8", "تلقائي", ask=False),
        _n("db", "قطر السيخ (تثبيت)", "mm", "20", "تلقائي", ask=False), _n("cover", "الغطاء", "mm", "40", "40", ask=False),
    ], "b=400 h=500 fcu=35 fy=460 N=1800 M=220 lo=3.5"),
    "slab": Form("تصميم بلاطة باتجاه واحد أو اتجاهين", [
        _c("type", "نوع البلاطة", [("", "اتجاهين"), ("one", "اتجاه واحد")], "اتجاهين"),
        _n("Lx", "البحر القصير", "m", "4", when=("type", ("",)), req=True),
        _n("Ly", "البحر الطويل", "m", "5", when=("type", ("",)), req=True),
        _c("edges", "حالة الحواف (يسار،يمين،أسفل،أعلى)", [("SSSS", "كلها بسيطة SSSS"), ("FFFF", "كلها مستمرة FFFF"),
                                                         ("FSFS", "FSFS"), ("FFSS", "FFSS"), ("FFFS", "FFFS")], "SSSS",
           when=("type", ("",)), hint="F مستمر ، S غير مستمر (Table 3.14)"),
        _n("L", "البحر", "m", "4", when=("type", ("one",)), req=True),
        _c("support", "الاستمرارية", [("ss", "بسيطة"), ("one", "مستمرة من طرف"), ("both", "مستمرة من الطرفين"), ("cant", "كابولي")], "ss",
           when=("type", ("one",))),
        _n("gk", "الحمل الميت الإضافي gk", "kN/m²", "2", "1.5"), _n("qk", "الحمل الحي qk", "kN/m²", "3", "2"),
        FC(), FY(), _n("h", "السماكة", "mm", "150", "تلقائي", ask=False),
    ], "Lx=4 Ly=5 edges=FSFS gk=2 qk=3 fcu=35 fy=460"),
    "punch": Form("فحص القص الثاقب BS 8110 3.7.7", [
        _n("c1", "بعد العمود c1", "mm", "400", pos=True), _n("c2", "بعد العمود c2", "mm", "400", "= c1"),
        _n("d", "العمق الفعال للبلاطة", "mm", "250", pos=True), FC(), _n("V", "قوة القص (ultimate)", "kN", "550", pos=True),
        _c("pos", "موقع العمود", [("interior", "داخلي"), ("edge", "طرفي"), ("corner", "ركني")], "interior"),
        _n("pct", "نسبة حديد الشد 100As/bd", "%", "0.5", "0.5", ask=False),
    ], "c1=400 c2=400 d=250 fcu=35 V=550 pos=interior"),
    "footing": Form("تصميم قاعدة منفصلة BS 8110 (ثاقب + قص + حديد + DXF)", [
        _n("Gk", "الحمل الميت Gk", "kN", "800", pos=True), _n("Qk", "الحمل الحي Qk", "kN", "500", "0"),
        _n("qa", "قدرة تحمل التربة المسموحة", "kPa", "200", pos=True),
        _n("c1", "بعد العمود c1", "mm", "400", pos=True), _n("c2", "بعد العمود c2", "mm", "400", "= c1"),
        FC(), FY(), _n("M", "عزم تشغيلي", "kN·m", "60", "0"),
        _n("Df", "عمق التأسيس", "m", "1.5", "1.5", ask=False), _n("ratio", "نسبة L/B", "", "1.2", "1", ask=False),
    ], "Gk=800 Qk=500 qa=200 c1=400 c2=400 fcu=35 fy=460 M=60"),
    "wall": Form("تصميم جدار ساند كابولي BS 8110 (انقلاب، انزلاق، ضغط، حديد)", [
        _n("H", "ارتفاع الجدار", "m", "5", pos=True), _n("phi", "زاوية الاحتكاك φ", "°", "30", pos=True),
        _n("gamma", "وزن التربة النوعي", "kN/m³", "18", "18"), _n("q", "حمل إضافي سطحي", "kPa", "10", "0"),
        _n("qa", "قدرة التحمل المسموحة", "kPa", "200", "200"), FC(), FY(),
        _n("B", "عرض القاعدة", "m", "3.5", "تلقائي", ask=False), _n("mu", "معامل الاحتكاك", "", "0.5", "تلقائي", ask=False),
    ], "H=5 phi=30 gamma=18 q=10 qa=200"),
    "combo": Form("تراكيب الأحمال BS 8110 Table 2.1 والحالة الحاكمة", [
        _n("D", "الحمل الميت Gk", "kN", "120", "0"), _n("L", "الحمل الحي Qk", "kN", "80", "0"),
        _n("Lr", "حمل السطح الحي", "kN", "10", "0", ask=False), _n("S", "حمل الثلج", "kN", "0", "0", ask=False),
        _n("W", "حمل الرياح Wk", "kN", "40", "0"),
        _c("code", "الحالة", [("bs", "الحدية القصوى ULS"), ("sls", "التشغيل SLS")], "bs"),
    ], "D=120 L=80 W=40", any_of=("D", "L", "Lr", "S", "W")),
    "trib": Form("المساحات التخديمية وأحمال الكمرات والأعمدة", [
        _t("X", "بحور اتجاه x (مفصولة بفاصلة)", "m", "5,6"), _t("Y", "بحور اتجاه y", "m", "4,4.5"),
        _n("q", "حمل البلاطة", "kN/m²", "12", pos=True),
    ], "X=5,6 Y=4,4.5 q=12"),
    "bearing": Form("قدرة تحمل التربة للأساسات الضحلة", [
        _n("B", "عرض الأساس", "m", "2", pos=True), _n("L", "طول الأساس (0 = شريطي)", "m", "2", "0"),
        _n("Df", "عمق التأسيس", "m", "1.5"), _n("c", "التماسك c", "kPa", "0", "0"), _n("phi", "زاوية الاحتكاك φ", "°", "30"),
        _n("gamma", "وزن التربة", "kN/m³", "18", "18"),
        _c("method", "الطريقة", [("terzaghi", "Terzaghi"), ("meyerhof", "Meyerhof"), ("hansen", "Hansen"), ("vesic", "Vesic")], "meyerhof"),
        _n("FS", "معامل الأمان", "", "3", "3"), _n("gw", "عمق المياه الجوفية", "m", "2", "-", ask=False),
    ], "B=2 L=2 Df=1.5 c=0 phi=30 gamma=18 method=meyerhof FS=3"),
    "mohr": Form("دائرة مور والإجهادات الرئيسية", [
        _n("sx", "الإجهاد σx", "kPa", "80"), _n("sy", "الإجهاد σy", "kPa", "-40"), _n("txy", "إجهاد القص τxy", "kPa", "25", "0"),
        _n("theta", "زاوية مستوى مطلوب", "°", "30", "-"),
    ], "sx=80 sy=-40 txy=25 theta=30"),
    "lateral": Form("ضغط التربة الجانبي (Rankine/Coulomb)", [
        _n("H", "ارتفاع الجدار", "m", "6", pos=True), _n("phi", "زاوية الاحتكاك φ", "°", "30"),
        _n("gamma", "وزن التربة", "kN/m³", "18", "18"), _n("c", "التماسك", "kPa", "0", "0"), _n("q", "حمل سطحي", "kPa", "10", "0"),
        _c("method", "الطريقة", [("rankine", "Rankine"), ("coulomb", "Coulomb")], "rankine"),
        _n("delta", "احتكاك الجدار δ", "°", "20", "0", when=("method", ("coulomb",))),
        _n("beta", "ميل سطح الردم β", "°", "0", "0", when=("method", ("coulomb",))),
    ], "H=6 phi=30 gamma=18 c=0 q=10 method=rankine"),
    "consol": Form("هبوط التصلب الأولي ومنحنى الزمن", [
        _n("H", "سماكة طبقة الطين", "m", "4", pos=True), _n("e0", "نسبة الفراغات الابتدائية", "", "1.1", pos=True),
        _n("Cc", "معامل الانضغاط Cc", "", "0.36", pos=True), _n("s0", "الإجهاد الفعال الأولي", "kPa", "80", pos=True),
        _n("ds", "زيادة الإجهاد", "kPa", "60", pos=True), _n("cv", "معامل التصلب cv", "m²/yr", "1.5", "-"),
        _n("t", "الزمن", "yr", "1", "-"), _n("Cs", "معامل الانتفاخ Cs", "", "0.05", "-", ask=False),
        _n("sp", "إجهاد ما قبل التحميل", "kPa", "120", "-", ask=False),
    ], "H=4 e0=1.1 Cc=0.36 s0=80 ds=60 cv=1.5 t=1"),
    "bulb": Form("بصيلات الإجهاد تحت الأساس (Boussinesq)", [
        _n("q", "الضغط على الأساس", "kPa", "150", pos=True), _n("B", "عرض الأساس", "m", "2", pos=True),
        _n("L", "طول الأساس", "m", "3", "-"),
    ], "q=150 B=2 L=3"),
    "slope": Form("ثبات المنحدرات بطريقة Bishop", [
        _n("H", "ارتفاع المنحدر", "m", "10", pos=True), _n("beta", "زاوية الميل", "°", "30", pos=True),
        _n("c", "التماسك", "kPa", "10", "0"), _n("phi", "زاوية الاحتكاك φ", "°", "30"),
        _n("gamma", "وزن التربة", "kN/m³", "18", "18"), _n("ru", "نسبة ضغط المسام ru", "", "0", "0"),
    ], "H=10 beta=30 c=10 phi=30 gamma=18 ru=0"),
    "mix": Form("تصميم خلطة خرسانية بطريقة DoE (البريطانية)", [
        _n("fcu", "المقاومة المميزة للمكعب", "MPa", "30", pos=True), _n("slump", "الهبوط", "mm", "50", "50"),
        _c("nmsa", "أكبر مقاس للركام", [("10", "10 mm"), ("20", "20 mm"), ("40", "40 mm")], "20"),
        _c("agg", "نوع الركام", [("crushed", "مكسّر"), ("uncrushed", "طبيعي")], "crushed"),
        _n("p600", "نسبة الرمل المار من 600 µm", "%", "50", "50"),
        _n("rd", "الوزن النوعي للركام (SSD)", "", "2.65", "2.65", ask=False),
        _n("s", "الانحراف المعياري", "MPa", "6", "8", ask=False), _n("wcmax", "أقصى w/c للديمومة", "", "0.55", "-", ask=False),
        _n("fa", "نسبة الرمل من شكل 6", "%", "35", "تقديري", ask=False),
    ], "fcu=30 slump=50 nmsa=20 agg=crushed p600=50"),
    "sieve": Form("التحليل المنخلي، FM و Cu و Cc وحدود BS 882", [
        _t("sizes", "فتحات المناخل (مفصولة بفاصلة)", "mm", "5,2.36,1.18,0.6,0.3,0.15,0.075"),
        _t("mass", "الكتلة المحجوزة على كل منخل", "g", "20,80,120,150,90,30,10"),
        _c("spec", "المواصفة", [("fine", "رمل BS 882"), ("20", "ركام 20–5 mm"), ("10", "ركام 10–5 mm"), ("none", "بدون")], "fine"),
    ], "sizes=5,2.36,1.18,0.6,0.3,0.15,0.075 mass=20,80,120,150,90,30,10 spec=fine"),
    "channel": Form("قناة مفتوحة بمعادلة Manning", [
        _c("shape", "شكل القناة", [("rect", "مستطيل"), ("trap", "شبه منحرف"), ("tri", "مثلث"), ("circle", "دائري")], "rect"),
        _n("b", "عرض القاع", "m", "3", when=("shape", ("rect", "trap")), req=True),
        _n("z", "ميل الجوانب (أفقي:رأسي)", "", "2", when=("shape", ("trap", "tri")), req=True),
        _n("D", "القطر", "m", "1.2", when=("shape", ("circle",)), req=True),
        _n("n", "معامل Manning", "", "0.015", pos=True), _n("S", "ميل القاع", "m/m", "0.001", pos=True),
        _n("Q", "التصريف (لإيجاد العمق)", "m³/s", "10", "-", hint="أعط Q أو y"),
        _n("y", "العمق (لإيجاد التصريف)", "m", "1.5", "-"),
    ], "shape=trap b=3 z=2 n=0.015 S=0.001 Q=10", any_of=("Q", "y")),
    "pipe": Form("فواقد الأنابيب وقدرة المضخة", [
        _n("Q", "التصريف", "m³/s", "0.05", pos=True), _n("D", "قطر الأنبوب", "m", "0.2", pos=True),
        _n("L", "طول الأنبوب", "m", "500", pos=True),
        _c("method", "الطريقة", [("darcy", "Darcy-Colebrook"), ("hw", "Hazen-Williams")], "darcy"),
        _n("eps", "خشونة الجدار", "mm", "0.045", "0.045", when=("method", ("darcy",))),
        _n("C", "معامل Hazen-Williams", "", "130", "130", when=("method", ("hw",))),
        _n("K", "مجموع معاملات الفواقد الثانوية", "", "5", "0"), _n("dz", "فرق المنسوب", "m", "10", "0"),
    ], "Q=0.05 D=0.2 L=500 eps=0.045 K=5 dz=10"),
    "traverse": Form("ضبط مضلع مغلق بطريقة Bowditch", [
        _t("az", "الانحرافات (درجة-دقيقة-ثانية)", "", "45-30-00,135-12-00,225,315-06"),
        _t("d", "الأطوال", "m", "100,100,100.05,99.98"),
        _n("E0", "إحداثي الشرق للبداية", "m", "1000", "1000"), _n("N0", "إحداثي الشمال للبداية", "m", "1000", "1000"),
    ], "az=45-30-00,135-12-00,225,315-06 d=100,100,100.05,99.98 E0=1000 N0=1000"),
    "hcurve": Form("عناصر وتوقيع منحنى أفقي", [
        _n("R", "نصف القطر", "m", "300", pos=True), _t("delta", "زاوية الانحراف (درجة أو د-د-ث)", "°", "40"),
        _n("PI", "محطة نقطة التقاطع", "m", "1000"), _n("chord", "طول الوتر", "m", "20", "20"),
    ], "R=300 delta=40 PI=1000 chord=20"),
    "vcurve": Form("منحنى رأسي ومناسيبه", [
        _n("g1", "الميل الداخل", "%", "3"), _n("g2", "الميل الخارج", "%", "-2"), _n("L", "طول المنحنى", "m", "200", pos=True),
        _n("PVI", "محطة نقطة التقاطع", "m", "1500"), _n("el", "منسوب نقطة التقاطع", "m", "100"),
        _n("step", "مسافة الحساب", "m", "20", "20", ask=False),
    ], "g1=3 g2=-2 L=200 PVI=1500 el=100"),
    "earth": Form("كميات الحفر والردم ومنحنى ماس هول", [
        _t("st", "المحطات", "m", "0,20,40,60"), _t("A", "مساحات المقاطع (+حفر / -ردم)", "m²", "10,5,-4,-8"),
    ], "st=0,20,40,60 A=10,5,-4,-8"),
    "pavement": Form("تصميم رصف مرن AASHTO 93", [
        _n("W18", "عدد المحاور المكافئة ESAL", "", "5e6", pos=True), _n("R", "الاعتمادية", "%", "95", "95"),
        _n("S0", "الانحراف المعياري", "", "0.45", "0.45"), _n("MR", "معامل المرونة للتربة", "MPa", "50", pos=True),
    ], "W18=5e6 R=95 S0=0.45 MR=50"),
    "ssd": Form("مسافة الرؤية للتوقف", [
        _n("V", "السرعة التصميمية", "km/h", "100", pos=True), _n("t", "زمن رد الفعل", "s", "2.5", "2.5"),
        _n("G", "الميل الطولي", "%", "0", "0"),
    ], "V=100 t=2.5 G=0"),
    "sbeam": Form("اختيار وتصميم كمرة معدنية BS 5950-1:2000", [
        _n("M", "العزم الأقصى (ultimate)", "kN·m", "150", pos=True), _n("V", "القص الأقصى", "kN", "120", "0"),
        _n("LE", "الطول الفعال للانبعاج الجانبي", "m", "3"),
        _c("py", "رتبة الحديد", [("275", "S275"), ("355", "S355")], "355"),
        _c("family", "عائلة المقاطع", [("IPE", "IPE"), ("HEA", "HEA"), ("HEB", "HEB")], "IPE"),
        _n("mLT", "معامل العزم المكافئ mLT", "", "1", "1", ask=False),
        _n("L", "البحر (للترخيم)", "m", "6", "-", ask=False), _n("w", "الحمل الحي التشغيلي (للترخيم)", "kN/m", "15", "-", ask=False),
    ], "M=150 V=120 LE=3 py=355"),
    "scol": Form("تصميم عمود معدني BS 5950-1:2000", [
        _n("N", "الحمل المحوري (ultimate)", "kN", "1500", pos=True), _n("LE", "الطول الفعال (المحور الضعيف)", "m", "4", pos=True),
        _c("py", "رتبة الحديد", [("275", "S275"), ("355", "S355")], "355"), _n("Mx", "عزم مصاحب", "kN·m", "60", "0"),
        _c("family", "عائلة المقاطع", [("HEB", "HEB"), ("HEA", "HEA"), ("IPE", "IPE")], "HEB"),
        _n("LEx", "الطول الفعال (المحور القوي)", "m", "4", "= LE", ask=False),
    ], "N=1500 LE=4 py=355"),
    "stab": Form("وصلة قص Fin plate بمسامير BS 5950", [
        _n("V", "قوة القص", "kN", "250", pos=True), _n("d", "قطر المسمار", "mm", "20", "20"),
        _c("grade", "رتبة المسامير", [("8.8", "8.8"), ("10.9", "10.9"), ("4.6", "4.6")], "8.8"),
        _n("tp", "سماكة اللوح", "mm", "10", "10"), _n("tw", "سماكة جذع الكمرة", "mm", "7.1", "7.1"),
        _c("py", "رتبة اللوح", [("275", "S275"), ("355", "S355")], "275", ask=False),
    ], "V=250 d=20 grade=8.8 tp=10 tw=7.1"),
    "bplate": Form("تصميم لوح قاعدة عمود معدني BS 5950 4.13", [
        _n("N", "الحمل المحوري (ultimate)", "kN", "1500", pos=True), _n("D", "عمق مقطع العمود", "mm", "300", pos=True),
        _n("B", "عرض شفة العمود", "mm", "300", pos=True), _n("fcu", "مقاومة خرسانة القاعدة", "MPa", "30", "30"),
        _c("py", "رتبة اللوح", [("275", "S275"), ("355", "S355")], "275"),
    ], "N=1500 D=300 B=300 fcu=30 py=275"),
}

# one-line descriptions for tools without a form (shown in the category list and the tool card)
DESC = {
    "section": "خصائص أي مقطع: المساحة، المركز، العزوم، المحاور الرئيسية",
    "formula": "حل أي قانون هندسي خطوة بخطوة وإيجاد المجهول",
    "units": "تحويل فوري بين وحدات القوى والإجهادات والأحمال",
    "level": "حساب المناسيب من دفتر الميزانية مع التحقق",
    "il": "خطوط التأثير وأقصى تأثير لشاحنة أو حمل موزع",
    "anim": "رسوم متحركة GIF للانبعاج والترخيم والاهتزاز",
    "codes": "مقارنة بنود الأكواد بالذكاء الاصطناعي",
    "schedule": "جدول تصميم أعمدة كامل دفعة واحدة",
    "boq": "حصر كميات الخرسانة والحديد والطوب مع التكلفة",
    "crack": "تحليل صورة شرخ: النوع، السبب المحتمل، العرض",
    "equation": "قراءة معادلة من صورة وحسابها",
    "layout": "اقتراح توزيع أعمدة على اسكتش معماري",
}


def desc(tool: str) -> str:
    f = FORMS.get(tool)
    return f.desc if f else DESC.get(tool, "")


def visible(form: Form, values: dict) -> list:
    """Fields that apply given the values chosen so far (choice-dependent fields)."""
    out = []
    for f in form.fields:
        if f.when:
            k, allowed = f.when
            dep = next((x for x in form.fields if x.key == k), None)
            cur = values.get(k, _choice_default_value(dep) if dep else None)
            if cur not in allowed:
                continue
        out.append(f)
    return out


def _choice_default_value(f: F):
    if f.kind != "choice":
        return f.default
    for v, lbl in f.options:
        if f.default in (v, lbl):
            return v
    return f.options[0][0] if f.options else ""


def wizard_fields(form: Form, values: dict) -> list:
    return [f for f in visible(form, values) if f.ask or f.req]


_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$", re.I)


def clean(text: str) -> str:
    """Arabic/Persian digits -> ASCII, Arabic comma -> comma, trim."""
    return text.translate(_AR).replace("،", ",").replace("−", "-").strip()


def parse_value(f: F, text: str) -> tuple[str | None, str | None]:
    """Returns (value, error_message_ar)."""
    t = clean(text)
    if f.kind == "choice":
        for v, lbl in f.options:
            if t.lower() in (v.lower(), lbl.lower()) and t != "":
                return v, None
        return None, "اختر من الأزرار بالأسفل 👇"
    if not t:
        return None, "القيمة فاضية"
    if f.kind == "num":
        t = t.replace(",", ".") if t.count(",") == 1 and "." not in t else t.replace(",", "")
        t = re.sub(r"\s*[a-zA-Z/²³·°%]+.*$", "", t) if re.match(r"^[-+]?[\d.]", t) else t   # "300 mm" -> 300
        if not NUM_RE.match(t):
            return None, f"لازم رقم. مثال: {f.ex or '10'}"
        if f.pos and float(t) <= 0:
            return None, "لازم القيمة تكون أكبر من صفر"
        return t, None
    t = re.sub(r"\s+", " ", t)
    if " " in t and not f.multi:
        t = t.replace(" ", "")
    return t, None


def build_text(form: Form, values: dict) -> str:
    parts = []
    for f in visible(form, values):
        v = values.get(f.key)
        if v is None and f.kind == "choice":
            v = _choice_default_value(f)      # a choice always sends its value (e.g. frame needs type=portal)
        elif v is None and f.kind == "num" and f.ask and f.default and NUM_RE.match(f.default):
            v = f.default                     # numeric defaults are sent explicitly: the user sees exactly what was used
        if v in (None, ""):
            continue
        if f.multi:
            parts += [f"{f.key}={x}" for x in re.split(r"[\s,]+", v) if x]
        else:
            parts.append(f"{f.key}={v}")
    return " ".join(parts)


def parse_text(form: Form, text: str) -> dict:
    """One-line input -> wizard values (so «✏️ عدّل القيم» works after typed input too)."""
    keys = {f.key.lower(): f for f in form.fields}
    vals: dict = {}
    for k, v in re.findall(r"([A-Za-z][A-Za-z0-9]*)\s*=\s*([^\s]+)", clean(text)):
        f = keys.get(k.lower())
        if not f:
            continue
        vals[f.key] = (vals[f.key] + " " + v) if (f.multi and f.key in vals) else v
    return vals


def missing_any(form: Form, values: dict) -> list:
    """[] if the any_of rule is satisfied, else the keys the user must choose from."""
    if not form.any_of:
        return []
    return [] if any(values.get(k) not in (None, "", "0") for k in form.any_of) else list(form.any_of)


def schema(tool: str) -> dict | None:
    f = FORMS.get(tool)
    if not f:
        return None
    return {"desc": f.desc, "example": f.example, "note": f.note, "any_of": list(f.any_of), "fields": [x.to_dict() for x in f.fields]}

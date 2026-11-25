"""Bulanık mantık kapısı (Mamdani): CNN güveni, CNN-arşiv uyumu, klinik risk ve yaş -> konsey gerekliliği (0-100).

VE = min, VEYA = max, DEĞİL = 1 - µ; kural çıkışları min ile kırpılır, max ile birleştirilir,
ağırlık merkezi (centroid) ile durulaştırılır. Bütün işlemler numpy ile vektörel yapılır.
"""
import numpy as np

CIKIS_EVRENI = np.linspace(0, 100, 201)


def yamuk(x, a, b, c, d):
    """Yamuk üyelik fonksiyonu (a<=b<=c<=d). a==b sol omuz, c==d sağ omuz demektir."""
    x = np.asarray(x, dtype=float)
    y = np.where((x >= b) & (x <= c), 1.0, 0.0)
    if b > a:
        y = np.where((x > a) & (x < b), (x - a) / (b - a), y)
    if d > c:
        y = np.where((x > c) & (x < d), (d - x) / (d - c), y)
    return y


def uc_kume(q05, q50, q95, alt=0.0, ust=1.0):
    """Düşük / orta / yüksek kümeleri, girdinin doğrulama dağılımındaki %5, %50, %95 yüzdeliklerine göre.
    Tam üyelik yalnızca dağılımın uçlarında (en alt / en üst %5) olur; böylece puan kademeli değişir."""
    return {'dusuk': (alt, alt, q05, q50), 'orta': (q05, q50, q50, q95), 'yuksek': (q50, q95, ust, ust)}


YAS_KUMELERI = {'genc': (0, 0, 35, 50), 'ileri': (35, 50, 150, 150)}     # yaş bilinmiyorsa ikisi de 0,5
CIKIS_KUMELERI = {'dusuk': (0, 0, 0, 50), 'orta': (25, 50, 50, 75), 'yuksek': (50, 100, 100, 100)}


def ve(*a):
    return np.minimum.reduce(a)


def veya(*a):
    return np.maximum.reduce(a)


def degil(a):
    return 1.0 - a


# (ad, Türkçe kural, öncül fonksiyonu, çıkış kümesi)
KURALLAR = [
    ('K1', 'güven DÜŞÜK ise konsey YÜKSEK', lambda m: m['guven']['dusuk'], 'yuksek'),
    ('K2', 'uyum DÜŞÜK ise konsey YÜKSEK', lambda m: m['uyum']['dusuk'], 'yuksek'),
    ('K3', 'güven YÜKSEK ve uyum YÜKSEK ve risk DÜŞÜK ise konsey DÜŞÜK',
     lambda m: ve(m['guven']['yuksek'], m['uyum']['yuksek'], m['risk']['dusuk']), 'dusuk'),
    ('K4', 'güven YÜKSEK ve uyum YÜKSEK ve risk ORTA ise konsey DÜŞÜK',
     lambda m: ve(m['guven']['yuksek'], m['uyum']['yuksek'], m['risk']['orta']), 'dusuk'),
    ('K5', 'güven YÜKSEK ve uyum YÜKSEK ve risk YÜKSEK ise konsey ORTA',
     lambda m: ve(m['guven']['yuksek'], m['uyum']['yuksek'], m['risk']['yuksek']), 'orta'),
    ('K6', 'güven ORTA ve uyum YÜKSEK ve risk DÜŞÜK ise konsey DÜŞÜK',
     lambda m: ve(m['guven']['orta'], m['uyum']['yuksek'], m['risk']['dusuk']), 'dusuk'),
    ('K7', 'güven ORTA ve uyum YÜKSEK ve risk (ORTA veya YÜKSEK) ise konsey ORTA',
     lambda m: ve(m['guven']['orta'], m['uyum']['yuksek'], veya(m['risk']['orta'], m['risk']['yuksek'])), 'orta'),
    ('K8', 'güven YÜKSEK ve uyum ORTA ve risk DÜŞÜK ise konsey DÜŞÜK',
     lambda m: ve(m['guven']['yuksek'], m['uyum']['orta'], m['risk']['dusuk']), 'dusuk'),
    ('K9', 'güven YÜKSEK ve uyum ORTA ve risk (ORTA veya YÜKSEK) ise konsey ORTA',
     lambda m: ve(m['guven']['yuksek'], m['uyum']['orta'], veya(m['risk']['orta'], m['risk']['yuksek'])), 'orta'),
    ('K10', 'güven ORTA ve uyum ORTA ve risk DÜŞÜK ise konsey ORTA',
     lambda m: ve(m['guven']['orta'], m['uyum']['orta'], m['risk']['dusuk']), 'orta'),
    ('K11', 'güven ORTA ve uyum ORTA ve risk (ORTA veya YÜKSEK) ise konsey YÜKSEK',
     lambda m: ve(m['guven']['orta'], m['uyum']['orta'], veya(m['risk']['orta'], m['risk']['yuksek'])), 'yuksek'),
    ('K12', 'yaş İLERİ ve risk YÜKSEK ve DEĞİL(güven YÜKSEK ve uyum YÜKSEK) ise konsey YÜKSEK',
     lambda m: ve(m['yas']['ileri'], m['risk']['yuksek'], degil(ve(m['guven']['yuksek'], m['uyum']['yuksek']))), 'yuksek'),
]


class BulanikKapi:
    def __init__(self, yuzdelikler, kurallar=None):
        """yuzdelikler: {'guven': (q05, q50, q95), 'uyum': (...), 'risk': (...)}; kurallar: kullanılacak kural adları."""
        self.yuzdelikler = {k: tuple(float(v) for v in d) for k, d in yuzdelikler.items()}
        self.kumeler = {g: uc_kume(*q) for g, q in self.yuzdelikler.items()}
        self.kurallar = [k for k in KURALLAR if kurallar is None or k[0] in kurallar]

    def uyelikler(self, guven, uyum, risk, yas):
        girdi = {'guven': guven, 'uyum': uyum, 'risk': risk}
        m = {g: {k: yamuk(np.atleast_1d(girdi[g]), *p) for k, p in self.kumeler[g].items()} for g in girdi}
        yas = np.atleast_1d(np.asarray(yas, dtype=float))
        bilinmiyor = np.isnan(yas)
        m['yas'] = {k: np.where(bilinmiyor, 0.5, yamuk(np.nan_to_num(yas, nan=0.0), *p)) for k, p in YAS_KUMELERI.items()}
        return m

    def skor(self, guven, uyum, risk, yas, ayrinti=False):
        m = self.uyelikler(guven, uyum, risk, yas)
        guc = {ad: f(m) for ad, _, f, _ in self.kurallar}
        n = len(next(iter(guc.values())))
        cikis_gucu = {c: np.max([guc[ad] for ad, _, _, cc in self.kurallar if cc == c] or [np.zeros(n)], axis=0)
                      for c in CIKIS_KUMELERI}
        birlesik = np.max([np.minimum(cikis_gucu[c][:, None], yamuk(CIKIS_EVRENI, *p)[None, :])
                           for c, p in CIKIS_KUMELERI.items()], axis=0)
        pay = birlesik.sum(1)
        s = np.where(pay > 0, (birlesik * CIKIS_EVRENI).sum(1) / np.maximum(pay, 1e-12), 50.0)
        return (s, m, guc) if ayrinti else s

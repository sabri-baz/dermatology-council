"""Literatür ajanı (RAG): kanıt paketi oluşturma, sistem istemi ve kaynak doğrulaması.

Ajan görüntüyü görmez; yalnızca metin alır: CNN çıktısı, konsey kapısının gerekçesi, hasta bilgisi,
benzer arşiv vakaları (Adım 4) ve PubMed makaleleri (Adım 6).
"""
import re
import json
import numpy as np
import pandas as pd
import bulanik_kapi as bk
from llm_istemci import json_ayikla

SINIF_TR = {'akiec': 'Aktinik keratoz / Bowen', 'bcc': 'Bazal hücreli karsinom', 'bkl': 'Benign keratoz',
            'df': 'Dermatofibrom', 'mel': 'Melanom', 'nv': 'Melanositik nevüs', 'vasc': 'Vasküler lezyon'}
SINIF_EN = {'akiec': 'actinic keratosis or Bowen disease', 'bcc': 'basal cell carcinoma',
            'bkl': 'seborrheic keratosis or solar lentigo', 'df': 'dermatofibroma', 'mel': 'melanoma',
            'nv': 'melanocytic nevus', 'vasc': 'vascular lesions such as hemangioma or angiokeratoma'}
DOGRULAMA_TR = {'histo': 'patoloji', 'follow_up': 'takip', 'consensus': 'uzman uzlaşısı', 'confocal': 'konfokal mikroskopi'}
CINSIYET_TR = {'male': 'erkek', 'female': 'kadın'}
KOTU_HUYLU = ['mel', 'bcc', 'akiec']
KANIT_YONLERI = ('destekliyor', 'zayiflatiyor', 'belirsiz')

SISTEM_ISTEMI = """Sen bir dermatoloji konseyinde LİTERATÜR AJANISIN. Görevin, bir cilt lezyonu vakası için sana verilen KANIT PAKETİNİ okuyup kaynak gösteren, tarafsız bir kanıt özeti yazmak.

KURALLAR:
1. Yalnızca paketteki bilgileri kullan. Paket dışı bir makale, PMID ya da vaka uydurma; kendi genel bilgini kaynak gibi sunma.
2. Lezyonun görüntüsünü GÖRMÜYORSUN. "Bu lezyonda şu bulgu var/yok" deme. Makalelerdeki dermoskopik bulguları, uzmanın bakması gereken ölçütler olarak yaz.
3. Her iddianın sonuna kaynağını köşeli parantezle yaz: benzer vakalar [V1]...[V5], makaleler [M1]...[M6], CNN çıktısı [CNN], hasta bilgisi [HASTA], konsey kapısı [KAPI], arşiv oylaması [ARSIV]. Kaynaksız iddia yazma.
4. Tarafsız ol. CNN'in kararını savunmak ya da çürütmek senin görevin değil; kanıtın hangi yöne işaret ettiğini dürüstçe bildir. Kanıt zayıf ya da çelişkiliyse bunu açıkça söyle ve "belirsiz" de.
5. Benzer vakaların tanı doğrulama yöntemini dikkate al: patolojiyle doğrulanmış tanı, takip ya da uzman uzlaşısıyla konulan tanıdan daha güçlü kanıttır.
6. Cevabı yalnızca aşağıdaki JSON biçiminde ve Türkçe ver; JSON dışında hiçbir şey yazma:
{"ozet": "3-5 cümlelik kanıt özeti, her cümlede kaynak", "aday_tanilar": [{"sinif": "<kod>", "lehte": "... [Vx][Mx]", "aleyhte": "... [Mx]"}], "en_olasi_tani": "<kod>", "kanit_yonu": "destekliyor | zayiflatiyor | belirsiz", "bakilacak_bulgular": ["... [Mx]"]}

Sınıf kodları: akiec (aktinik keratoz / Bowen), bcc (bazal hücreli karsinom), bkl (benign keratoz), df (dermatofibrom), mel (melanom), nv (melanositik nevüs), vasc (vasküler lezyon).
"kanit_yonu": kanıtın bütün olarak CNN'in kararını destekleyip desteklemediğidir."""


def _softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def _yas(x):
    return 'bilinmiyor' if pd.isna(x) else f'{int(x)}'


class KanitDeposu:
    """Önceki adımların bütün çıktılarını yükler ve tek bir vaka için kanıt paketi üretir."""

    def __init__(self, proje, arama):
        self.arama = arama
        with open(f'{proje}/results/03v2_son_cnn.json', encoding='utf-8') as f:
            son = json.load(f)
        with open(f'{proje}/bulanik/05_kapi_ayarlari.json', encoding='utf-8') as f:
            kapi = json.load(f)
        self.siniflar = son['siniflar']
        log_oncel = np.array(son['log_oncel'])
        meta = pd.read_csv(f'{proje}/splits/ham10000_split.csv')
        self.kume = {k: meta[meta['split'] == k].reset_index(drop=True) for k in ['dogrulama', 'test']}
        self.arsiv = pd.read_csv(f'{proje}/rag/arsiv_meta.csv')
        self.kapi = bk.BulanikKapi(kapi['yuzdelikler'])
        self.esik = kapi['esik']
        self.logit, self.p_cnn, self.karar, self.p_arsiv, self.komsu, self.benzerlik, self.kapi_skor = {}, {}, {}, {}, {}, {}, {}
        kh = [self.siniflar.index(s) for s in KOTU_HUYLU]
        self.kapi_girdi = {}
        for k in self.kume:
            z = np.load(f'{proje}/models/son_cnn_{k}_logit.npy')
            self.logit[k] = z
            self.p_cnn[k] = _softmax(z / son['T'])
            self.karar[k] = (z - son['tau_klinik'] * log_oncel).argmax(1)
            self.p_arsiv[k] = np.load(f'{proje}/rag/arsiv_olasilik_{k}.npy')
            kd = np.load(f'{proje}/rag/komsular_{k}.npz')
            self.komsu[k], self.benzerlik[k] = kd['komsu'], kd['benzerlik']
            self.kapi_skor[k] = np.load(f'{proje}/bulanik/kapi_skoru_{k}.npy')
            n = np.arange(len(z))
            self.kapi_girdi[k] = {'guven': self.p_cnn[k][n, self.karar[k]], 'uyum': self.p_arsiv[k][n, self.karar[k]],
                                  'risk': 0.5 * (self.p_cnn[k][:, kh].sum(1) + self.p_arsiv[k][:, kh].sum(1)),
                                  'yas': self.kume[k]['age'].astype(float).values}

    def konsey_vakalari(self, k):
        return np.where(self.kapi_skor[k] > self.esik)[0]

    def literatur_sorgulari(self, adaylar):
        if len(adaylar) == 1:
            a = SINIF_EN[adaylar[0]]
            return [f'dermoscopic features of {a}', f'lesions mimicking {a} on dermoscopy and differential diagnosis']
        sorgular = [f'dermoscopic criteria to differentiate {SINIF_EN[a]} from {SINIF_EN[b]}'
                    for j, a in enumerate(adaylar) for b in adaylar[j + 1:]]
        return sorgular[:3] + [f'dermoscopic features of {SINIF_EN[adaylar[0]]}']

    def paket(self, k, i, n_komsu=5, n_makale=6, makale_basina=3, ozet_uzunlugu=1200):
        S, v = self.siniflar, self.kume[k].loc[i]
        karar = S[self.karar[k][i]]
        p = self.p_cnn[k][i]
        ilk3 = np.argsort(-p)[:3]
        pa = self.p_arsiv[k][i]
        arsiv3 = np.argsort(-pa)[:3]
        adaylar = list(dict.fromkeys([karar, S[ilk3[0]], S[arsiv3[0]]]))
        # Konsey kapısının gerekçesi
        G = {g: self.kapi_girdi[k][g][i] for g in ['guven', 'uyum', 'risk', 'yas']}
        skor, _, guc = self.kapi.skor(G['guven'], G['uyum'], G['risk'], G['yas'], ayrinti=True)
        kurallar = [(ad, metin, float(guc[ad][0])) for ad, metin, _, _ in bk.KURALLAR if guc[ad][0] > 0.2]
        # Literatür
        sorgular = self.literatur_sorgulari(adaylar)
        makaleler, gorulen = [], set()
        for s in sorgular:
            for _, r in self.arama.ara(s, k=makale_basina).iterrows():
                if r['pmid'] not in gorulen and len(makaleler) < n_makale:
                    gorulen.add(r['pmid'])
                    makaleler.append({'pmid': str(r['pmid']), 'yil': None if pd.isna(r['yil']) else int(r['yil']),
                                      'baslik': r['baslik'], 'ozet': r['ozet'][:ozet_uzunlugu]})
        # Benzer vakalar
        komsular = []
        for j in range(n_komsu):
            a = self.arsiv.loc[self.komsu[k][i, j]]
            komsular.append({'tani': a['dx'], 'dogrulama': DOGRULAMA_TR.get(a['dx_type'], a['dx_type']),
                             'benzerlik': float(self.benzerlik[k][i, j]), 'yas': _yas(a['age']),
                             'cinsiyet': CINSIYET_TR.get(a['sex'], 'bilinmiyor'), 'bolge': a['localization']})
        # Metin
        sat = [f'VAKA [HASTA]: yaş {_yas(v["age"])}, cinsiyet {CINSIYET_TR.get(v["sex"], "bilinmiyor")}, bölge {v["localization"]}.',
               f'CNN [CNN]: klinik eşikli karar = {SINIF_TR[karar]} ({karar}); bu karara kalibre güven %{100 * p[S.index(karar)]:.0f}. '
               'İlk 3 olasılık: ' + ', '.join(f'{SINIF_TR[S[c]]} ({S[c]}) %{100 * p[c]:.0f}' for c in ilk3) + '.',
               f'KONSEY KAPISI [KAPI]: konsey gerekliliği {skor[0]:.1f} (eşik {self.esik:.1f}). Ateşlenen kurallar: '
               + '; '.join(f'{ad} "{metin}" (güç {g:.2f})' for ad, metin, g in kurallar) + '.',
               f'ARŞİV OYLAMASI [ARSIV]: en benzer 50 eğitim vakasının sınıf sıklığına göre düzeltilmiş oyları: '
               + ', '.join(f'{SINIF_TR[S[c]]} ({S[c]}) %{100 * pa[c]:.0f}' for c in arsiv3) + '.',
               '', 'BENZER VAKALAR (eğitim arşivinden, tanısı bilinen):']
        for j, a in enumerate(komsular, 1):
            sat.append(f'[V{j}] {SINIF_TR[a["tani"]]} ({a["tani"]}) | tanı doğrulama: {a["dogrulama"]} | benzerlik {a["benzerlik"]:.2f} | '
                       f'{a["yas"]} yaş, {a["cinsiyet"]}, {a["bolge"]}')
        sat += ['', 'MAKALELER (PubMed özetleri):']
        for j, m in enumerate(makaleler, 1):
            sat.append(f'[M{j}] PMID {m["pmid"]} ({m["yil"]}) {m["baslik"]}\nÖzet: {m["ozet"]}')
        gecerli = {'CNN', 'HASTA', 'KAPI', 'ARSIV'} | {f'V{j}' for j in range(1, len(komsular) + 1)} | {f'M{j}' for j in range(1, len(makaleler) + 1)}
        return {'kume': k, 'indeks': int(i), 'image_id': v['image_id'], 'gercek': v['dx'], 'cnn_karar': karar,
                'arsiv_en_olasi': S[arsiv3[0]], 'adaylar': adaylar, 'kapi_skoru': float(skor[0]), 'sorgular': sorgular,
                'komsular': komsular, 'makaleler': makaleler, 'gecerli_kaynaklar': sorted(gecerli), 'metin': '\n'.join(sat)}


def kaynaklari_bul(metin):
    etiketler = []
    for icerik in re.findall(r'\[([^\[\]]{1,40})\]', metin or ''):
        etiketler += [t for t in re.split(r'[\s,;]+', icerik.strip()) if t]
    return etiketler


def _metinler(cikti):
    parcalar = [cikti.get('ozet', '')]
    for a in cikti.get('aday_tanilar', []) or []:
        if isinstance(a, dict):
            parcalar += [str(a.get('lehte', '')), str(a.get('aleyhte', ''))]
    parcalar += [str(b) for b in (cikti.get('bakilacak_bulgular', []) or [])]
    return [str(p) for p in parcalar if p]


def dogrula(cikti, paket, siniflar):
    """Biçim ve kaynak kontrolü. Uydurma kaynak: pakette olmayan herhangi bir köşeli parantez etiketi."""
    if not isinstance(cikti, dict):
        return {'json_gecerli': False}
    gecerli = set(paket['gecerli_kaynaklar'])
    metinler = _metinler(cikti)
    etiketler = [e for m in metinler for e in kaynaklari_bul(m)]
    uydurma = sorted({e for e in etiketler if e not in gecerli})
    cumleler = [c for c in re.split(r'(?<=[.!?])\s+', str(cikti.get('ozet', '')).strip()) if len(c) > 15]
    kaynaksiz = [c for c in cumleler if not kaynaklari_bul(c)]
    adaylar = [a.get('sinif') for a in (cikti.get('aday_tanilar') or []) if isinstance(a, dict)]
    return {'json_gecerli': True,
            'alanlar_tam': all(a in cikti for a in ['ozet', 'aday_tanilar', 'en_olasi_tani', 'kanit_yonu', 'bakilacak_bulgular']),
            'en_olasi_gecerli': cikti.get('en_olasi_tani') in siniflar,
            'kanit_yonu_gecerli': cikti.get('kanit_yonu') in KANIT_YONLERI,
            'aday_siniflar_gecerli': all(a in siniflar for a in adaylar) and len(adaylar) > 0,
            'kaynak_sayisi': len(etiketler), 'uydurma_kaynaklar': uydurma,
            'kullanilan_makale': len({e for e in etiketler if e.startswith('M') and e in gecerli}),
            'kullanilan_vaka': len({e for e in etiketler if e.startswith('V') and e in gecerli}),
            'ozet_cumle': len(cumleler), 'kaynaksiz_cumle': len(kaynaksiz)}


def _sade(x):
    return str(x or '').strip().lower().translate(str.maketrans('ıİşŞğĞüÜöÖçÇ', 'iissgguuoocc'))


def normallestir(cikti):
    """Küçük biçim farklarını düzeltir: 'Zayıflatıyor' -> 'zayiflatiyor', 'MEL' -> 'mel'."""
    if isinstance(cikti, dict):
        cikti['kanit_yonu'] = _sade(cikti.get('kanit_yonu'))
        cikti['en_olasi_tani'] = _sade(cikti.get('en_olasi_tani'))
        for a in cikti.get('aday_tanilar') or []:
            if isinstance(a, dict):
                a['sinif'] = _sade(a.get('sinif'))
    return cikti


def calistir(paket, istemci, siniflar):
    cevap = istemci.cagir(SISTEM_ISTEMI, paket['metin'], json_cikti=True)
    cikti = normallestir(json_ayikla(cevap['metin']))
    return {'cikti': cikti, 'dogrulama': dogrula(cikti, paket, siniflar), 'ham_metin': cevap['metin'],
            'girdi_token': cevap['girdi_token'], 'cikti_token': cevap['cikti_token'], 'onbellekten': cevap['onbellekten']}

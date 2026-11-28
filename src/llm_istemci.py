"""Sağlayıcıdan bağımsız dil modeli istemcisi.

- Sağlayıcılar: 'gemini' (google-genai), 'anthropic', 'openai'. Değiştirmek için yalnızca saglayici ve model değişir.
- Önbellek: Her istek (sağlayıcı, model, sıcaklık, sistem istemi, mesaj) özetiyle Drive'a kaydedilir. Aynı istek
  ikinci kez yapılırsa API'ye gidilmez; böylece sonuçlar tekrarlanabilir olur ve aynı cevaba iki kez para ödenmez.
- Hız sınırı: dakikada en fazla `dakikada_istek` istek. Kota hatalarında (429 vb.) bekleyip yeniden dener.
- Zaman aşımı: Bir istek `zaman_asimi_sn` saniyede cevap gelmezse kesilir ve yeniden denenir (sunucu yoğunken takılı kalmayı önler).
"""
import os
import re
import json
import time
import hashlib

KOTA_IZLERI = ('429', 'RESOURCE_EXHAUSTED', 'rate limit', 'Rate limit', 'quota', 'Quota', 'overloaded', '503', '529', 'UNAVAILABLE',
               '504', 'DEADLINE_EXCEEDED', 'timed out', 'Timeout', 'timeout')
KALICI_HATA_IZLERI = ('400', '401', '403', '404', 'INVALID_ARGUMENT', 'PERMISSION_DENIED', 'NOT_FOUND', 'API key not valid',
                      'UNAUTHENTICATED', 'invalid_api_key', 'model_not_found')


class LLMIstemci:
    def __init__(self, saglayici, model, api_anahtari, onbellek=None, dakikada_istek=8, sicaklik=0.0, en_fazla_token=8192,
                 zaman_asimi_sn=120):
        self.saglayici, self.model, self.sicaklik = saglayici, model, sicaklik
        self.dakikada_istek, self.en_fazla_token, self.onbellek = dakikada_istek, en_fazla_token, onbellek
        self._son = 0.0
        self.istatistik = {'api_istegi': 0, 'onbellekten': 0, 'girdi_token': 0, 'cikti_token': 0}
        if onbellek:
            os.makedirs(onbellek, exist_ok=True)
        if saglayici == 'gemini':
            from google import genai
            from google.genai import types
            self._istemci = genai.Client(api_key=api_anahtari, http_options=types.HttpOptions(timeout=int(zaman_asimi_sn * 1000)))
        elif saglayici == 'anthropic':
            import anthropic
            self._istemci = anthropic.Anthropic(api_key=api_anahtari, timeout=zaman_asimi_sn, max_retries=0)
        elif saglayici == 'openai':
            from openai import OpenAI
            self._istemci = OpenAI(api_key=api_anahtari, timeout=zaman_asimi_sn, max_retries=0)
        else:
            raise ValueError(f'Bilinmeyen sağlayıcı: {saglayici}')

    def _anahtar(self, sistem, mesaj, json_cikti):
        ham = json.dumps([self.saglayici, self.model, self.sicaklik, sistem, mesaj, json_cikti], ensure_ascii=False)
        return hashlib.sha256(ham.encode('utf-8')).hexdigest()[:32]

    def _ham_cagri(self, sistem, mesaj, json_cikti):
        """(metin, girdi_token, cikti_token) döndürür."""
        if self.saglayici == 'gemini':
            from google.genai import types
            ayar = types.GenerateContentConfig(system_instruction=sistem, temperature=self.sicaklik,
                                               max_output_tokens=self.en_fazla_token,
                                               response_mime_type='application/json' if json_cikti else None)
            r = self._istemci.models.generate_content(model=self.model, contents=mesaj, config=ayar)
            u = r.usage_metadata
            cikti = (getattr(u, 'candidates_token_count', 0) or 0) + (getattr(u, 'thoughts_token_count', 0) or 0)
            return (r.text or ''), (getattr(u, 'prompt_token_count', 0) or 0), cikti
        if self.saglayici == 'anthropic':
            r = self._istemci.messages.create(model=self.model, max_tokens=self.en_fazla_token, temperature=self.sicaklik,
                                              system=sistem, messages=[{'role': 'user', 'content': mesaj}])
            metin = ''.join(getattr(b, 'text', '') for b in r.content)
            return metin, r.usage.input_tokens, r.usage.output_tokens
        r = self._istemci.chat.completions.create(
            model=self.model, temperature=self.sicaklik,
            messages=[{'role': 'system', 'content': sistem}, {'role': 'user', 'content': mesaj}],
            **({'response_format': {'type': 'json_object'}} if json_cikti else {}))
        return (r.choices[0].message.content or ''), r.usage.prompt_tokens, r.usage.completion_tokens

    def cagir(self, sistem, mesaj, json_cikti=True, deneme_sayisi=6):
        anahtar = self._anahtar(sistem, mesaj, json_cikti)
        yol = f'{self.onbellek}/{anahtar}.json' if self.onbellek else None
        if yol and os.path.exists(yol):
            with open(yol, encoding='utf-8') as f:
                kayit = json.load(f)
            self.istatistik['onbellekten'] += 1
            return {**kayit, 'onbellekten': True}
        bekle = 60.0 / self.dakikada_istek - (time.time() - self._son)
        if bekle > 0:
            time.sleep(bekle)
        for deneme in range(deneme_sayisi):
            try:
                t0 = time.time()
                metin, girdi, cikti = self._ham_cagri(sistem, mesaj, json_cikti)
                break
            except Exception as hata:
                kota = any(iz in str(hata) for iz in KOTA_IZLERI)
                if not kota and any(iz in str(hata) for iz in KALICI_HATA_IZLERI):
                    raise RuntimeError(f'Düzeltilemeyen API hatası (anahtar, model adı ya da istek biçimi): {str(hata)[:300]}') from hata
                if deneme == deneme_sayisi - 1:
                    raise
                sure = 65 if kota else 10 * (deneme + 1)
                print(f'  {"kota/yoğunluk" if kota else "hata"}: {str(hata)[:150]} -> {sure} sn bekleniyor ({deneme + 1}/{deneme_sayisi})')
                time.sleep(sure)
        self._son = time.time()
        kayit = {'saglayici': self.saglayici, 'model': self.model, 'sicaklik': self.sicaklik,
                 'sistem': sistem, 'mesaj': mesaj, 'metin': metin, 'girdi_token': int(girdi), 'cikti_token': int(cikti),
                 'sure_sn': round(time.time() - t0, 2), 'zaman': time.strftime('%Y-%m-%d %H:%M:%S')}
        if yol:
            with open(yol, 'w', encoding='utf-8') as f:
                json.dump(kayit, f, ensure_ascii=False, indent=1)
        self.istatistik['api_istegi'] += 1
        self.istatistik['girdi_token'] += int(girdi)
        self.istatistik['cikti_token'] += int(cikti)
        return {**kayit, 'onbellekten': False}


def gemini_modeli_sec(api_anahtari, tercih='flash'):
    """Hesapta generateContent destekleyen Gemini modellerini listeler ve kararlı, en yeni 'flash' modelini önerir."""
    from google import genai
    adlar = []
    istemci = genai.Client(api_key=api_anahtari)   # değişkende tutulmalı: geçici istemci silinince bağlantısı kapanır ve liste okunamaz
    for m in istemci.models.list():
        eylemler = getattr(m, 'supported_actions', None) or []
        if 'generateContent' in eylemler:
            adlar.append(m.name.replace('models/', ''))
    istenmeyen = ('preview', 'exp', 'image', 'tts', 'live', 'audio', 'thinking', '8b', 'embedding', 'latest')

    def surum(ad):
        m = re.search(r'gemini-(\d+(?:\.\d+)?)', ad)
        return float(m.group(1)) if m else 0.0
    for tur in ([tercih + '-lite'] if tercih.endswith('lite') else [tercih, tercih + '-lite']):
        adaylar = [a for a in adlar if a.endswith(tur) and not any(x in a for x in istenmeyen)]
        if adaylar:
            return sorted(adaylar, key=surum, reverse=True)[0], adlar
    return None, adlar


def json_ayikla(metin):
    """Model cevabından JSON nesnesini çıkarır (kod bloğu işaretleri vb. temizlenir). Başarısızsa None."""
    if not metin:
        return None
    t = metin.strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    try:
        return json.loads(t)
    except Exception:
        a, b = t.find('{'), t.rfind('}')
        if a >= 0 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                return None
    return None

"""PubMed literatür kütüphanesinde arama: MedCPT sorgu kodlayıcı + FAISS (iç çarpım) + isteğe bağlı MedCPT çapraz kodlayıcı ile yeniden sıralama."""
import json
import numpy as np
import pandas as pd
import faiss
import torch
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification


class PubmedArama:
    def __init__(self, klasor, sorgu_modeli='ncbi/MedCPT-Query-Encoder', capraz_model='ncbi/MedCPT-Cross-Encoder', cihaz=None):
        self.cihaz = cihaz or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.indeks = faiss.read_index(f'{klasor}/pubmed.faiss')
        self.makaleler = pd.read_parquet(f'{klasor}/pubmed_makaleler.parquet')
        assert self.indeks.ntotal == len(self.makaleler), 'İndeks ile makale tablosu uyuşmuyor'
        self.s_tok = AutoTokenizer.from_pretrained(sorgu_modeli)
        self.s_model = AutoModel.from_pretrained(sorgu_modeli).to(self.cihaz).eval()
        self.c_tok = self.c_model = None
        if capraz_model:
            self.c_tok = AutoTokenizer.from_pretrained(capraz_model)
            self.c_model = AutoModelForSequenceClassification.from_pretrained(capraz_model).to(self.cihaz).eval()

    @torch.no_grad()
    def sorgu_vektoru(self, sorgular):
        g = self.s_tok(list(sorgular), truncation=True, padding=True, max_length=64, return_tensors='pt').to(self.cihaz)
        return self.s_model(**g).last_hidden_state[:, 0, :].float().cpu().numpy().astype('float32')

    @torch.no_grad()
    def capraz_puan(self, sorgu, satirlar):
        ciftler = [[sorgu, f'{b} {o}'] for b, o in zip(satirlar['baslik'], satirlar['ozet'])]
        g = self.c_tok(ciftler, truncation=True, padding=True, max_length=512, return_tensors='pt').to(self.cihaz)
        return self.c_model(**g).logits.squeeze(-1).float().cpu().numpy()

    def ara(self, sorgu, k=5, aday=50, yeniden_sirala=True):
        """En ilgili k makale. Önce FAISS ile 'aday' kadar makale bulunur; çapraz kodlayıcı varsa bunlar yeniden sıralanır."""
        puan, ix = self.indeks.search(self.sorgu_vektoru([sorgu]), aday)
        sonuc = self.makaleler.iloc[ix[0]].copy()
        sonuc['faiss_puani'] = puan[0]
        if yeniden_sirala and self.c_model is not None:
            sonuc['capraz_puan'] = self.capraz_puan(sorgu, sonuc)
            sonuc = sonuc.sort_values('capraz_puan', ascending=False)
        return sonuc.head(k).reset_index(drop=True)

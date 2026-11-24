# Defterler (Colab)

Defterler Google Colab'da çalıştırılır; veri ve modeller Google Drive'da tutulur (repoda yok). Adlandırma: `NN_konu_vX.ipynb`, `NN` proje adımını, `vX` sürümü gösterir.

| Defter | Adım | Ne yapar | Durum |
|---|---|---|---|
| [`01_veri_hazirligi.ipynb`](01_veri_hazirligi.ipynb) | 1 | HAM10000 indirme, inceleme, lezyon bazlı %70/%15/%15 ayrım | Final |
| [`02_cnn_egitimi_v1.ipynb`](02_cnn_egitimi_v1.ipynb) | 2 | EfficientNetB0 ilk deneme (iki aşamalı eğitim, tam sınıf ağırlıkları); çıktılarıyla birlikte kayıtlı | Eski (doğrulama dengeli doğruluk 0,653) |
| [`02_cnn_egitimi_v2.ipynb`](02_cnn_egitimi_v2.ipynb) | 2 | Karekök sınıf ağırlıkları, gövdenin tamamı ince ayarda | Eski (0,673) |
| [`02_cnn_egitimi_v3_b0.ipynb`](02_cnn_egitimi_v3_b0.ipynb) | 2 | Model seçimi ve karar ayarı düzeltildi; B0 çalıştırması (`cnn_b0_v3`, en iyi tur 10, doğrulama dengeli doğruluğu 0,695) | Aday |
| [`02_cnn_egitimi_v3_b3.ipynb`](02_cnn_egitimi_v3_b3.ipynb) | 2 | Aynı defter, `MODEL_TIPI = 'B3'` (`cnn_b3_v3`, giriş 300, en iyi tur 11, 0,696) | Aday |
| [`02_cnn_egitimi_v4.ipynb`](02_cnn_egitimi_v4.ipynb) | 2 | Ön işleme tutarlılığı ve eğitim tarifi iyileştirmesi (`cnn_b0_v4`) | Aday |
| [`03_kalibrasyon_test_gradcam_v1.ipynb`](03_kalibrasyon_test_gradcam_v1.ipynb) | 3 | `cnn_b0_v3` için sıcaklık ölçekleme, test, Grad-CAM | Eski (v2 ile değiştirildi) |
| [`03_son_cnn_secimi_test_v2.ipynb`](03_son_cnn_secimi_test_v2.ipynb) | 3 | Adayları ve toplulukları doğrulamada karşılaştırır, son CNN'i seçer, kalibre eder, test eder, uzmana yönlendirme ve Grad-CAM | **Final** (seçilen: Topluluk + TTA) |

## Çalıştırma sırası

`01` → `02_*` (v3 B0, v3 B3 ve v4 modelleri gerekli) → `03_son_cnn_secimi_test_v2`. Eski sürümler (v1, v2, `03_..._v1`) tezde "denenen yaklaşımlar" için saklanır; yeniden çalıştırmak gerekmez.

## Notlar

- Test kümesi yalnızca Adım 3'te kullanılmıştır. Şeffaflık notu: `03_..._v1` defterinde B0 v3'ün test sonucu görülmüştür; son CNN'in seçimi ve ayarları (v2) yalnızca doğrulamaya dayanır.
- Çıktılar (grafikler, tablolar) defterlerin içinde kayıtlıdır; öne çıkan grafikler `../results/` altındadır.

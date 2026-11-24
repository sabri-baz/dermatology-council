# Tez Notları

Her adımın sonunda teze girecek cümleler, sayılar ve kararlar burada birikir. Tezi yazarken bu dosyadan başlanır.

---

## Adım 1: Veri Hazırlığı

### Veri seti
Çalışmada HAM10000 veri seti kullanılmıştır (Tschandl ve diğ., 2018). Veri seti, Viyana Tıp Üniversitesi Dermatoloji Bölümü ve Avustralya'daki bir cilt kanseri kliniğinden 20 yıllık süreçte toplanmış 10.015 dermatoskopik görüntüden oluşmakta ve 7 tanı sınıfını kapsamaktadır. Görüntüler 7.470 farklı lezyona aittir. Tanıların %53'ü (5.340 görüntü) histopatoloji ile doğrulanmıştır; kalanlar takip (3.704), uzman uzlaşısı (902) ve konfokal mikroskopi (69) ile belirlenmiştir.

### Sınıf dengesizliği
Veri seti belirgin biçimde dengesizdir: melanositik nevüs görüntülerin %66,9'unu oluştururken dermatofibrom yalnızca %1,1'ini oluşturmaktadır. Bu nedenle model başarımı düz doğruluk yerine dengeli doğruluk ve sınıf bazlı duyarlılık ile raporlanmıştır.

### Lezyon bazlı ayrım
Lezyonların 1.956'sının birden fazla görüntüsü bulunmakta ve görüntülerin yaklaşık %45'i bu lezyonlara ait olmaktadır. Aynı lezyonun görüntülerinin hem eğitim hem test kümesine düşmesini önlemek için ayrım görüntü yerine lezyon kimliğine (lesion_id) göre, sınıf oranlarını koruyacak şekilde tabakalı olarak yapılmıştır (%70 eğitim, %15 doğrulama, %15 test; random_state = 42). Sonuçta eğitim kümesinde 7.054, doğrulama kümesinde 1.464 ve test kümesinde 1.497 görüntü yer almıştır.

### Veri kalite kontrolleri
Tüm görüntüler 600×450 çözünürlüktedir. Dosya parmak izi (MD5) kontrolünde 2 çift birebir aynı görüntü bulunmuştur; her çift aynı lezyona ve tanıya aittir ve aynı kümede yer almaktadır, dolayısıyla kümeler arasında sızıntı yoktur. Görüntülerin 57'sinde yaş, 57'sinde cinsiyet (47'sinde ikisi birden), 234'ünde lezyon bölgesi bilinmemektedir.

### Gözlemler (ileride kullanılacak)
- Bazı görüntülerde cetvel işaretleri, kıllar ve dermatoskop çerçevesinden kaynaklanan koyu kenarlar bulunmaktadır. Modelin bu ipuçlarından kısa yol öğrenip öğrenmediği Adım 3'te Grad-CAM ile incelenecektir.
- Bilinmeyen yaş, cinsiyet ve bölge değerleri, bulanık mantık modülünde (Adım 8) nötr risk olarak ele alınacaktır.

### Sınırlılıklar
- Veri iki merkezden gelmektedir ve hastalar ağırlıklı olarak açık tenlidir; ten tipi etiketi bulunmamaktadır.
- Görüntülerin tamamı dermatoskopiktir; akıllı telefon fotoğraflarına genellenebilirlik bu çalışmanın kapsamı dışındadır.
- Nadir sınıflarda test örneği azdır (dermatofibrom ve vasküler lezyon için 22'şer görüntü); bu sınıflardaki sonuçlar dalgalı olabilir.

---

## Adım 2-3: CNN Eğitimi, Seçimi ve Test

### Süreç
EfficientNet-B0 dört sürümde (v1-v4) eğitilmiş, B3 v3 sürümünde eklenmiştir. Doğrulama dengeli doğruluğu v1: 0,653, v2: 0,673; v3 ve v4 ile iyileştirme sürmüştür. v2'de modelin yanlış turu (gürültülü dengeli doğruluğa göre) seçilmesi v3'te düzeltilmiş, v4'te ön işleme tutarlılığı sağlanmıştır.

### Son CNN seçimi
Adaylar (B0 v3, B3 v3, B0 v4, TTA'lı hâlleri ve toplulukları) test kümesine bakılmadan sabitlenmiş ve yalnızca doğrulamada karşılaştırılmıştır. Topluluk ile Topluluk + TTA dengeli doğrulukta eşit sayılmış (fark < 0,01), negatif log olabilirlik düşük olduğu için **Topluluk + TTA** seçilmiştir. Topluluğun üyeleri B0 v3 ve B3 v3'tür (B0 v4 tek başına aday olarak değerlendirilmiş, topluluğa girmemiştir). Sıcaklık T = 1,178 (ham model fazla özgüvenli), klinik eşik τ = 0,8.

### Test sonuçları (ayarlar dondurulduktan sonra, tek açılış)
- Ayarsız: doğruluk 0,821, dengeli doğruluk 0,653 (%95 GA 0,590-0,728), melanom duyarlılığı 0,756 (0,667-0,838).
- Klinik eşik: dengeli doğruluk 0,705, melanom duyarlılığı 0,869 (0,803-0,928), nevüs duyarlılığı 0,734.
- Topluluk + TTA ile tek model B0 v3 arasındaki fark istatistiksel olarak belirgin değildir (eşleştirilmiş bootstrap; aralık 0'ı içeriyor). Topluluğun asıl faydası kalibrasyondadır.
- Yalnızca patolojiyle doğrulanmış 804 test görüntüsünde dengeli doğruluk 0,575 (ayarsız) / 0,633 (klinik); zor vakalarda başarım düşmektedir.
- Nadir sınıflarda (dermatofibrom, vasküler lezyon: 22'şer görüntü) sonuçlar dalgalıdır.

### Uzmana yönlendirme (Bulanık mantık kapısının zeminini oluşturur)
Güveni en düşük %20 vaka uzmana yönlendirildiğinde (ayarsız) doğruluk 0,821 → 0,903, kaçırılan melanom 41 → 16 olmaktadır. %50 kapsamda doğruluk 0,971'dir. Bu, güvenin anlamlı bir belirsizlik sinyali olduğunu gösterir.

### Grad-CAM gözlemi
Dermatoskop kenar şeridi görüntü alanının %35'ini kaplamaktadır; ısı haritasının kenardaki payı ortancada %14'tür ve görüntülerin yalnızca %1'inde kenar payı alan payından büyüktür. Yani model çoğunlukla kenar artefaktına değil lezyona bakmaktadır (Adım 1'deki kısa yol endişesi büyük ölçüde giderilmiştir).

### Sınırlılıklar
- Tek bölünme (random_state = 42); farklı bölünmelerle tekrar yapılmamıştır.
- İyi kalibrasyon yanlış kararların olmadığı anlamına gelmez: klinik eşikte nevüs duyarlılığı 0,734'e düşerek yanlış alarm (169 görüntü) artar. Konsey bu ödünleşimi azaltmak için tasarlanmıştır.

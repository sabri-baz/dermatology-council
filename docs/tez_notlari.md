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

import sys
import time
from signal import pause
from gpiozero import Button, LED

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService

# =====================================================================
# SABİT TANIMLAMALAR & DEVICE ID'LER
# =====================================================================
CALL_DEVICE_ID = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
TAXI_DEVICE_ID = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
SWITCH_ID = "40049B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"

# LED Tanımlamaları
led_yesil = LED(25)  # Sistem hazır / Bağlantı aktif
led_sari = LED(24)  # İşlem yapılıyor
led_kirmizi = LED(23)  # Hata / Reddedildi


# =====================================================================
# BUTON FONKSİYONLARI
# =====================================================================

def secim_1_taksi_cagir(api: APIService):
    print("\n" + "=" * 45)
    print(">>> [1. BUTON] TAKSİ ÇAĞRILIYOR... <<<")
    print("=" * 45)

    led_sari.on()
    try:
        result = api.call_taxi(device_unique_id=TAXI_DEVICE_ID)
        print("[BAŞARILI] Taksi Çağrısı Yanıtı:", result)
    except Exception as e:
        print("[HATA] Taksi çağrılamadı:", e)
        led_kirmizi.blink(on_time=0.2, off_time=0.2, n=3, background=False)
    finally:
        led_sari.off()
        led_yesil.on()  # Yeşil LED'in açık kaldığından emin ol

    print("\n[BİLGİ] Butonlar dinleniyor...")


def secim_2_cagri_baslat(api: APIService):
    print("\n" + "=" * 45)
    print(">>> [2. BUTON] ÇAĞRI MODU SEÇİLDİ <<<")
    print("=" * 45)

    try:
        daire_no = input(">> Aramak istediğiniz Daire No'yu yazın (Varsayılan 1): ").strip()
        if not daire_no:
            daire_no = "1"

        print(f"\n[İŞLEM] Daire {daire_no} için sunucuya istek gönderiliyor...")
        led_sari.on()

        result = api.start_call(
            device_unique_id=CALL_DEVICE_ID,
            apartment_no=str(daire_no)
        )
        print(f"[BAŞARILI] Daire {daire_no} Çağrı Yanıtı:", result)
    except Exception as e:
        print("[HATA] Çağrı işlemi sırasında hata:", e)
        led_kirmizi.blink(on_time=0.2, off_time=0.2, n=3, background=False)
    finally:
        led_sari.off()
        led_yesil.on()  # İşlem bitince Yeşil LED yanmaya devam eder

    print("\n[BİLGİ] Butonlar dinleniyor...")


def secim_3_anahtar_durumu_degistir(api: APIService):
    print("\n" + "=" * 45)
    print(">>> [3. BUTON] RÖLE/ANAHTAR DURUMU DEĞİŞTİRİLİYOR (Outlet 1) <<<")
    print("=" * 45)

    led_sari.on()
    try:
        result = api.set_switch_status(
            switch_id=SWITCH_ID,
            device_unique_id=CALL_DEVICE_ID,
            outlet=1
        )
        print("[BAŞARILI] Anahtar Yanıtı:", result)
    except Exception as e:
        print("[HATA] Anahtar durumu değiştirilemedi:", e)
        led_kirmizi.blink(on_time=0.2, off_time=0.2, n=3, background=False)
    finally:
        led_sari.off()
        led_yesil.on()  # Yeşil LED açık kalır

    print("\n[BİLGİ] Butonlar dinleniyor...")


# =====================================================================
# ANA SİSTEM
# =====================================================================

def main():
    print("\n[SİSTEM] QRing Akıllı Panel Başlatılıyor...")

    # Başlangıçta tüm LED'leri sıfırla
    led_yesil.off()
    led_sari.off()
    led_kirmizi.off()

    # 1. API ve SignalR Hazırlığı
    session = create_api_session()
    api = APIService(session=session)
    signalr = SignalRService()

    try:
        print("[SİSTEM] Oturum açılıyor...")
        token = api.login("samsung.canli@fsitip.com", "Aa123456.")
        print("[SİSTEM] Giriş başarılı! Token alındı.")

        signalr.start_connection(token=token)
        time.sleep(1)

        # Oturum açılıp bağlantı sağlandığı an Yeşil LED sürekli yanar
        led_yesil.on()

    except Exception as e:
        print(f"\n[SİSTEM HATA] Giriş yapılırken hata oluştu: {e}")
        led_kirmizi.on()  # Bağlantı hatasında kırmızı sabit yanar
        return

    # 2. Donanımsal Buton Tanımları
    btn_taksi = Button(17, bounce_time=0.1)  # 1. Buton (GPIO 17)
    btn_cagri = Button(27, bounce_time=0.1)  # 2. Buton (GPIO 27)
    btn_anahtar = Button(22, bounce_time=0.1)  # 3. Buton (GPIO 22)

    # Olayları bağlama
    btn_taksi.when_pressed = lambda: secim_1_taksi_cagir(api)
    btn_cagri.when_pressed = lambda: secim_2_cagri_baslat(api)
    btn_anahtar.when_pressed = lambda: secim_3_anahtar_durumu_degistir(api)

    # 3. Ana Menü Ekranı
    print("\n" + "=" * 45)
    print("             QRING AKILLI PANEL MENÜSÜ       ")
    print("=" * 45)
    print("  [1] BUTON (GPIO 17) -> Taksi Çağır")
    print("  [2] BUTON (GPIO 27) -> Daire Ara (Daire No İster)")
    print("  [3] BUTON (GPIO 22) -> Röle Aç/Kapat (Outlet 1)")
    print("=" * 45)
    print("\n[BİLGİ] Sistem hazır (Yeşil LED Aktif). Bir butona basabilirsiniz... (Çıkış: CTRL+C)\n")

    try:
        pause()
    except (KeyboardInterrupt, EOFError):
        print("\n\n[SİSTEM] Çıkış yapılıyor...")
    finally:
        led_yesil.off()
        led_sari.off()
        led_kirmizi.off()
        signalr.stop_connection()
        print("[SİSTEM] Güvenle kapatıldı.")
        sys.exit(0)


if __name__ == "__main__":
    main()
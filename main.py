import sys
import requests
from signal import pause
from gpiozero import Button

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService

# =====================================================================
# MENÜ SEÇİMLERİNİN BUTON KARŞILIKLARI
# =====================================================================

def secim_1_taksi_cagir(api):
    print("\n--- TAKSİ ÇAĞRILIYOR ---")
    device_id = "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
    try:
        result = api.call_taxi(device_unique_id=device_id)
        print("Taksi İsteği Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


def secim_2_cagri_baslat(api):
    print("\n--- ÇAĞRI BAŞLATILIYOR ---")
    device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
    try:
        result = api.start_call(device_unique_id=device_id)
        print("Çağrı İsteği Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


def secim_3_anahtar_durumu_degistir(api):
    print("\n--- ANAHTAR DURUMU DEĞİŞTİRİLİYOR ---")
    switch_id = "1002533340"
    device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
    try:
        result = api.set_switch_status(switch_id=switch_id, device_unique_id=device_id)
        print("Anahtar Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


# =====================================================================
# ANA SİSTEM
# =====================================================================

def main():
    print("\n[SİSTEM] Başlatılıyor...")
    session = create_api_session()
    api = APIService(session=session)
    signalr = SignalRService()

    try:
        print("[SİSTEM] Oturum açılıyor...")
        token = api.login("samsung.canli@fsitip.com", "Aa123456.")
        print("[SİSTEM] Giriş başarılı! Token alındı.")

        # SignalR bağlantısını başlatıyoruz
        signalr.start_connection(token=token)

    except Exception as e:
        print(f"\n[SİSTEM HATA] Giriş yapılırken hata oluştu: {e}")
        return

    # İSTEDİĞİN MENÜ EKRANI
    print("\n================================")
    print("      SEÇİM YAPINIZ    ")
    print("================================")
    print("1 - Taksi Çağır                  (1. Buton - GPIO 17)")
    print("2 - Çağrı Başlat                 (2. Buton - GPIO 27 Tık)")
    print("3 - Anahtar/Röle Durumu Değiştir (2. Buton - GPIO 27 2sn Basılı)")
    print("E - Çıkış Yap                    (CTRL+C ile)")
    print("================================\n")

    # -----------------------------------------------------------------
    # DONANIMSAL BUTON TANIMLARI
    # -----------------------------------------------------------------
    btn1 = Button(17)
    btn2 = Button(27, hold_time=2)

    # Buton basışlarını fonksiyonlara bağlıyoruz
    btn1.when_pressed = lambda: secim_1_taksi_cagir(api)
    btn2.when_pressed = lambda: secim_2_cagri_baslat(api)
    btn2.when_held = lambda: secim_3_anahtar_durumu_degistir(api)

    try:
        # Butonları dinlemek için sistemi beklemede tutuyoruz
        pause()
    except (KeyboardInterrupt, EOFError):
        print("\n\n[SİSTEM] Çıkış yapıldı.")
    finally:
        signalr.stop_connection()
        sys.exit(0)


if __name__ == "__main__":
    main()
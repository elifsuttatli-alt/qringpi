import sys
from signal import pause
from gpiozero import Button

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService

# =====================================================================
# SABİT TANIMLAMALAR & DEVICE ID'LER
# =====================================================================
TAXI_DEVICE_ID = "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
CALL_DEVICE_ID = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
SWITCH_ID = "1002533340"


# =====================================================================
# MENÜ SEÇİMLERİNİN BUTON KARŞILIKLARI
# =====================================================================

def secim_1_taksi_cagir(api: APIService):
    print("\n--- TAKSİ ÇAĞRILIYOR ---")
    try:
        result = api.call_taxi(device_unique_id=TAXI_DEVICE_ID)
        print("Taksi İsteği Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


def secim_2_cagri_baslat(api: APIService):
    print("\n--- ÇAĞRI BAŞLATILIYOR ---")
    try:
        # APIService artık dinamik dış IP kullanıyor
        result = api.start_call(device_unique_id=CALL_DEVICE_ID)
        print("Çağrı İsteği Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


def secim_3_anahtar_durumu_degistir(api: APIService):
    print("\n--- ANAHTAR DURUMU DEĞİŞTİRİLİYOR ---")
    try:
        result = api.set_switch_status(switch_id=SWITCH_ID, device_unique_id=CALL_DEVICE_ID)
        print("Anahtar Yanıtı:", result, "\n")
    except Exception as e:
        print("Hata oluştu:", e, "\n")


# =====================================================================
# ANA SİSTEM
# =====================================================================

def main():
    print("\n[SİSTEM] Başlatılıyor...")

    # Interceptor destekli API Session oluşturuyoruz
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

    # KULLANICI ARAYÜZÜ
    print("\n=======================================================")
    print("                SİSTEM AKTİF / SEÇİM YAPIN              ")
    print("=======================================================")
    print("1. Buton (GPIO 17 / Pin 11) -> Taksi Çağır")
    print("2. Buton (GPIO 27 / Pin 13) -> Çağrı Başlat")
    print("3. Buton (GPIO 22 / Pin 15) -> Anahtar/Röle Durumu Değiştir")
    print("Çıkış yapmak için CTRL+C")
    print("=======================================================\n")

    # -----------------------------------------------------------------
    # DONANIMSAL BUTON TANIMLARI
    # -----------------------------------------------------------------
    btn1 = Button(17, bounce_time=0.1)
    btn2 = Button(27, bounce_time=0.1)
    btn3 = Button(22, bounce_time=0.1)

    # Buton olaylarını fonksiyonlara bağlıyoruz
    btn1.when_pressed = lambda: secim_1_taksi_cagir(api)
    btn2.when_pressed = lambda: secim_2_cagri_baslat(api)
    btn3.when_pressed = lambda: secim_3_anahtar_durumu_degistir(api)

    try:
        # Arka planda butonları ve SignalR bağlantısını dinlemede tut
        pause()
    except (KeyboardInterrupt, EOFError):
        print("\n\n[SİSTEM] Çıkış yapılıyor...")
    finally:
        signalr.stop_connection()
        print("[SİSTEM] Bağlantılar kapatıldı. Güvenle çıkıldı.")
        sys.exit(0)


if __name__ == "__main__":
    main()
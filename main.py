import sys
import requests
from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService


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

    # MENÜ DÖNGÜSÜ
    while True:
        print("\n================================")
        print("      SEÇİM YAPINIZ    ")
        print("================================")
        print("1 - Taksi Çağır")
        print("2 - Çağrı Başlat")
        print("3 - Anahtar/Röle Durumu Değiştir")
        print("E - Çıkış Yap")
        print("================================")

        try:
            secim = input("Seçiminiz (1/2/3/E): ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[SİSTEM] Çıkış yapıldı.")
            signalr.stop_connection()
            sys.exit(0)

        if secim == "1":
            print("\n--- TAKSİ ÇAĞRILIYOR ---")
            device_id = "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
            try:
                result = api.call_taxi(device_unique_id=device_id)
                print("Taksi İsteği Yanıtı:", result, "\n")
            except Exception as e:
                print("Hata oluştu:", e, "\n")

        elif secim == "2":
            print("\n--- ÇAĞRI BAŞLATILIYOR ---")
            device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
            try:
                result = api.start_call(device_unique_id=device_id)
                print("Çağrı İsteği Yanıtı:", result, "\n")
            except Exception as e:
                print("Hata oluştu:", e, "\n")

        elif secim == "3":
            print("\n--- ANAHTAR DURUMU DEĞİŞTİRİLİYOR ---")
            switch_id = "1002533340"
            device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
            try:
                result = api.set_switch_status(switch_id=switch_id, device_unique_id=device_id)
                print("Anahtar Yanıtı:", result, "\n")
            except Exception as e:
                print("Hata oluştu:", e, "\n")

        elif secim == "E":
            print("\n[SİSTEM] Programdan çıkış yapılıyor...")
            signalr.stop_connection()
            break

        else:
            print("\n[HATA] Geçersiz seçim! Lütfen 1, 2, 3 veya E girin.\n")


if __name__ == "__main__":
    main()
import sys
import threading
from signal import pause

from gpiozero import Button, LED

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService


# ============================================================
# DEVICE ID / SWITCH ID
# ============================================================

TAXI_DEVICE_ID = (
    "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
)

CALL_DEVICE_ID = (
    "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
)

SWITCH_ID = "1002533340"


# ============================================================
# LOGIN BİLGİLERİ
# ============================================================

USERNAME = "samsung.canli@fsitip.com"
PASSWORD = "Aa123456."


# ============================================================
# GPIO PINLERİ
# ============================================================

# 3 işlem butonu
TAXI_BUTTON_PIN = 17       # Fiziksel Pin 11
CALL_BUTTON_PIN = 27       # Fiziksel Pin 13
SWITCH_BUTTON_PIN = 22     # Fiziksel Pin 15

# Sistem ON / OFF butonu
POWER_BUTTON_PIN = 12      # Fiziksel Pin 32


# Trafik lambası
BOOT_GREEN_PIN = 5         # Fiziksel Pin 29
BOOT_YELLOW_PIN = 6        # Fiziksel Pin 31
BOOT_RED_PIN = 13          # Fiziksel Pin 33


# Ayrı durum LED'leri
ACTION_GREEN_PIN = 23      # Fiziksel Pin 16
ACTION_YELLOW_PIN = 24     # Fiziksel Pin 18
ACTION_RED_PIN = 25        # Fiziksel Pin 22


# ============================================================
# LED KONTROL SINIFI
# ============================================================

class StatusLEDs:

    def __init__(self, green_pin, yellow_pin, red_pin):

        self.green = LED(green_pin)
        self.yellow = LED(yellow_pin)
        self.red = LED(red_pin)

        self.off()


    def off(self):
        """Bütün LED'leri kapat."""
        self.green.off()
        self.yellow.off()
        self.red.off()


    def loading(self):
        """
        İşlem devam ediyor:
        Sarı LED yanıp söner.
        """

        self.off()

        self.yellow.blink(
            on_time=0.4,
            off_time=0.4,
            background=True
        )


    def success(self):
        """
        Başarılı:
        Sadece yeşil LED yanar.
        """

        self.off()
        self.green.on()


    def fail(self):
        """
        Başarısız:
        Sadece kırmızı LED yanar.
        """

        self.off()
        self.red.on()


    def close(self):
        """Program kapanırken GPIO kaynaklarını bırak."""

        self.off()

        self.green.close()
        self.yellow.close()
        self.red.close()


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    # --------------------------------------------------------
    # LED GRUPLARI
    # --------------------------------------------------------

    # Trafik lambası
    boot_leds = StatusLEDs(
        green_pin=BOOT_GREEN_PIN,
        yellow_pin=BOOT_YELLOW_PIN,
        red_pin=BOOT_RED_PIN
    )


    # Ayrı 3 durum LED'i
    action_leds = StatusLEDs(
        green_pin=ACTION_GREEN_PIN,
        yellow_pin=ACTION_YELLOW_PIN,
        red_pin=ACTION_RED_PIN
    )


    # --------------------------------------------------------
    # PROGRAM İLK AÇILDIĞINDA
    # --------------------------------------------------------

    # Sistem henüz başlatılmadı -> KIRMIZI
    boot_leds.fail()

    # İşlem LED'leri kapalı
    action_leds.off()


    print("\n=======================================================")
    print("              QRING RASPBERRY PI SİSTEMİ")
    print("=======================================================")
    print("[SİSTEM] Program çalışıyor.")
    print("[SİSTEM] Sistem şu anda KAPALI.")
    print("[SİSTEM] Başlatmak için ON/OFF butonuna basın.")
    print("=======================================================\n")


    # --------------------------------------------------------
    # BUTONLARI TANIMLA
    # --------------------------------------------------------

    btn_taxi = Button(
        TAXI_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.1
    )

    btn_call = Button(
        CALL_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.1
    )

    btn_switch = Button(
        SWITCH_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.1
    )

    power_button = Button(
        POWER_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.2
    )


    # --------------------------------------------------------
    # SİSTEM DEĞİŞKENLERİ
    # --------------------------------------------------------

    system_active = False
    system_starting = False

    api = None

    signalr = SignalRService()

    # Aynı anda iki işlem butonunun API isteği göndermesini engeller
    action_lock = threading.Lock()

    # ON/OFF işlemlerinin üst üste binmesini engeller
    power_lock = threading.Lock()


    # ========================================================
    # MENÜ
    # ========================================================

    def show_menu():

        print("\n=======================================================")
        print("                    SİSTEM AKTİF")
        print("=======================================================")
        print("1. BUTON -> Taksi Çağır")
        print("2. BUTON -> Çağrı Başlat")
        print("3. BUTON -> Anahtar/Röle Durumu Değiştir")
        print("ON/OFF    -> Sistemi Kapat")
        print("=======================================================\n")


    # ========================================================
    # CALL REJECTED
    # ========================================================

    def call_rejected():
        """
        SignalR üzerinden CallRejected geldiğinde çalışır.
        """

        if not system_active:
            return

        print("\n[CALL] Çağrı reddedildi.")
        print("[LED] İşlem durumu -> KIRMIZI")

        action_leds.fail()


    # SignalRService'e callback'i ver
    signalr.set_rejection_callback(
        call_rejected
    )


    # ========================================================
    # SİSTEMİ BAŞLAT
    # ========================================================

    def start_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal api


        # Zaten açıksa tekrar başlatma
        if system_active:
            print("[SİSTEM] Sistem zaten açık.")
            return


        # Zaten başlatılıyorsa tekrar başlatma
        if system_starting:
            print("[SİSTEM] Sistem zaten başlatılıyor.")
            return


        system_starting = True


        print("\n=======================================================")
        print("[SİSTEM] BAŞLATILIYOR")
        print("=======================================================")


        # ----------------------------------------------------
        # LOGIN BAŞLIYOR
        # ----------------------------------------------------

        # Kırmızıyı kapat
        # Sarıyı yanıp söndür
        boot_leds.loading()

        print("[LED] Trafik lambası -> SARI")
        print("[SİSTEM] Login isteği gönderiliyor...")


        try:

            # ------------------------------------------------
            # API SESSION
            # ------------------------------------------------

            session = create_api_session()

            api = APIService(
                session=session
            )


            # ------------------------------------------------
            # LOGIN + TOKEN
            # ------------------------------------------------

            token = api.login(
                USERNAME,
                PASSWORD
            )


            # Token gerçekten geldi mi kontrol et
            if not token:
                raise RuntimeError(
                    "Login başarılı görünmesine rağmen token alınamadı."
                )


            print("[SİSTEM] Login başarılı.")
            print("[SİSTEM] Token başarıyla alındı.")


            # ------------------------------------------------
            # TOKEN GELDİ -> YEŞİL
            # ------------------------------------------------

            boot_leds.success()

            print("[LED] Trafik lambası -> YEŞİL")


            # ------------------------------------------------
            # SIGNALR
            # ------------------------------------------------

            print("[SİSTEM] SignalR bağlantısı kuruluyor...")


            connected = signalr.start_connection(
                token=token,
                timeout=12
            )


            if not connected:

                # Burada trafik lambasını kırmızı yapmıyoruz.
                # Çünkü yeşil LED TOKEN'ın başarılı alındığını temsil ediyor.

                system_active = False
                system_starting = False

                print("\n[SIGNALR HATA] SignalR bağlantısı kurulamadı.")
                print("[SİSTEM] Token alındı ancak sistem tamamen hazır değil.")
                print("[LED] Trafik lambası YEŞİL kalıyor.")

                return


            # ------------------------------------------------
            # SİSTEM HAZIR
            # ------------------------------------------------

            system_active = True
            system_starting = False


            print("[SİSTEM] SignalR bağlantısı hazır.")
            print("[SİSTEM] Sistem tamamen aktif.")


            # Yeşil burada SÖNMÜYOR
            # Sistem açık kaldığı sürece yanmaya devam ediyor.
            boot_leds.success()


            show_menu()


        except Exception as e:

            system_active = False
            system_starting = False


            print("\n=======================================================")
            print("[SİSTEM HATA]")
            print(e)
            print("=======================================================")


            # Login / token başarısız -> KIRMIZI
            boot_leds.fail()

            print("[LED] Trafik lambası -> KIRMIZI")


            # SignalR yarım kaldıysa kapat
            signalr.stop_connection()


    # ========================================================
    # SİSTEMİ KAPAT
    # ========================================================

    def stop_system():

        nonlocal system_active
        nonlocal system_starting


        print("\n=======================================================")
        print("[SİSTEM] KAPATILIYOR")
        print("=======================================================")


        system_active = False
        system_starting = False


        # SignalR bağlantısını kapat
        signalr.stop_connection()


        # İşlem LED'lerini söndür
        action_leds.off()


        # Sistem kapalı -> trafik lambası KIRMIZI
        boot_leds.fail()


        print("[LED] Trafik lambası -> KIRMIZI")
        print("[SİSTEM] Sistem kapalı.")
        print("[SİSTEM] Yeniden başlatmak için ON/OFF butonuna basın.\n")


    # ========================================================
    # POWER BUTONU
    # ========================================================

    def toggle_power():

        if not power_lock.acquire(blocking=False):
            return


        try:

            if system_active or system_starting:

                stop_system()

            else:

                start_system()


        finally:

            power_lock.release()


    # ========================================================
    # 1. BUTON -> TAKSİ ÇAĞIR
    # ========================================================

    def taxi_action():

        if not system_active:

            print("[UYARI] Sistem kapalı. Önce sistemi başlatın.")
            return


        # Başka işlem devam ediyorsa yeni işlem başlatma
        if not action_lock.acquire(blocking=False):

            print("[UYARI] Başka bir işlem devam ediyor.")
            return


        try:

            print("\n=======================================================")
            print("TAKSİ ÇAĞRILIYOR")
            print("=======================================================")


            # İşlem devam ediyor
            action_leds.loading()

            print("[LED] İşlem durumu -> SARI")


            result = api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "[TAKSİ] API yanıtı:",
                result
            )


            # Başarılı
            action_leds.success()

            print("[LED] İşlem durumu -> YEŞİL")


        except Exception as e:

            print(
                "[TAKSİ HATA]",
                e
            )


            action_leds.fail()

            print("[LED] İşlem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # 2. BUTON -> ÇAĞRI BAŞLAT
    # ========================================================

    def call_action():

        if not system_active:

            print("[UYARI] Sistem kapalı. Önce sistemi başlatın.")
            return


        if not action_lock.acquire(blocking=False):

            print("[UYARI] Başka bir işlem devam ediyor.")
            return


        try:

            print("\n=======================================================")
            print("ÇAĞRI BAŞLATILIYOR")
            print("=======================================================")


            # API isteği sürerken sarı
            action_leds.loading()

            print("[LED] İşlem durumu -> SARI")


            result = api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[ÇAĞRI] API yanıtı:",
                result
            )


            # API başarılı
            action_leds.success()

            print("[LED] İşlem durumu -> YEŞİL")


            # Daha sonra SignalR üzerinden CallRejected gelirse
            # call_rejected() çalışacak ve LED kırmızıya dönecek.


        except Exception as e:

            print(
                "[ÇAĞRI HATA]",
                e
            )


            action_leds.fail()

            print("[LED] İşlem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # 3. BUTON -> SWITCH / RÖLE
    # ========================================================

    def switch_action():

        if not system_active:

            print("[UYARI] Sistem kapalı. Önce sistemi başlatın.")
            return


        if not action_lock.acquire(blocking=False):

            print("[UYARI] Başka bir işlem devam ediyor.")
            return


        try:

            print("\n=======================================================")
            print("ANAHTAR/RÖLE DURUMU DEĞİŞTİRİLİYOR")
            print("=======================================================")


            # İşlem sırasında sarı
            action_leds.loading()

            print("[LED] İşlem durumu -> SARI")


            result = api.set_switch_status(
                switch_id=SWITCH_ID,
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[SWITCH] API yanıtı:",
                result
            )


            # Başarılı
            action_leds.success()

            print("[LED] İşlem durumu -> YEŞİL")


        except Exception as e:

            print(
                "[SWITCH HATA]",
                e
            )


            action_leds.fail()

            print("[LED] İşlem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # BUTON EVENTLERİ
    # ========================================================

    btn_taxi.when_pressed = taxi_action

    btn_call.when_pressed = call_action

    btn_switch.when_pressed = switch_action

    power_button.when_pressed = toggle_power


    # ========================================================
    # PROGRAMI AÇIK TUT
    # ========================================================

    try:

        pause()


    except KeyboardInterrupt:

        print("\n[SİSTEM] CTRL+C algılandı.")
        print("[SİSTEM] Program tamamen kapatılıyor...")


    finally:

        # SignalR
        signalr.stop_connection()


        # LED'ler
        boot_leds.close()
        action_leds.close()


        # Butonlar
        btn_taxi.close()
        btn_call.close()
        btn_switch.close()
        power_button.close()


        print("[SİSTEM] GPIO kaynakları kapatıldı.")
        print("[SİSTEM] Program sonlandırıldı.")


        sys.exit(0)


# ============================================================
# PROGRAM BAŞLANGICI
# ============================================================

if __name__ == "__main__":
    main()
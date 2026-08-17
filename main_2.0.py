import sys
import time
import threading
from signal import pause

from gpiozero import Button, LED

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService


# ============================================================
# DEVICE ID
# ============================================================

TAXI_DEVICE_ID = (
    "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
)

CALL_DEVICE_ID = (
    "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
)

SWITCH_ID = "1002533340"


# ============================================================
# LOGIN
# ============================================================

USERNAME = "samsung.canli@fsitip.com"
PASSWORD = "Aa123456."

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

        self.green.off()
        self.yellow.off()
        self.red.off()


    def loading(self):

        self.off()

        self.yellow.blink(
            on_time=0.4,
            off_time=0.4,
            background=True
        )


    def success(self):

        self.off()
        self.green.on()


    def fail(self):

        self.off()
        self.red.on()


    def close(self):

        self.off()

        self.green.close()
        self.yellow.close()
        self.red.close()


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n[SİSTEM] Program çalışıyor.")
    print("[SİSTEM] Başlatmak için ON/OFF butonuna basın.")


    # --------------------------------------------------------
    # TRAFİK LAMBASI
    # --------------------------------------------------------

    boot_leds = StatusLEDs(
        green_pin=5,
        yellow_pin=6,
        red_pin=13
    )


    # --------------------------------------------------------
    # NORMAL DURUM LEDLERİ
    # --------------------------------------------------------

    action_leds = StatusLEDs(
        green_pin=23,
        yellow_pin=24,
        red_pin=25
    )


    # --------------------------------------------------------
    # BUTONLAR
    # --------------------------------------------------------

    btn_taxi = Button(
        17,
        bounce_time=0.1
    )

    btn_call = Button(
        27,
        bounce_time=0.1
    )

    btn_switch = Button(
        22,
        bounce_time=0.1
    )

    power_button = Button(
        12,
        bounce_time=0.2
    )


    # --------------------------------------------------------
    # PROGRAM DURUMU
    # --------------------------------------------------------

    system_active = False
    system_starting = False

    api = None

    signalr = SignalRService()

    action_lock = threading.Lock()


    # ========================================================
    # MENÜ
    # ========================================================

    def show_menu():

        print("\n=======================================================")
        print("                  SİSTEM AKTİF")
        print("=======================================================")

        print(
            "1. Buton -> Taksi Çağır"
        )

        print(
            "2. Buton -> Çağrı Başlat"
        )

        print(
            "3. Buton -> Anahtar/Röle Durumu Değiştir"
        )

        print(
            "ON/OFF Butonu -> Sistemi Kapat"
        )

        print("=======================================================\n")


    # ========================================================
    # CALL REJECTED
    # ========================================================

    def call_rejected():

        if not system_active:
            return

        print(
            "[LED] Çağrı reddedildi -> KIRMIZI"
        )

        action_leds.fail()


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

        if system_active or system_starting:
            return

        system_starting = True

        print("\n[SİSTEM] Başlatılıyor...")


        # Bağlantı kurulurken trafik lambası sarı
        boot_leds.loading()

        # Normal LED'leri temizle
        action_leds.off()


        try:

            # API session
            session = create_api_session()

            api = APIService(
                session=session
            )


            # ----------------------------
            # LOGIN
            # ----------------------------

            print("[SİSTEM] Oturum açılıyor...")

            token = api.login(
                USERNAME,
                PASSWORD
            )

            print("[SİSTEM] Login başarılı.")


            # ----------------------------
            # SIGNALR
            # ----------------------------

            print(
                "[SİSTEM] SignalR bağlantısı bekleniyor..."
            )

            connected = signalr.start_connection(
                token=token,
                timeout=12
            )


            if not connected:

                raise ConnectionError(
                    "SignalR bağlantısı kurulamadı."
                )


            # ----------------------------
            # SUCCESS
            # ----------------------------

            system_active = True
            system_starting = False

            print("[SİSTEM] Bağlantılar hazır.")


            # Trafik lambası yeşil
            boot_leds.success()

            time.sleep(1)


            # Menüden sonra trafik lambasını tamamen kapat
            boot_leds.off()


            show_menu()


        except Exception as e:

            system_active = False
            system_starting = False

            print(
                f"\n[SİSTEM HATA] {e}"
            )


            # Trafik lambası kırmızı
            boot_leds.fail()

            signalr.stop_connection()


    # ========================================================
    # SİSTEMİ KAPAT
    # ========================================================

    def stop_system():

        nonlocal system_active
        nonlocal system_starting

        if not system_active and not system_starting:
            return

        print("\n[SİSTEM] Kapatılıyor...")


        system_active = False
        system_starting = False


        signalr.stop_connection()


        boot_leds.off()
        action_leds.off()


        print("[SİSTEM] SİSTEM OFF")
        print(
            "[SİSTEM] Tekrar başlatmak için "
            "ON/OFF butonuna basın."
        )


    # ========================================================
    # POWER BUTTON
    # ========================================================

    def toggle_power():

        if system_active:
            stop_system()

        else:
            start_system()


    # ========================================================
    # TAKSİ
    # ========================================================

    def taxi_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı."
            )

            return


        # Aynı anda iki API isteği gitmesini engelle
        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Başka bir işlem devam ediyor."
            )

            return


        try:

            print("\n--- TAKSİ ÇAĞRILIYOR ---")


            # Sarı yanıp söner
            action_leds.loading()


            result = api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "Taksi İsteği Yanıtı:",
                result
            )


            # Başarılı
            action_leds.success()


        except Exception as e:

            print(
                "Taksi hatası:",
                e
            )


            action_leds.fail()


        finally:

            action_lock.release()


    # ========================================================
    # ÇAĞRI
    # ========================================================

    def call_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı."
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Başka bir işlem devam ediyor."
            )

            return


        try:

            print("\n--- ÇAĞRI BAŞLATILIYOR ---")


            action_leds.loading()


            result = api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "Çağrı İsteği Yanıtı:",
                result
            )


            # API isteği başarılı
            action_leds.success()


        except Exception as e:

            print(
                "Çağrı hatası:",
                e
            )


            action_leds.fail()


        finally:

            action_lock.release()


    # ========================================================
    # SWITCH
    # ========================================================

    def switch_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı."
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Başka bir işlem devam ediyor."
            )

            return


        try:

            print(
                "\n--- ANAHTAR DURUMU DEĞİŞTİRİLİYOR ---"
            )


            action_leds.loading()


            result = api.set_switch_status(
                switch_id=SWITCH_ID,
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "Anahtar Yanıtı:",
                result
            )


            action_leds.success()


        except Exception as e:

            print(
                "Anahtar hatası:",
                e
            )


            action_leds.fail()


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

        print("\n[SİSTEM] Program sonlandırılıyor...")


    finally:

        signalr.stop_connection()

        boot_leds.close()
        action_leds.close()

        btn_taxi.close()
        btn_call.close()
        btn_switch.close()
        power_button.close()

        print("[SİSTEM] GPIO bağlantıları kapatıldı.")

        sys.exit(0)


if __name__ == "__main__":
    main()
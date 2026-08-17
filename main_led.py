import sys
import threading
import time
from signal import pause

from gpiozero import Button, LED

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService

# OLED
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas


# ============================================================
# DEVICE / SWITCH BILGILERI
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
# GPIO PINLERI
# ============================================================

# Islem butonlari
TAXI_BUTTON_PIN = 17       # Fiziksel Pin 11
CALL_BUTTON_PIN = 27       # Fiziksel Pin 13
SWITCH_BUTTON_PIN = 22     # Fiziksel Pin 15

# Sistem ON / OFF butonu
POWER_BUTTON_PIN = 12      # Fiziksel Pin 32


# ============================================================
# TRAFIK LAMBASI
# ============================================================

BOOT_GREEN_PIN = 5         # Fiziksel Pin 29
BOOT_YELLOW_PIN = 6        # Fiziksel Pin 31
BOOT_RED_PIN = 13          # Fiziksel Pin 33


# ============================================================
# AYRI DURUM LEDLERI
# ============================================================

ACTION_GREEN_PIN = 23      # Fiziksel Pin 16
ACTION_YELLOW_PIN = 24     # Fiziksel Pin 18
ACTION_RED_PIN = 25        # Fiziksel Pin 22


# ============================================================
# OLED SINIFI
# ============================================================

class OLEDDisplay:

    def __init__(self):

        # I2C -> Bus 1
        # OLED adresi -> 0x3C
        serial = i2c(
            port=1,
            address=0x3C
        )

        self.device = ssd1306(
            serial,
            width=128,
            height=64
        )

        self.lock = threading.Lock()

        self.clear()


    def show(
        self,
        line1="",
        line2="",
        line3="",
        line4=""
    ):
        """
        OLED ekrana maksimum 4 satir yazar.
        """

        with self.lock:

            with canvas(self.device) as draw:

                draw.text(
                    (0, 0),
                    str(line1),
                    fill="white"
                )

                draw.text(
                    (0, 16),
                    str(line2),
                    fill="white"
                )

                draw.text(
                    (0, 32),
                    str(line3),
                    fill="white"
                )

                draw.text(
                    (0, 48),
                    str(line4),
                    fill="white"
                )


    def clear(self):

        with self.lock:
            self.device.clear()


# ============================================================
# LED KONTROL SINIFI
# ============================================================

class StatusLEDs:

    def __init__(
        self,
        green_pin,
        yellow_pin,
        red_pin
    ):

        self.green = LED(green_pin)
        self.yellow = LED(yellow_pin)
        self.red = LED(red_pin)

        self.lock = threading.Lock()

        self.current_state = None

        self.off()


    # --------------------------------------------------------
    # Tum LED'leri sondur
    # --------------------------------------------------------

    def off(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.current_state = "off"


    # --------------------------------------------------------
    # Sari yanip sonsun
    # --------------------------------------------------------

    def loading(self):

        with self.lock:

            if self.current_state == "loading":
                return

            self.green.off()
            self.red.off()
            self.yellow.off()

            self.yellow.blink(
                on_time=0.4,
                off_time=0.4,
                background=True
            )

            self.current_state = "loading"


    # --------------------------------------------------------
    # Yesil
    # --------------------------------------------------------

    def success(self):

        with self.lock:

            if self.current_state == "success":
                return

            self.yellow.off()
            self.red.off()
            self.green.on()

            self.current_state = "success"


    # --------------------------------------------------------
    # Kirmizi
    # --------------------------------------------------------

    def fail(self):

        with self.lock:

            if self.current_state == "fail":
                return

            self.yellow.off()
            self.green.off()
            self.red.on()

            self.current_state = "fail"


    # --------------------------------------------------------
    # GPIO kaynaklarini kapat
    # --------------------------------------------------------

    def close(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.green.close()
            self.yellow.close()
            self.red.close()


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    # ========================================================
    # OLED
    # ========================================================

    oled = OLEDDisplay()


    # ========================================================
    # LED GRUPLARI
    # ========================================================

    # Trafik lambasi
    boot_leds = StatusLEDs(
        green_pin=BOOT_GREEN_PIN,
        yellow_pin=BOOT_YELLOW_PIN,
        red_pin=BOOT_RED_PIN
    )

    # Normal 3 LED
    action_leds = StatusLEDs(
        green_pin=ACTION_GREEN_PIN,
        yellow_pin=ACTION_YELLOW_PIN,
        red_pin=ACTION_RED_PIN
    )


    # ========================================================
    # PROGRAM ILK ACILDIGINDA
    # ========================================================

    boot_leds.fail()
    action_leds.off()

    oled.show(
        "QRING SISTEM",
        "",
        "SISTEM KAPALI",
        "ON tusuna basin"
    )


    print("\n=======================================================")
    print("              QRING RASPBERRY PI SISTEMI")
    print("=======================================================")
    print("[SISTEM] Program calisiyor.")
    print("[SISTEM] Sistem su anda KAPALI.")
    print("[LED] Trafik lambasi -> KIRMIZI")
    print("[SISTEM] Baslatmak icin ON/OFF butonuna basin.")
    print("=======================================================\n")


    # ========================================================
    # BUTONLAR
    # ========================================================

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


    # ========================================================
    # SISTEM DEGISKENLERI
    # ========================================================

    system_active = False
    system_starting = False

    api = None

    signalr = SignalRService()

    action_lock = threading.Lock()
    power_lock = threading.Lock()

    monitor_stop_event = threading.Event()


    # ========================================================
    # MENU
    # ========================================================

    def show_menu():

        print("\n=======================================================")
        print("                    SISTEM AKTIF")
        print("=======================================================")
        print("1. BUTON -> Taksi Cagir")
        print("2. BUTON -> Cagri Baslat")
        print("3. BUTON -> Anahtar/Role Durumu Degistir")
        print("ON/OFF    -> Sistemi Kapat")
        print("=======================================================\n")

        # OLED
        oled.show(
            "QRING SISTEM",
            "SISTEM AKTIF",
            "BAGLANTI: OK",
            "SECIM BEKLENIYOR"
        )


    # ========================================================
    # SIGNALR BAGLANTI MONITORU
    # ========================================================

    def connection_monitor():

        while not monitor_stop_event.is_set():

            if system_active:

                if signalr.connected_event.is_set():

                    # Baglanti varsa yesil
                    boot_leds.success()

                else:

                    # Baglanti gecici olarak yoksa sari
                    boot_leds.loading()

                    oled.show(
                        "QRING SISTEM",
                        "BAGLANTI KOPTU",
                        "YENIDEN",
                        "BAGLANIYOR..."
                    )

            time.sleep(0.2)


    monitor_thread = threading.Thread(
        target=connection_monitor,
        daemon=True
    )

    monitor_thread.start()


    # ========================================================
    # CALL REJECTED
    # ========================================================

    def call_rejected():

        if not system_active:
            return


        print("\n=======================================================")
        print("[CALL] CAGRI REDDEDILDI")
        print("=======================================================")

        action_leds.fail()

        print("[LED] Islem durumu -> KIRMIZI")


        oled.show(
            "CAGRI",
            "",
            "CAGRI REDDEDILDI",
            "SONUC: HATA"
        )


    signalr.set_rejection_callback(
        call_rejected
    )


    # ========================================================
    # SISTEMI BASLAT
    # ========================================================

    def start_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal api


        if system_active:

            print("[SISTEM] Sistem zaten aktif.")
            return


        if system_starting:

            print("[SISTEM] Sistem zaten baslatiliyor.")
            return


        system_starting = True


        print("\n=======================================================")
        print("[SISTEM] BASLATILIYOR")
        print("=======================================================")


        # ----------------------------------------------------
        # LOGIN
        # ----------------------------------------------------

        boot_leds.loading()
        action_leds.off()


        oled.show(
            "QRING SISTEM",
            "",
            "LOGIN",
            "YAPILIYOR..."
        )


        print("[LED] Trafik lambasi -> SARI")
        print("[SISTEM] Login istegi hazirlaniyor...")


        try:

            # =================================================
            # API SESSION
            # =================================================

            session = create_api_session()

            api = APIService(
                session=session
            )


            # =================================================
            # LOGIN
            # =================================================

            print("[SISTEM] Oturum aciliyor...")


            token = api.login(
                USERNAME,
                PASSWORD
            )


            if not token:

                raise RuntimeError(
                    "Sunucudan token alinamadi."
                )


            print("[SISTEM] Login basarili.")
            print("[SISTEM] Token basariyla alindi.")


            oled.show(
                "QRING SISTEM",
                "",
                "TOKEN ALINDI",
                "SIGNALR..."
            )


            # =================================================
            # SIGNALR
            # =================================================

            print(
                "[SISTEM] SignalR baglantisi kuruluyor..."
            )


            connected = signalr.start_connection(
                token=token,
                timeout=12
            )


            if not connected:

                raise ConnectionError(
                    "SignalR baglantisi kurulamadi."
                )


            # =================================================
            # SISTEM HAZIR
            # =================================================

            system_active = True
            system_starting = False


            boot_leds.success()


            print("\n[SISTEM] SignalR baglantisi hazir.")
            print("[SISTEM] Sistem tamamen aktif.")
            print("[LED] Trafik lambasi -> YESIL")


            oled.show(
                "QRING SISTEM",
                "SISTEM AKTIF",
                "BAGLANTI: OK",
                "SECIM BEKLENIYOR"
            )


            show_menu()


        except Exception as e:

            system_active = False
            system_starting = False


            print("\n=======================================================")
            print("[SISTEM HATA]")
            print(e)
            print("=======================================================")


            boot_leds.fail()


            oled.show(
                "QRING SISTEM",
                "",
                "BAGLANTI HATASI",
                "SISTEM KAPALI"
            )


            print("[LED] Trafik lambasi -> KIRMIZI")


            signalr.stop_connection()


    # ========================================================
    # SISTEMI KAPAT
    # ========================================================

    def stop_system():

        nonlocal system_active
        nonlocal system_starting


        print("\n=======================================================")
        print("[SISTEM] KAPATILIYOR")
        print("=======================================================")


        oled.show(
            "QRING SISTEM",
            "",
            "SISTEM",
            "KAPATILIYOR..."
        )


        system_active = False
        system_starting = False


        signalr.stop_connection()

        action_leds.off()

        boot_leds.fail()


        print("[LED] Trafik lambasi -> KIRMIZI")
        print("[SISTEM] Sistem kapali.")


        oled.show(
            "QRING SISTEM",
            "",
            "SISTEM KAPALI",
            "ON tusuna basin"
        )


    # ========================================================
    # ON/OFF BUTONU
    # ========================================================

    def toggle_power():

        if not power_lock.acquire(
            blocking=False
        ):
            return


        try:

            if system_active or system_starting:

                stop_system()

            else:

                start_system()


        finally:

            power_lock.release()


    # ========================================================
    # BUTON 1 -> TAKSI
    # ========================================================

    def taxi_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapali."
            )

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                "ON tusuna basin"
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska bir islem devam ediyor."
            )

            return


        try:

            print("\n=======================================================")
            print("TAKSI CAGIRILIYOR")
            print("=======================================================")


            action_leds.loading()


            oled.show(
                "TAKSI",
                "",
                "CAGIRILIYOR...",
                "LUTFEN BEKLEYIN"
            )


            print("[LED] Islem durumu -> SARI")


            result = api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "[TAKSI] API yaniti:",
                result
            )


            action_leds.success()


            oled.show(
                "TAKSI",
                "",
                "BASARILI",
                "ISTEK GONDERILDI"
            )


            print("[LED] Islem durumu -> YESIL")


        except Exception as e:

            print(
                "[TAKSI HATA]",
                e
            )


            action_leds.fail()


            oled.show(
                "TAKSI",
                "",
                "HATA",
                "ISTEK BASARISIZ"
            )


            print("[LED] Islem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 2 -> CAGRI
    # ========================================================

    def call_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapali."
            )

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                "ON tusuna basin"
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska bir islem devam ediyor."
            )

            return


        try:

            print("\n=======================================================")
            print("CAGRI BASLATILIYOR")
            print("=======================================================")


            action_leds.loading()


            oled.show(
                "CAGRI",
                "",
                "BASLATILIYOR...",
                "LUTFEN BEKLEYIN"
            )


            print("[LED] Islem durumu -> SARI")


            result = api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[CAGRI] API yaniti:",
                result
            )


            action_leds.success()


            oled.show(
                "CAGRI",
                "",
                "BASARILI",
                "CAGRI GONDERILDI"
            )


            print("[LED] Islem durumu -> YESIL")


            # Cagri sonradan reddedilirse
            # SignalR -> call_rejected()
            # OLED ve LED kirmizi olur.


        except Exception as e:

            print(
                "[CAGRI HATA]",
                e
            )


            action_leds.fail()


            oled.show(
                "CAGRI",
                "",
                "HATA",
                "CAGRI BASARISIZ"
            )


            print("[LED] Islem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 3 -> SWITCH
    # ========================================================

    def switch_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapali."
            )

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                "ON tusuna basin"
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska bir islem devam ediyor."
            )

            return


        try:

            print("\n=======================================================")
            print("ANAHTAR/ROLE DURUMU DEGISTIRILIYOR")
            print("=======================================================")


            action_leds.loading()


            oled.show(
                "SWITCH",
                "",
                "ISTEK",
                "GONDERILIYOR..."
            )


            print("[LED] Islem durumu -> SARI")


            result = api.set_switch_status(
                switch_id=SWITCH_ID,
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[SWITCH] API yaniti:",
                result
            )


            action_leds.success()


            oled.show(
                "SWITCH",
                "",
                "BASARILI",
                "DURUM DEGISTI"
            )


            print("[LED] Islem durumu -> YESIL")


        except Exception as e:

            print(
                "[SWITCH HATA]",
                e
            )


            action_leds.fail()


            oled.show(
                "SWITCH",
                "",
                "HATA",
                "ISTEK BASARISIZ"
            )


            print("[LED] Islem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # BUTON EVENTLERI
    # ========================================================

    btn_taxi.when_pressed = taxi_action

    btn_call.when_pressed = call_action

    btn_switch.when_pressed = switch_action

    power_button.when_pressed = toggle_power


    # ========================================================
    # PROGRAMI ACIK TUT
    # ========================================================

    try:

        pause()


    except KeyboardInterrupt:

        print("\n[SISTEM] CTRL+C algilandi.")
        print("[SISTEM] Program kapatiliyor...")


    # ========================================================
    # TEMIZLIK
    # ========================================================

    finally:

        monitor_stop_event.set()

        signalr.stop_connection()

        boot_leds.close()
        action_leds.close()

        btn_taxi.close()
        btn_call.close()
        btn_switch.close()
        power_button.close()


        oled.show(
            "QRING SISTEM",
            "",
            "PROGRAM",
            "KAPATILDI"
        )

        time.sleep(1)

        oled.clear()


        print("[SISTEM] GPIO kaynaklari kapatildi.")
        print("[SISTEM] Program sonlandirildi.")

        sys.exit(0)


# ============================================================
# PROGRAM BASLANGICI
# ============================================================

if __name__ == "__main__":
    main()
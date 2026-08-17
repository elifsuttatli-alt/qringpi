import sys
import threading
import time
from signal import pause

from gpiozero import Button, LED

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService


# ============================================================
# DEVICE / SWITCH BİLGİLERİ
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
# GPIO PINLERİ
# ============================================================

# ------------------------------------------------------------
# İşlem butonları
# ------------------------------------------------------------

TAXI_BUTTON_PIN = 17       # Fiziksel Pin 11
CALL_BUTTON_PIN = 27       # Fiziksel Pin 13
SWITCH_BUTTON_PIN = 22     # Fiziksel Pin 15


# ------------------------------------------------------------
# Sistem ON / OFF butonu
# ------------------------------------------------------------

POWER_BUTTON_PIN = 12      # Fiziksel Pin 32


# ------------------------------------------------------------
# Trafik lambası
# ------------------------------------------------------------

BOOT_GREEN_PIN = 5         # Fiziksel Pin 29
BOOT_YELLOW_PIN = 6        # Fiziksel Pin 31
BOOT_RED_PIN = 13          # Fiziksel Pin 33


# ------------------------------------------------------------
# Ayrı durum LED'leri
# ------------------------------------------------------------

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

        self.lock = threading.Lock()

        self.current_state = None

        self.off()


    # --------------------------------------------------------
    # Bütün LED'leri kapat
    # --------------------------------------------------------

    def off(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.current_state = "off"


    # --------------------------------------------------------
    # Sarı yanıp sön
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
    # Yeşil sürekli yan
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
    # Kırmızı sürekli yan
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
    # GPIO kaynaklarını kapat
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
    # LED GRUPLARI
    # ========================================================

    # Trafik lambası
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
    # PROGRAM İLK AÇILDIĞINDA
    # ========================================================

    # Sistem henüz aktif değil
    # Trafik lambası KIRMIZI
    boot_leds.fail()

    # İşlem LED'leri kapalı
    action_leds.off()


    print("\n=======================================================")
    print("              QRING RASPBERRY PI SİSTEMİ")
    print("=======================================================")
    print("[SİSTEM] Program çalışıyor.")
    print("[SİSTEM] Sistem şu anda KAPALI.")
    print("[LED] Trafik lambası -> KIRMIZI")
    print("[SİSTEM] Başlatmak için ON/OFF butonuna basın.")
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
    # SİSTEM DEĞİŞKENLERİ
    # ========================================================

    system_active = False
    system_starting = False

    api = None

    signalr = SignalRService()


    # Aynı anda iki işlem çalışmasın
    action_lock = threading.Lock()

    # ON/OFF işlemleri üst üste binmesin
    power_lock = threading.Lock()


    # Monitor thread'ini kapatmak için
    monitor_stop_event = threading.Event()


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

        print("=======================================================")
        print("[LED] Trafik lambası YEŞİL yanmaya devam ediyor.")
        print("=======================================================\n")


    # ========================================================
    # SIGNALR BAĞLANTI MONİTÖRÜ
    # ========================================================

    def connection_monitor():

        """
        SignalR bağlantısını sürekli kontrol eder.

        Bağlantı varsa:
            YEŞİL

        Bağlantı geçici olarak kopmuşsa:
            SARI yanıp söner

        Sistem kapalıysa:
            KIRMIZI
        """

        while not monitor_stop_event.is_set():

            if system_active:

                if signalr.connected_event.is_set():

                    # SignalR bağlantısı VAR
                    boot_leds.success()

                else:

                    # Sistem aktif ama SignalR geçici olarak yok
                    # Otomatik reconnect bekleniyor
                    boot_leds.loading()

            time.sleep(0.2)


    # Monitor thread
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
        print("[CALL] ÇAĞRI REDDEDİLDİ")
        print("=======================================================")

        # Ayrı işlem LED'lerini kırmızı yap
        action_leds.fail()

        print("[LED] İşlem durumu -> KIRMIZI")


    # SignalR'dan CallRejected gelince bunu çalıştır
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


        if system_active:

            print("[SİSTEM] Sistem zaten aktif.")
            return


        if system_starting:

            print("[SİSTEM] Sistem zaten başlatılıyor.")
            return


        system_starting = True


        print("\n=======================================================")
        print("[SİSTEM] BAŞLATILIYOR")
        print("=======================================================")


        # ----------------------------------------------------
        # BAĞLANTI KURULUYOR
        # ----------------------------------------------------

        boot_leds.loading()

        action_leds.off()


        print("[LED] Trafik lambası -> SARI")
        print("[SİSTEM] Login isteği hazırlanıyor...")


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

            print("[SİSTEM] Oturum açılıyor...")


            token = api.login(
                USERNAME,
                PASSWORD
            )


            # Token gerçekten geldi mi?
            if not token:

                raise RuntimeError(
                    "Sunucudan token alınamadı."
                )


            print("[SİSTEM] Login başarılı.")
            print("[SİSTEM] Token başarıyla alındı.")


            # Token geldi ama SignalR henüz bağlanmadı
            # Bu nedenle SARI devam ediyor.
            boot_leds.loading()


            # =================================================
            # SIGNALR
            # =================================================

            print("[SİSTEM] SignalR bağlantısı kuruluyor...")


            connected = signalr.start_connection(
                token=token,
                timeout=12
            )


            if not connected:

                raise ConnectionError(
                    "SignalR bağlantısı kurulamadı."
                )


            # =================================================
            # BAĞLANTI TAMAM
            # =================================================

            system_active = True
            system_starting = False


            # SignalR bağlı -> YEŞİL
            boot_leds.success()


            print("\n[SİSTEM] SignalR bağlantısı hazır.")
            print("[SİSTEM] Sistem tamamen aktif.")
            print("[LED] Trafik lambası -> YEŞİL")


            # ------------------------------------------------
            # ÖNEMLİ:
            # BURADA boot_leds.off() YOK.
            #
            # Menü geldiğinde yeşil SÖNMEYECEK.
            # ------------------------------------------------

            show_menu()


        except Exception as e:

            system_active = False
            system_starting = False


            print("\n=======================================================")
            print("[SİSTEM HATA]")
            print(e)
            print("=======================================================")


            # Bağlantı başarısız
            boot_leds.fail()


            print("[LED] Trafik lambası -> KIRMIZI")


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


        # Önce sistem durumunu kapat
        system_active = False
        system_starting = False


        # SignalR bağlantısını kapat
        signalr.stop_connection()


        # İşlem LED'lerini söndür
        action_leds.off()


        # Sistem OFF -> KIRMIZI
        boot_leds.fail()


        print("[LED] Trafik lambası -> KIRMIZI")
        print("[SİSTEM] Sistem kapalı.")

        print(
            "[SİSTEM] Tekrar başlatmak için "
            "ON/OFF butonuna basın.\n"
        )


    # ========================================================
    # ON / OFF BUTONU
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
    # BUTON 1 -> TAKSİ ÇAĞIR
    # ========================================================

    def taxi_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı. "
                "Önce ON/OFF butonuna basın."
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

            print("\n=======================================================")
            print("TAKSİ ÇAĞRILIYOR")
            print("=======================================================")


            # İşlem başladı -> SARI
            action_leds.loading()

            print("[LED] İşlem durumu -> SARI")


            result = api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "[TAKSİ] API yanıtı:",
                result
            )


            # Başarılı -> YEŞİL
            action_leds.success()

            print("[LED] İşlem durumu -> YEŞİL")


        except Exception as e:

            print(
                "[TAKSİ HATA]",
                e
            )


            # Hata -> KIRMIZI
            action_leds.fail()

            print("[LED] İşlem durumu -> KIRMIZI")


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 2 -> ÇAĞRI BAŞLAT
    # ========================================================

    def call_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı. "
                "Önce ON/OFF butonuna basın."
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

            print("\n=======================================================")
            print("ÇAĞRI BAŞLATILIYOR")
            print("=======================================================")


            # API isteği devam ediyor -> SARI
            action_leds.loading()

            print("[LED] İşlem durumu -> SARI")


            result = api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[ÇAĞRI] API yanıtı:",
                result
            )


            # API başarılı -> YEŞİL
            action_leds.success()

            print("[LED] İşlem durumu -> YEŞİL")


            # Eğer çağrı sonradan reddedilirse
            # SignalR -> call_rejected()
            # çalışır ve LED KIRMIZI olur.


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
    # BUTON 3 -> SWITCH
    # ========================================================

    def switch_action():

        if not system_active:

            print(
                "[UYARI] Sistem kapalı. "
                "Önce ON/OFF butonuna basın."
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

            print("\n=======================================================")
            print("ANAHTAR/RÖLE DURUMU DEĞİŞTİRİLİYOR")
            print("=======================================================")


            # İşlem başladı -> SARI
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


            # Başarılı -> YEŞİL
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
    # PROGRAMI ÇALIŞIR DURUMDA TUT
    # ========================================================

    try:

        pause()


    # ========================================================
    # CTRL + C
    # ========================================================

    except KeyboardInterrupt:

        print("\n[SİSTEM] CTRL+C algılandı.")
        print("[SİSTEM] Program tamamen kapatılıyor...")


    # ========================================================
    # TEMİZLE
    # ========================================================

    finally:

        # Monitor thread'e durmasını söyle
        monitor_stop_event.set()


        # SignalR'ı kapat
        signalr.stop_connection()


        # LED GPIO'larını bırak
        boot_leds.close()
        action_leds.close()


        # Buton GPIO'larını bırak
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
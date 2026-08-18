import sys
import threading
import time
from signal import pause

from gpiozero import (
    Button,
    LED,
    DigitalOutputDevice,
    DigitalInputDevice
)

from interceptor import create_api_session
from api_service import APIService
from signalr_service import SignalRService

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas


# ============================================================
# LOGIN
# ============================================================

USERNAME = "samsung.canli@fsitip.com"
PASSWORD = "Aa123456."


# ============================================================
# DEVICE ID'LER
# ============================================================

# 1. fiziksel buton -> Taksi
TAXI_DEVICE_ID = (
    "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
)

# 2. fiziksel buton -> normal CallStart
CALL_DEVICE_ID = (
    "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
)

# Keypad ile blok / daire araması
RESIDENCE_CALL_DEVICE_ID = (
    "289AF5D65ABDC9FFB2FE7DBE1AA66A9D5A2C8D5C5ACF269E87D701CB868E1723"
)

# Residence cihaz numarası
RESIDENCE_DEVICE_ID = 102025

SWITCH_ID = "1002533340"


# ============================================================
# FIZIKSEL BUTON GPIO'LARI
# ============================================================

TAXI_BUTTON_PIN = 17       # Fiziksel Pin 11
CALL_BUTTON_PIN = 27       # Fiziksel Pin 13
SWITCH_BUTTON_PIN = 22     # Fiziksel Pin 15

POWER_BUTTON_PIN = 12      # Fiziksel Pin 32


# ============================================================
# TRAFIK LAMBASI
# ============================================================

BOOT_GREEN_PIN = 5         # Fiziksel Pin 29
BOOT_YELLOW_PIN = 6        # Fiziksel Pin 31
BOOT_RED_PIN = 13          # Fiziksel Pin 33


# ============================================================
# AYRI DURUM LED'LERI
# ============================================================

ACTION_GREEN_PIN = 23      # Fiziksel Pin 16
ACTION_YELLOW_PIN = 24     # Fiziksel Pin 18
ACTION_RED_PIN = 25        # Fiziksel Pin 22


# ============================================================
# 4x4 KEYPAD GPIO
# ============================================================

ROWS = [4, 7, 8, 9]
COLS = [10, 11, 18, 19]

KEYS = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]


# ============================================================
# OLED
# ============================================================

class OLEDDisplay:

    def __init__(self):

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
# LED KONTROL
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


    def off(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.current_state = "off"


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


    def success(self):

        with self.lock:

            if self.current_state == "success":
                return

            self.yellow.off()
            self.red.off()
            self.green.on()

            self.current_state = "success"


    def fail(self):

        with self.lock:

            if self.current_state == "fail":
                return

            self.yellow.off()
            self.green.off()
            self.red.on()

            self.current_state = "fail"


    def close(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.green.close()
            self.yellow.close()
            self.red.close()


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # OLED
    # ========================================================

    oled = OLEDDisplay()


    # ========================================================
    # LED GRUPLARI
    # ========================================================

    boot_leds = StatusLEDs(
        BOOT_GREEN_PIN,
        BOOT_YELLOW_PIN,
        BOOT_RED_PIN
    )

    action_leds = StatusLEDs(
        ACTION_GREEN_PIN,
        ACTION_YELLOW_PIN,
        ACTION_RED_PIN
    )


    # ========================================================
    # KEYPAD GPIO
    # ========================================================

    keypad_rows = [
        DigitalOutputDevice(
            pin,
            initial_value=True
        )
        for pin in ROWS
    ]

    keypad_cols = [
        DigitalInputDevice(
            pin,
            pull_up=True
        )
        for pin in COLS
    ]


    # ========================================================
    # FIZIKSEL BUTONLAR
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

    stop_event = threading.Event()


    # ========================================================
    # KEYPAD DURUMU
    # ========================================================

    selected_block = None
    apartment_list = []
    apartment_input = ""

    blocks_cache = []

    keypad_state_lock = threading.Lock()


    # ========================================================
    # BASLANGIC DURUMU
    # ========================================================

    boot_leds.fail()
    action_leds.off()

    oled.show(
        "QRING SISTEM",
        "",
        "SISTEM KAPALI",
        "ON TUSUNA BASIN"
    )


    print("\n=======================================================")
    print("              QRING RASPBERRY PI SISTEMI")
    print("=======================================================")
    print("[SISTEM] Program calisiyor.")
    print("[SISTEM] Sistem KAPALI.")
    print("[LED] Trafik lambasi -> KIRMIZI")
    print("ON/OFF butonuna basarak sistemi baslatin.")
    print("=======================================================\n")


    # ========================================================
    # OLED ANA EKRAN
    # ========================================================

    def show_home():

        oled.show(
            "QRING SISTEM",
            "SISTEM AKTIF",
            "BLOK: A B C D",
            "SECIM YAPIN"
        )


    # ========================================================
    # TERMINAL MENU
    # ========================================================

    def show_menu():

        print("\n=======================================================")
        print("                    SISTEM AKTIF")
        print("=======================================================")
        print("BUTON 1 -> Taksi Cagir")
        print("BUTON 2 -> Cagri Baslat")
        print("BUTON 3 -> Anahtar/Role")
        print("")
        print("KEYPAD:")
        print("A/B/C/D -> Blok sec")
        print("0-9     -> Daire numarasi")
        print("#       -> Ara")
        print("*       -> Temizle / Geri")
        print("")
        print("ON/OFF -> Sistemi Kapat")
        print("=======================================================\n")


    # ========================================================
    # KEYPAD DURUMUNU SIFIRLA
    # ========================================================

    def reset_keypad_state():

        nonlocal selected_block
        nonlocal apartment_list
        nonlocal apartment_input

        with keypad_state_lock:

            selected_block = None
            apartment_list = []
            apartment_input = ""


    # ========================================================
    # BLOCK BUL
    # ========================================================

    def find_block(blocks, letter):

        target = f"{letter} Blok".casefold()

        for block in blocks:

            name = block.get(
                "blockName",
                ""
            ).casefold()

            if name == target:
                return block

        return None


    # ========================================================
    # DAIRE BUL
    # ========================================================

    def find_apartment(
        apartments,
        entered_number
    ):

        # ----------------------------------------------------
        # Once apartmentNo alanina bak
        # Ornek:
        #
        # Yonetici -> apartmentNo = 1
        # ----------------------------------------------------

        for apartment in apartments:

            apartment_no = apartment.get(
                "apartmentNo"
            )

            if apartment_no is not None:

                if str(apartment_no) == entered_number:
                    return apartment


        # ----------------------------------------------------
        # apartmentNo yoksa apartmentName kullan
        #
        # Daire 2
        # Daire 3
        # Daire 4
        # ----------------------------------------------------

        target = (
            f"Daire {entered_number}"
            .casefold()
        )


        for apartment in apartments:

            name = apartment.get(
                "apartmentName",
                ""
            ).casefold()

            if name == target:
                return apartment


        return None


    # ========================================================
    # KEYPAD OKUMA
    # ========================================================

    def read_key():

        for row_index, row in enumerate(
            keypad_rows
        ):

            row.off()

            time.sleep(0.002)


            for col_index, col in enumerate(
                keypad_cols
            ):

                if col.is_active:

                    key = KEYS[
                        row_index
                    ][
                        col_index
                    ]


                    # Tus birakilana kadar bekle
                    while (
                        col.is_active
                        and not stop_event.is_set()
                    ):

                        time.sleep(0.02)


                    row.on()

                    time.sleep(0.05)

                    return key


            row.on()


        return None


    # ========================================================
    # CALL REJECTED
    # ========================================================

    def call_rejected():

        if not system_active:
            return


        print("\n=======================================================")
        print("CAGRI REDDEDILDI")
        print("=======================================================")


        action_leds.fail()


        oled.show(
            "CAGRI",
            "",
            "CAGRI REDDEDILDI",
            "SONUC: HATA"
        )


        print(
            "[LED] Islem durumu -> KIRMIZI"
        )


    signalr.set_rejection_callback(
        call_rejected
    )


    # ========================================================
    # SIGNALR BAGLANTI MONITORU
    # ========================================================

    def connection_monitor():

        previous_connected = None


        while not stop_event.is_set():

            if not system_active:

                previous_connected = None

                time.sleep(0.2)

                continue


            connected = (
                signalr.connected_event.is_set()
            )


            # Sadece durum DEGISTIGINDE ekran/LED degistir
            if connected != previous_connected:

                if connected:

                    boot_leds.success()

                    print(
                        "[SIGNALR] Baglanti aktif."
                    )


                    # Eger kopup geri geldiyse
                    if previous_connected is False:

                        oled.show(
                            "QRING SISTEM",
                            "BAGLANTI",
                            "YENIDEN KURULDU",
                            ""
                        )

                        time.sleep(1)

                        show_home()


                else:

                    boot_leds.loading()

                    print(
                        "[SIGNALR] Baglanti koptu."
                    )

                    oled.show(
                        "QRING SISTEM",
                        "BAGLANTI KOPTU",
                        "",
                        "YENIDEN BAGLANIYOR"
                    )


                previous_connected = connected


            time.sleep(0.2)


    # ========================================================
    # SISTEMI BASLAT
    # ========================================================

    def start_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal api
        nonlocal blocks_cache


        if system_active:

            print(
                "[SISTEM] Sistem zaten aktif."
            )

            return


        if system_starting:

            print(
                "[SISTEM] Sistem zaten baslatiliyor."
            )

            return


        system_starting = True

        reset_keypad_state()


        print("\n=======================================================")
        print("[SISTEM] BASLATILIYOR")
        print("=======================================================")


        # Baglanti kurulurken SARI
        boot_leds.loading()

        action_leds.off()


        oled.show(
            "QRING SISTEM",
            "",
            "LOGIN",
            "YAPILIYOR..."
        )


        print(
            "[LED] Trafik lambasi -> SARI"
        )


        try:

            # =================================================
            # SESSION
            # =================================================

            session = create_api_session()

            api = APIService(
                session=session
            )


            # =================================================
            # LOGIN
            # =================================================

            print(
                "[SISTEM] Oturum aciliyor..."
            )


            token = api.login(
                USERNAME,
                PASSWORD
            )


            if not token:

                raise RuntimeError(
                    "Token alinamadi."
                )


            print(
                "[SISTEM] Login basarili."
            )

            print(
                "[SISTEM] Token alindi."
            )


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
            # SISTEM AKTIF
            # =================================================

            system_active = True
            system_starting = False


            boot_leds.success()


            print(
                "[SISTEM] Sistem AKTIF."
            )

            print(
                "[LED] Trafik lambasi -> YESIL"
            )


            # Blok cache temiz baslasin
            blocks_cache = []


            show_menu()
            show_home()


        except Exception as e:

            system_active = False
            system_starting = False


            print(
                f"[SISTEM HATA] {e}"
            )


            boot_leds.fail()


            oled.show(
                "QRING SISTEM",
                "",
                "BAGLANTI HATASI",
                "SISTEM KAPALI"
            )


            signalr.stop_connection()


    # ========================================================
    # SISTEMI KAPAT
    # ========================================================

    def stop_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal blocks_cache


        print("\n=======================================================")
        print("[SISTEM] KAPATILIYOR")
        print("=======================================================")


        system_active = False
        system_starting = False

        blocks_cache = []

        reset_keypad_state()


        signalr.stop_connection()


        action_leds.off()
        boot_leds.fail()


        oled.show(
            "QRING SISTEM",
            "",
            "SISTEM KAPALI",
            "ON TUSUNA BASIN"
        )


        print(
            "[LED] Trafik lambasi -> KIRMIZI"
        )

        print(
            "[SISTEM] Sistem kapali."
        )


    # ========================================================
    # POWER BUTTON
    # ========================================================

    def toggle_power():

        if not power_lock.acquire(
            blocking=False
        ):

            return


        try:

            if (
                system_active
                or system_starting
            ):

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

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                ""
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska islem devam ediyor."
            )

            return


        try:

            print(
                "\nTAKSI CAGIRILIYOR..."
            )


            action_leds.loading()


            oled.show(
                "TAKSI",
                "",
                "CAGIRILIYOR...",
                ""
            )


            result = api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "[TAKSI] Yanit:",
                result
            )


            action_leds.success()


            oled.show(
                "TAKSI",
                "",
                "BASARILI",
                "ISTEK GONDERILDI"
            )


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


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 2 -> NORMAL CAGRI
    # ========================================================

    def call_action():

        if not system_active:

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                ""
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska islem devam ediyor."
            )

            return


        try:

            print(
                "\nCAGRI BASLATILIYOR..."
            )


            action_leds.loading()


            oled.show(
                "CAGRI",
                "",
                "BASLATILIYOR...",
                ""
            )


            result = api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[CAGRI] Yanit:",
                result
            )


            action_leds.success()


            oled.show(
                "CAGRI",
                "",
                "CAGRI GONDERILDI",
                ""
            )


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


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 3 -> SWITCH
    # ========================================================

    def switch_action():

        if not system_active:

            oled.show(
                "UYARI",
                "",
                "SISTEM KAPALI",
                ""
            )

            return


        if not action_lock.acquire(
            blocking=False
        ):

            print(
                "[UYARI] Baska islem devam ediyor."
            )

            return


        try:

            print(
                "\nSWITCH ISTEGI..."
            )


            action_leds.loading()


            oled.show(
                "SWITCH",
                "",
                "ISTEK",
                "GONDERILIYOR"
            )


            result = api.set_switch_status(
                switch_id=SWITCH_ID,
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[SWITCH] Yanit:",
                result
            )


            action_leds.success()


            oled.show(
                "SWITCH",
                "",
                "BASARILI",
                ""
            )


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
                ""
            )


        finally:

            action_lock.release()


    # ========================================================
    # KEYPAD TUS ISLEME
    # ========================================================

    def process_key(key):

        nonlocal selected_block
        nonlocal apartment_list
        nonlocal apartment_input
        nonlocal blocks_cache


        if not system_active:
            return


        print(
            "[KEYPAD] Tus:",
            key
        )


        # ====================================================
        # BLOK SECIMI
        # ====================================================

        if selected_block is None:

            if key not in [
                "A",
                "B",
                "C",
                "D"
            ]:

                oled.show(
                    "BLOK SECIN",
                    "",
                    "A  B  C  D",
                    ""
                )

                return


            # -----------------------------------------------
            # API'den bloklari al
            # -----------------------------------------------

            if not action_lock.acquire(
                blocking=False
            ):

                oled.show(
                    "UYARI",
                    "",
                    "BASKA ISLEM",
                    "DEVAM EDIYOR"
                )

                return


            try:

                oled.show(
                    "BLOKLAR",
                    "",
                    "YUKLENIYOR...",
                    ""
                )


                if not blocks_cache:

                    blocks_cache = (
                        api.get_block_list(
                            RESIDENCE_DEVICE_ID
                        )
                    )


                block = find_block(
                    blocks_cache,
                    key
                )


                if block is None:

                    oled.show(
                        "HATA",
                        "",
                        "BLOK BULUNAMADI",
                        key
                    )

                    return


                # Daireleri API'den al
                apartments = (
                    api.get_apartment_list(
                        block["id"]
                    )
                )


                with keypad_state_lock:

                    selected_block = block
                    apartment_list = apartments
                    apartment_input = ""


                print(
                    "[KEYPAD] Blok:",
                    block["blockName"],
                    "ID:",
                    block["id"]
                )


                oled.show(
                    block["blockName"].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )


            except Exception as e:

                print(
                    "[KEYPAD BLOK HATA]",
                    e
                )


                blocks_cache = []


                oled.show(
                    "HATA",
                    "",
                    "BLOK LISTESI",
                    "ALINAMADI"
                )


            finally:

                action_lock.release()


            return


        # ====================================================
        # * -> TEMIZLE / GERI
        # ====================================================

        if key == "*":

            # Numara yazilmissa sadece numarayi temizle
            if apartment_input:

                apartment_input = ""


                oled.show(
                    selected_block[
                        "blockName"
                    ].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )


            # Numara yoksa blok secimine geri don
            else:

                reset_keypad_state()

                show_home()


            return


        # ====================================================
        # RAKAM GIRISI
        # ====================================================

        if key.isdigit():

            if len(apartment_input) < 3:

                apartment_input += key


            oled.show(
                selected_block[
                    "blockName"
                ].upper(),
                "",
                "DAIRE NO:",
                apartment_input
            )


            return


        # ====================================================
        # # -> CAGRIYI BASLAT
        # ====================================================

        if key == "#":

            if apartment_input == "":

                oled.show(
                    "HATA",
                    "",
                    "DAIRE NO GIRIN",
                    ""
                )

                return


            apartment = find_apartment(
                apartment_list,
                apartment_input
            )


            if apartment is None:

                oled.show(
                    selected_block[
                        "blockName"
                    ].upper(),
                    "",
                    "DAIRE YOK:",
                    apartment_input
                )


                print(
                    "[KEYPAD] Daire bulunamadi:",
                    apartment_input
                )


                apartment_input = ""

                return


            # -----------------------------------------------
            # CAGRI
            # -----------------------------------------------

            if not action_lock.acquire(
                blocking=False
            ):

                oled.show(
                    "UYARI",
                    "",
                    "BASKA ISLEM",
                    "DEVAM EDIYOR"
                )

                return


            try:

                block_id = (
                    selected_block["id"]
                )

                apartment_id = (
                    apartment["id"]
                )

                apartment_name = (
                    apartment.get(
                        "apartmentName",
                        apartment_input
                    )
                )


                print(
                    "\n==================================="
                )

                print(
                    "KEYPAD CAGRI BASLATILIYOR"
                )

                print(
                    "Blok:",
                    selected_block[
                        "blockName"
                    ]
                )

                print(
                    "blockId:",
                    block_id
                )

                print(
                    "Daire:",
                    apartment_name
                )

                print(
                    "apartmentId:",
                    apartment_id
                )

                print(
                    "==================================="
                )


                # Islem LED'i SARI
                action_leds.loading()


                oled.show(
                    selected_block[
                        "blockName"
                    ].upper(),
                    apartment_name.upper(),
                    "",
                    "ARANIYOR..."
                )


                result = api.start_call(
                    device_unique_id=(
                        RESIDENCE_CALL_DEVICE_ID
                    ),
                    guest_name="Keypad",
                    block_id=block_id,
                    apartment_id=apartment_id,
                    apartment_no="undefined"
                )


                print(
                    "[KEYPAD CALL] Yanit:",
                    result
                )


                # Basarili -> YESIL
                action_leds.success()


                oled.show(
                    selected_block[
                        "blockName"
                    ].upper(),
                    apartment_name.upper(),
                    "",
                    "CAGRI GONDERILDI"
                )


                # Yeni cagri icin state sifirla.
                # OLED sonuc ekrani olarak kalir.
                reset_keypad_state()


            except Exception as e:

                print(
                    "[KEYPAD CALL HATA]",
                    e
                )


                action_leds.fail()


                oled.show(
                    "CAGRI",
                    "",
                    "HATA",
                    "ISTEK BASARISIZ"
                )


                reset_keypad_state()


            finally:

                action_lock.release()


            return


    # ========================================================
    # KEYPAD THREAD
    # ========================================================

    def keypad_loop():

        while not stop_event.is_set():

            if not system_active:

                time.sleep(0.1)

                continue


            key = read_key()


            if key is not None:

                try:

                    process_key(
                        key
                    )

                except Exception as e:

                    print(
                        "[KEYPAD HATA]",
                        e
                    )


            else:

                time.sleep(0.01)


    # ========================================================
    # THREADLER
    # ========================================================

    monitor_thread = threading.Thread(
        target=connection_monitor,
        daemon=True
    )

    monitor_thread.start()


    keypad_thread = threading.Thread(
        target=keypad_loop,
        daemon=True
    )

    keypad_thread.start()


    # ========================================================
    # FIZIKSEL BUTON EVENTLERI
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

        print(
            "\n[SISTEM] CTRL+C algilandi."
        )


    # ========================================================
    # TEMIZLIK
    # ========================================================

    finally:

        stop_event.set()


        signalr.stop_connection()


        boot_leds.close()
        action_leds.close()


        btn_taxi.close()
        btn_call.close()
        btn_switch.close()
        power_button.close()


        for row in keypad_rows:
            row.close()


        for col in keypad_cols:
            col.close()


        oled.show(
            "QRING SISTEM",
            "",
            "PROGRAM",
            "KAPATILDI"
        )


        time.sleep(1)


        oled.clear()


        print(
            "[SISTEM] Program sonlandirildi."
        )


        sys.exit(0)


# ============================================================
# BASLANGIC
# ============================================================

if __name__ == "__main__":
    main()
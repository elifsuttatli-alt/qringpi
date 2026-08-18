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

TAXI_DEVICE_ID = (
    "4F5ADCB3E377A2B06409DC96D96B45CC6FFFCE8A137C9CDC50460F1CF233C1FA"
)

CALL_DEVICE_ID = (
    "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
)

RESIDENCE_CALL_DEVICE_ID = (
    "289AF5D65ABDC9FFB2FE7DBE1AA66A9D5A2C8D5C5ACF269E87D701CB868E1723"
)

RESIDENCE_DEVICE_ID = 102025

SWITCH_ID = "1002533340"


# ============================================================
# FIZIKSEL BUTONLAR
# ============================================================

TAXI_BUTTON_PIN = 17          # Fiziksel Pin 11
CALL_BUTTON_PIN = 27          # Fiziksel Pin 13
SWITCH_BUTTON_PIN = 22        # Fiziksel Pin 15
RESIDENCE_BUTTON_PIN = 16     # Fiziksel Pin 36

POWER_BUTTON_PIN = 12         # Fiziksel Pin 32


# ============================================================
# TRAFIK LAMBASI
# ============================================================

BOOT_GREEN_PIN = 5
BOOT_YELLOW_PIN = 6
BOOT_RED_PIN = 13


# ============================================================
# AYRI DURUM LEDLERI
# ============================================================

ACTION_GREEN_PIN = 23
ACTION_YELLOW_PIN = 24
ACTION_RED_PIN = 25


# ============================================================
# 4x4 KEYPAD
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

                draw.text((0, 0), str(line1), fill="white")
                draw.text((0, 16), str(line2), fill="white")
                draw.text((0, 32), str(line3), fill="white")
                draw.text((0, 48), str(line4), fill="white")


    def clear(self):

        with self.lock:
            self.device.clear()


# ============================================================
# LED KONTROL
# ============================================================

class StatusLEDs:

    def __init__(self, green_pin, yellow_pin, red_pin):

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
    # LEDLER
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
    # KEYPAD
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

    btn_residence = Button(
        RESIDENCE_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.1
    )

    power_button = Button(
        POWER_BUTTON_PIN,
        pull_up=True,
        bounce_time=0.2
    )


    # ========================================================
    # SISTEM DURUMU
    # ========================================================

    system_active = False
    system_starting = False

    residence_mode = False

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


    # ========================================================
    # ANA MENU
    # ========================================================

    def show_home():

        oled.show(
            "1: TAKSI",
            "2: CAGRI",
            "3: SWITCH",
            "4: APARTMAN"
        )


    # ========================================================
    # APARTMAN BLOK SECIM EKRANI
    # ========================================================

    def show_block_selection():

        oled.show(
            "APARTMAN CAGRI",
            "BLOK SECIN",
            "",
            "A   B   C   D"
        )


    # ========================================================
    # KEYPAD DURUMUNU SIFIRLA
    # ========================================================

    def reset_keypad_state():

        nonlocal selected_block
        nonlocal apartment_list
        nonlocal apartment_input

        selected_block = None
        apartment_list = []
        apartment_input = ""


    # ========================================================
    # BLOK BUL
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

    def find_apartment(apartments, entered_number):

        # Önce apartmentNo alanına bak.
        # Örneğin Yönetici -> apartmentNo = 1

        for apartment in apartments:

            apartment_no = apartment.get(
                "apartmentNo"
            )

            if apartment_no is not None:

                if str(apartment_no) == entered_number:
                    return apartment


        # apartmentNo boşsa "Daire X" adına bak.

        target = f"Daire {entered_number}".casefold()

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

        for row_index, row in enumerate(keypad_rows):

            row.off()

            time.sleep(0.002)

            for col_index, col in enumerate(keypad_cols):

                if col.is_active:

                    key = KEYS[row_index][col_index]

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

        print("\n======================================")
        print("CAGRI REDDEDILDI")
        print("======================================")

        action_leds.fail()

        oled.show(
            "CAGRI",
            "",
            "REDDEDILDI",
            ""
        )


    signalr.set_rejection_callback(
        call_rejected
    )


    # ========================================================
    # SIGNALR MONITOR
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


            if connected != previous_connected:

                if connected:

                    boot_leds.success()

                    print(
                        "[SIGNALR] Baglanti aktif."
                    )

                    # Bağlantı koptu ve tekrar geldiyse
                    if previous_connected is False:

                        oled.show(
                            "QRING SISTEM",
                            "",
                            "BAGLANTI",
                            "GERI GELDI"
                        )

                        time.sleep(1)

                        if residence_mode:
                            show_block_selection()
                        else:
                            show_home()


                else:

                    boot_leds.loading()

                    print(
                        "[SIGNALR] Baglanti koptu."
                    )

                    oled.show(
                        "QRING SISTEM",
                        "",
                        "BAGLANTI KOPTU",
                        "BEKLEYIN..."
                    )


                previous_connected = connected


            time.sleep(0.2)


    # ========================================================
    # SISTEM BASLAT
    # ========================================================

    def start_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal api
        nonlocal residence_mode
        nonlocal blocks_cache


        if system_active:
            return

        if system_starting:
            return


        system_starting = True

        residence_mode = False

        reset_keypad_state()


        print("\n======================================")
        print("SISTEM BASLATILIYOR")
        print("======================================")


        boot_leds.loading()
        action_leds.off()


        oled.show(
            "QRING SISTEM",
            "",
            "LOGIN",
            "YAPILIYOR..."
        )


        try:

            # -----------------------------------------------
            # SESSION
            # -----------------------------------------------

            session = create_api_session()

            api = APIService(
                session=session
            )


            # -----------------------------------------------
            # LOGIN
            # -----------------------------------------------

            print("[SISTEM] Login yapiliyor...")


            token = api.login(
                USERNAME,
                PASSWORD
            )


            if not token:

                raise RuntimeError(
                    "Token alinamadi."
                )


            print("[SISTEM] Token alindi.")


            oled.show(
                "QRING SISTEM",
                "",
                "TOKEN ALINDI",
                "SIGNALR..."
            )


            # -----------------------------------------------
            # SIGNALR
            # -----------------------------------------------

            connected = signalr.start_connection(
                token=token,
                timeout=12
            )


            if not connected:

                raise ConnectionError(
                    "SignalR baglantisi kurulamadi."
                )


            # -----------------------------------------------
            # AKTIF
            # -----------------------------------------------

            system_active = True
            system_starting = False

            residence_mode = False

            blocks_cache = []


            boot_leds.success()


            print("[SISTEM] Sistem AKTIF.")
            print("[LED] Trafik lambasi -> YESIL")


            show_home()


        except Exception as e:

            system_active = False
            system_starting = False
            residence_mode = False


            print(
                "[SISTEM HATA]",
                e
            )


            boot_leds.fail()


            oled.show(
                "QRING SISTEM",
                "",
                "HATA",
                "SISTEM KAPALI"
            )


            signalr.stop_connection()


    # ========================================================
    # SISTEM KAPAT
    # ========================================================

    def stop_system():

        nonlocal system_active
        nonlocal system_starting
        nonlocal residence_mode
        nonlocal blocks_cache


        system_active = False
        system_starting = False
        residence_mode = False

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


        print("[SISTEM] Sistem kapali.")


    # ========================================================
    # POWER
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
            return


        if not action_lock.acquire(
            blocking=False
        ):

            return


        try:

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
                "[TAKSI]",
                result
            )


            action_leds.success()


            oled.show(
                "TAKSI",
                "",
                "BASARILI",
                ""
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
                ""
            )


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 2 -> CAGRI
    # ========================================================

    def call_action():

        if not system_active:
            return


        if not action_lock.acquire(
            blocking=False
        ):

            return


        try:

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
                "[CAGRI]",
                result
            )


            action_leds.success()


            oled.show(
                "CAGRI",
                "",
                "GONDERILDI",
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
                ""
            )


        finally:

            action_lock.release()


    # ========================================================
    # BUTON 3 -> SWITCH
    # ========================================================

    def switch_action():

        if not system_active:
            return


        if not action_lock.acquire(
            blocking=False
        ):

            return


        try:

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
                "[SWITCH]",
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
    # BUTON 4 -> APARTMAN MODU
    # ========================================================

    def residence_action():

        nonlocal residence_mode


        if not system_active:
            return


        # Apartman modu kapalıysa aç
        if not residence_mode:

            residence_mode = True

            reset_keypad_state()


            print(
                "[APARTMAN] Apartman cagri modu acildi."
            )


            show_block_selection()


        # Zaten açıksa butona tekrar basınca ana menüye dön
        else:

            residence_mode = False

            reset_keypad_state()


            print(
                "[APARTMAN] Apartman cagri modu kapatildi."
            )


            show_home()


    # ========================================================
    # KEYPAD TUS ISLEME
    # ========================================================

    def process_key(key):

        nonlocal selected_block
        nonlocal apartment_list
        nonlocal apartment_input
        nonlocal blocks_cache
        nonlocal residence_mode


        if not system_active:
            return


        # Apartman modu açık değilse keypad hiçbir şey yapmasın.
        if not residence_mode:
            return


        print(
            "[KEYPAD] Tus:",
            key
        )


        # ====================================================
        # HENUZ BLOK SECILMEDI
        # ====================================================

        if selected_block is None:

            # * -> Apartman modundan çık
            if key == "*":

                residence_mode = False

                reset_keypad_state()

                show_home()

                return


            # Sadece A/B/C/D kabul et
            if key not in [
                "A",
                "B",
                "C",
                "D"
            ]:

                show_block_selection()

                return


            if not action_lock.acquire(
                blocking=False
            ):

                return


            try:

                oled.show(
                    "APARTMAN",
                    "",
                    "BLOK",
                    "YUKLENIYOR..."
                )


                if not blocks_cache:

                    blocks_cache = api.get_block_list(
                        RESIDENCE_DEVICE_ID
                    )


                block = find_block(
                    blocks_cache,
                    key
                )


                if block is None:

                    oled.show(
                        "HATA",
                        "",
                        "BLOK YOK",
                        key
                    )

                    return


                apartments = api.get_apartment_list(
                    block["id"]
                )


                selected_block = block
                apartment_list = apartments
                apartment_input = ""


                print(
                    "[KEYPAD] Blok:",
                    block["blockName"]
                )


                oled.show(
                    block["blockName"].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )


            except Exception as e:

                print(
                    "[BLOK HATA]",
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
        # * -> GERI
        # ====================================================

        if key == "*":

            # Daire numarası yazılmışsa sadece numarayı sil
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


            # Numara yoksa blok seçim ekranına dön
            else:

                selected_block = None
                apartment_list = []
                apartment_input = ""

                show_block_selection()


            return


        # ====================================================
        # SAYI
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
        # # -> ARA
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


                apartment_input = ""

                return


            if not action_lock.acquire(
                blocking=False
            ):

                return


            try:

                block_id = selected_block["id"]
                apartment_id = apartment["id"]

                apartment_name = apartment.get(
                    "apartmentName",
                    apartment_input
                )


                print()
                print("======================================")
                print("APARTMAN CAGRI")
                print(
                    "Blok:",
                    selected_block["blockName"]
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
                print("======================================")


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
                    device_unique_id=RESIDENCE_CALL_DEVICE_ID,
                    guest_name="Keypad",
                    block_id=block_id,
                    apartment_id=apartment_id,
                    apartment_no="undefined"
                )


                print(
                    "[APARTMAN CALL]",
                    result
                )


                action_leds.success()


                oled.show(
                    selected_block[
                        "blockName"
                    ].upper(),
                    apartment_name.upper(),
                    "",
                    "CAGRI GONDERILDI"
                )


                # Çağrıdan sonra apartman modunu kapat.
                residence_mode = False

                reset_keypad_state()


            except Exception as e:

                print(
                    "[APARTMAN CALL HATA]",
                    e
                )


                action_leds.fail()


                oled.show(
                    "CAGRI",
                    "",
                    "HATA",
                    "BASARISIZ"
                )


                residence_mode = False

                reset_keypad_state()


            finally:

                action_lock.release()


    # ========================================================
    # KEYPAD THREAD
    # ========================================================

    def keypad_loop():

        while not stop_event.is_set():

            # Sistem veya apartman modu kapalıysa keypad taramasını
            # yavaşlat.
            if not system_active or not residence_mode:

                time.sleep(0.1)
                continue


            key = read_key()


            if key is not None:

                try:

                    process_key(key)

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
    # BUTON EVENTLERI
    # ========================================================

    btn_taxi.when_pressed = taxi_action
    btn_call.when_pressed = call_action
    btn_switch.when_pressed = switch_action

    # Yeni 4. buton
    btn_residence.when_pressed = residence_action

    power_button.when_pressed = toggle_power


    # ========================================================
    # PROGRAM
    # ========================================================

    try:

        pause()


    except KeyboardInterrupt:

        print(
            "\n[SISTEM] Program kapatiliyor."
        )


    finally:

        stop_event.set()

        signalr.stop_connection()

        boot_leds.close()
        action_leds.close()

        btn_taxi.close()
        btn_call.close()
        btn_switch.close()
        btn_residence.close()
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

        sys.exit(0)


# ============================================================
# BASLANGIC
# ============================================================

if __name__ == "__main__":
    main()
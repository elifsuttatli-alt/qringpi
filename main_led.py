import time
import threading
import traceback

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
# DEVICE BILGILERI
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
# GPIO
# ============================================================

# Fiziksel butonlar
TAXI_BUTTON_PIN = 17
CALL_BUTTON_PIN = 27
SWITCH_BUTTON_PIN = 22
RESIDENCE_BUTTON_PIN = 16

# Sistem ON/OFF
POWER_BUTTON_PIN = 12


# Trafik lambasi
BOOT_GREEN_PIN = 5
BOOT_YELLOW_PIN = 6
BOOT_RED_PIN = 13


# Ayri durum LED'leri
ACTION_GREEN_PIN = 23
ACTION_YELLOW_PIN = 24
ACTION_RED_PIN = 25


# ============================================================
# KEYPAD
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
# OLED ICIN TURKCE KARAKTER DUZELTME
# ============================================================

def oled_safe(text):

    text = str(text)

    replacements = {
        "ç": "c",
        "Ç": "C",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "ö": "o",
        "Ö": "O",
        "ş": "s",
        "Ş": "S",
        "ü": "u",
        "Ü": "U"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # OLED satirina sigmasi icin
    return text[:21]


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
                    oled_safe(line1),
                    fill="white"
                )

                draw.text(
                    (0, 16),
                    oled_safe(line2),
                    fill="white"
                )

                draw.text(
                    (0, 32),
                    oled_safe(line3),
                    fill="white"
                )

                draw.text(
                    (0, 48),
                    oled_safe(line4),
                    fill="white"
                )


    def clear(self):

        with self.lock:
            self.device.clear()


# ============================================================
# LED SINIFI
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

        self.state = None

        self.off()


    def off(self):

        with self.lock:

            self.green.off()
            self.yellow.off()
            self.red.off()

            self.state = "off"


    def loading(self):

        with self.lock:

            if self.state == "loading":
                return

            self.green.off()
            self.red.off()
            self.yellow.off()

            self.yellow.blink(
                on_time=0.4,
                off_time=0.4,
                background=True
            )

            self.state = "loading"


    def success(self):

        with self.lock:

            self.yellow.off()
            self.red.off()
            self.green.on()

            self.state = "success"


    def fail(self):

        with self.lock:

            self.yellow.off()
            self.green.off()
            self.red.on()

            self.state = "fail"


    def close(self):

        self.off()

        self.green.close()
        self.yellow.close()
        self.red.close()


# ============================================================
# QRING SISTEM
# ============================================================

class QringSystem:

    def __init__(self):

        print("[SISTEM] Donanim hazirlaniyor...")


        # ====================================================
        # OLED
        # ====================================================

        self.oled = OLEDDisplay()


        # ====================================================
        # LEDLER
        # ====================================================

        self.boot_leds = StatusLEDs(
            BOOT_GREEN_PIN,
            BOOT_YELLOW_PIN,
            BOOT_RED_PIN
        )

        self.action_leds = StatusLEDs(
            ACTION_GREEN_PIN,
            ACTION_YELLOW_PIN,
            ACTION_RED_PIN
        )


        # ====================================================
        # FIZIKSEL BUTONLAR
        # ====================================================

        self.btn_taxi = Button(
            TAXI_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.15
        )

        self.btn_call = Button(
            CALL_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.15
        )

        self.btn_switch = Button(
            SWITCH_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.15
        )

        self.btn_residence = Button(
            RESIDENCE_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.15
        )

        self.btn_power = Button(
            POWER_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.25
        )


        # ====================================================
        # KEYPAD
        # ====================================================

        self.keypad_rows = [
            DigitalOutputDevice(
                pin,
                initial_value=True
            )
            for pin in ROWS
        ]

        self.keypad_cols = [
            DigitalInputDevice(
                pin,
                pull_up=True
            )
            for pin in COLS
        ]


        # ====================================================
        # SISTEM DURUMU
        # ====================================================

        self.system_active = False
        self.system_starting = False

        self.residence_mode = False

        # block / apartment / users
        self.residence_stage = "block"

        self.selected_block = None
        self.selected_apartment = None

        self.apartments = []
        self.apartment_input = ""

        self.apartment_users = []
        self.user_page = 0

        self.blocks_cache = []


        # ====================================================
        # API / SIGNALR
        # ====================================================

        self.api = None

        self.signalr = SignalRService()

        self.signalr.set_rejection_callback(
            self.call_rejected
        )


        # ====================================================
        # LOCK / EVENT
        # ====================================================

        self.action_lock = threading.Lock()
        self.power_lock = threading.Lock()

        self.stop_event = threading.Event()


        # ====================================================
        # BUTON EVENTLERI
        # ====================================================

        self.btn_power.when_pressed = (
            lambda: self.run_async(
                self.toggle_power
            )
        )

        self.btn_taxi.when_pressed = (
            lambda: self.run_async(
                self.taxi_action
            )
        )

        self.btn_call.when_pressed = (
            lambda: self.run_async(
                self.call_action
            )
        )

        self.btn_switch.when_pressed = (
            lambda: self.run_async(
                self.switch_action
            )
        )

        self.btn_residence.when_pressed = (
            self.residence_action
        )


        # ====================================================
        # ILK DURUM
        # ====================================================

        self.boot_leds.fail()
        self.action_leds.off()

        self.show_power_off()

        print("[SISTEM] Hazir.")
        print("[SISTEM] ON/OFF butonuna basin.")


    # ========================================================
    # THREAD
    # ========================================================

    def run_async(self, function):

        threading.Thread(
            target=function,
            daemon=True
        ).start()


    # ========================================================
    # OLED EKRANLARI
    # ========================================================

    def show_power_off(self):

        self.oled.show(
            "QRING SISTEM",
            "",
            "SISTEM KAPALI",
            "ON TUSUNA BASIN"
        )


    def show_home(self):

        self.oled.show(
            "1: TAKSI",
            "2: CAGRI",
            "3: SWITCH",
            "4: APARTMAN"
        )


    def show_blocks(self):

        self.oled.show(
            "APARTMAN CAGRI",
            "BLOK SECIN",
            "",
            "A   B   C   D"
        )


    def show_apartment_input(self):

        if self.selected_block is None:
            return

        shown_number = (
            self.apartment_input
            if self.apartment_input
            else "_"
        )

        self.oled.show(
            self.selected_block[
                "blockName"
            ].upper(),
            "",
            "DAIRE NO:",
            shown_number
        )


    # ========================================================
    # OTURANLARI OLED'DE GOSTER
    # ========================================================

    def show_users(self):

        if self.selected_apartment is None:
            return


        apartment_name = self.selected_apartment.get(
            "apartmentName",
            ""
        )

        block_name = self.selected_block.get(
            "blockName",
            ""
        )


        # ----------------------------------------------------
        # Hic kullanici yok
        # ----------------------------------------------------

        if not self.apartment_users:

            self.oled.show(
                f"{block_name} {apartment_name}",
                "KAYITLI KISI YOK",
                "",
                "#ARA   *=GERI"
            )

            return


        # ----------------------------------------------------
        # Her sayfada 2 kisi
        # ----------------------------------------------------

        page_size = 2

        total_pages = (
            len(self.apartment_users)
            + page_size
            - 1
        ) // page_size


        if self.user_page < 0:
            self.user_page = total_pages - 1

        if self.user_page >= total_pages:
            self.user_page = 0


        start = self.user_page * page_size

        page_users = self.apartment_users[
            start:start + page_size
        ]


        name1 = ""

        name2 = ""


        if len(page_users) >= 1:

            name1 = page_users[0].get(
                "nameSurname",
                "Isimsiz"
            )


        if len(page_users) >= 2:

            name2 = page_users[1].get(
                "nameSurname",
                "Isimsiz"
            )


        header = (
            f"{block_name} "
            f"{apartment_name} "
            f"{self.user_page + 1}/{total_pages}"
        )


        self.oled.show(
            header,
            name1,
            name2,
            "2> 8< #ARA *=GERI"
        )


    # ========================================================
    # APARTMAN STATE SIFIRLA
    # ========================================================

    def reset_residence(self):

        self.residence_stage = "block"

        self.selected_block = None
        self.selected_apartment = None

        self.apartments = []
        self.apartment_input = ""

        self.apartment_users = []
        self.user_page = 0


    # ========================================================
    # BLOK BUL
    # ========================================================

    def find_block(self, letter):

        target = (
            f"{letter} Blok"
            .casefold()
        )


        for block in self.blocks_cache:

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

    def find_apartment(self):

        entered = self.apartment_input


        # Önce apartmentNo
        for apartment in self.apartments:

            apartment_no = apartment.get(
                "apartmentNo"
            )


            if apartment_no is not None:

                if str(apartment_no) == entered:

                    return apartment


        # Sonra Daire X
        target = (
            f"Daire {entered}"
            .casefold()
        )


        for apartment in self.apartments:

            name = apartment.get(
                "apartmentName",
                ""
            ).casefold()


            if name == target:
                return apartment


        return None


    # ========================================================
    # POWER TOGGLE
    # ========================================================

    def toggle_power(self):

        if not self.power_lock.acquire(
            blocking=False
        ):

            return


        try:

            if (
                self.system_active
                or self.system_starting
            ):

                self.stop_system()

            else:

                self.start_system()


        finally:

            self.power_lock.release()


    # ========================================================
    # SISTEM BASLAT
    # ========================================================

    def start_system(self):

        if self.system_active:
            return

        if self.system_starting:
            return


        self.system_starting = True

        self.residence_mode = False

        self.reset_residence()


        print()
        print("==============================")
        print("SISTEM BASLATILIYOR")
        print("==============================")


        self.boot_leds.loading()
        self.action_leds.off()


        self.oled.show(
            "QRING SISTEM",
            "",
            "LOGIN",
            "YAPILIYOR..."
        )


        try:

            # API session
            session = create_api_session()

            self.api = APIService(
                session=session
            )


            # LOGIN
            print("[SISTEM] Login...")


            token = self.api.login(
                USERNAME,
                PASSWORD
            )


            if not token:

                raise RuntimeError(
                    "Token alinamadi"
                )


            print("[SISTEM] Token alindi.")


            self.oled.show(
                "QRING SISTEM",
                "",
                "TOKEN ALINDI",
                "SIGNALR..."
            )


            # SIGNALR
            connected = (
                self.signalr.start_connection(
                    token=token,
                    timeout=12
                )
            )


            if not connected:

                raise RuntimeError(
                    "SignalR baglanamadi"
                )


            # AKTIF
            self.system_active = True
            self.system_starting = False

            self.residence_mode = False

            self.blocks_cache = []


            self.boot_leds.success()


            print(
                "[SISTEM] BAGLANTI BASARILI"
            )

            print(
                "[LED] Trafik -> YESIL"
            )


            self.show_home()


        except Exception as e:

            print(
                "[SISTEM HATA]",
                e
            )

            traceback.print_exc()


            self.system_active = False
            self.system_starting = False
            self.residence_mode = False


            self.boot_leds.fail()


            self.oled.show(
                "QRING SISTEM",
                "",
                "BAGLANTI HATASI",
                "TEKRAR DENE"
            )


            try:

                self.signalr.stop_connection()

            except Exception:

                pass


    # ========================================================
    # SISTEM KAPAT
    # ========================================================

    def stop_system(self):

        print("[SISTEM] Kapatiliyor...")


        self.system_active = False
        self.system_starting = False

        self.residence_mode = False

        self.reset_residence()

        self.blocks_cache = []


        try:

            self.signalr.stop_connection()

        except Exception:

            pass


        self.action_leds.off()

        self.boot_leds.fail()

        self.show_power_off()


        print(
            "[SISTEM] Sistem kapali."
        )


    # ========================================================
    # TAKSI
    # ========================================================

    def taxi_action(self):

        if not self.system_active:
            return


        if not self.action_lock.acquire(
            blocking=False
        ):

            return


        try:

            self.action_leds.loading()


            self.oled.show(
                "TAKSI",
                "",
                "CAGIRILIYOR...",
                ""
            )


            result = self.api.call_taxi(
                device_unique_id=TAXI_DEVICE_ID
            )


            print(
                "[TAKSI]",
                result
            )


            self.action_leds.success()


            self.oled.show(
                "TAKSI",
                "",
                "BASARILI",
                ""
            )


            time.sleep(2)


            if self.system_active:

                self.show_home()


        except Exception as e:

            print(
                "[TAKSI HATA]",
                e
            )


            self.action_leds.fail()


            self.oled.show(
                "TAKSI",
                "",
                "HATA",
                ""
            )


        finally:

            self.action_lock.release()


    # ========================================================
    # NORMAL CAGRI
    # ========================================================

    def call_action(self):

        if not self.system_active:
            return


        if not self.action_lock.acquire(
            blocking=False
        ):

            return


        try:

            self.action_leds.loading()


            self.oled.show(
                "CAGRI",
                "",
                "BASLATILIYOR...",
                ""
            )


            result = self.api.start_call(
                device_unique_id=CALL_DEVICE_ID
            )


            print(
                "[CAGRI]",
                result
            )


            self.action_leds.success()


            self.oled.show(
                "CAGRI",
                "",
                "GONDERILDI",
                ""
            )


            time.sleep(2)


            if self.system_active:

                self.show_home()


        except Exception as e:

            print(
                "[CAGRI HATA]",
                e
            )


            self.action_leds.fail()


            self.oled.show(
                "CAGRI",
                "",
                "HATA",
                ""
            )


        finally:

            self.action_lock.release()


    # ========================================================
    # SWITCH
    # ========================================================

    def switch_action(self):

        if not self.system_active:
            return


        if not self.action_lock.acquire(
            blocking=False
        ):

            return


        try:

            self.action_leds.loading()


            self.oled.show(
                "SWITCH",
                "",
                "ISTEK",
                "GONDERILIYOR"
            )


            result = (
                self.api.set_switch_status(
                    switch_id=SWITCH_ID,
                    device_unique_id=CALL_DEVICE_ID
                )
            )


            print(
                "[SWITCH]",
                result
            )


            self.action_leds.success()


            self.oled.show(
                "SWITCH",
                "",
                "BASARILI",
                ""
            )


            time.sleep(2)


            if self.system_active:

                self.show_home()


        except Exception as e:

            print(
                "[SWITCH HATA]",
                e
            )


            self.action_leds.fail()


            self.oled.show(
                "SWITCH",
                "",
                "HATA",
                ""
            )


        finally:

            self.action_lock.release()


    # ========================================================
    # APARTMAN BUTONU
    # ========================================================

    def residence_action(self):

        if not self.system_active:
            return


        if not self.residence_mode:

            self.residence_mode = True

            self.reset_residence()

            self.show_blocks()


            print(
                "[APARTMAN] Mod acildi."
            )


        else:

            self.residence_mode = False

            self.reset_residence()

            self.show_home()


            print(
                "[APARTMAN] Mod kapandi."
            )


    # ========================================================
    # KEYPAD OKUMA
    # ========================================================

    def read_key(self):

        for row_index, row in enumerate(
            self.keypad_rows
        ):

            row.off()

            time.sleep(0.002)


            for col_index, col in enumerate(
                self.keypad_cols
            ):

                if col.is_active:

                    key = KEYS[
                        row_index
                    ][
                        col_index
                    ]


                    while (
                        col.is_active
                        and not self.stop_event.is_set()
                    ):

                        time.sleep(0.02)


                    row.on()

                    time.sleep(0.05)

                    return key


            row.on()


        return None


    # ========================================================
    # KEYPAD ISLEMLERI
    # ========================================================

    def process_key(self, key):

        if not self.system_active:
            return

        if not self.residence_mode:
            return


        print(
            "[KEYPAD]",
            key
        )


        # ====================================================
        # 1) BLOK SECIM ASAMASI
        # ====================================================

        if self.residence_stage == "block":

            # * -> Ana menu
            if key == "*":

                self.residence_mode = False

                self.reset_residence()

                self.show_home()

                return


            if key not in [
                "A",
                "B",
                "C",
                "D"
            ]:

                return


            if not self.action_lock.acquire(
                blocking=False
            ):

                return


            try:

                self.oled.show(
                    "APARTMAN",
                    "",
                    "BLOK",
                    "YUKLENIYOR..."
                )


                if not self.blocks_cache:

                    self.blocks_cache = (
                        self.api.get_block_list(
                            RESIDENCE_DEVICE_ID
                        )
                    )


                block = self.find_block(
                    key
                )


                if block is None:

                    self.oled.show(
                        "HATA",
                        "",
                        "BLOK YOK",
                        key
                    )

                    return


                self.apartments = (
                    self.api.get_apartment_list(
                        block["id"]
                    )
                )


                self.selected_block = block

                self.apartment_input = ""

                self.residence_stage = (
                    "apartment"
                )


                self.show_apartment_input()


            except Exception as e:

                print(
                    "[BLOK HATA]",
                    e
                )


                self.blocks_cache = []


                self.oled.show(
                    "HATA",
                    "",
                    "BLOK LISTESI",
                    "ALINAMADI"
                )


            finally:

                self.action_lock.release()


            return


        # ====================================================
        # 2) DAIRE NUMARASI ASAMASI
        # ====================================================

        if self.residence_stage == "apartment":

            # -----------------------------------------------
            # * -> temizle / bloklara don
            # -----------------------------------------------

            if key == "*":

                if self.apartment_input:

                    self.apartment_input = ""

                    self.show_apartment_input()

                else:

                    self.selected_block = None
                    self.apartments = []

                    self.residence_stage = "block"

                    self.show_blocks()


                return


            # -----------------------------------------------
            # Rakam
            # -----------------------------------------------

            if key.isdigit():

                if len(
                    self.apartment_input
                ) < 3:

                    self.apartment_input += key


                self.show_apartment_input()

                return


            # -----------------------------------------------
            # # -> daireyi onayla ve oturanlari getir
            # -----------------------------------------------

            if key == "#":

                if not self.apartment_input:

                    self.oled.show(
                        "HATA",
                        "",
                        "DAIRE NO GIRIN",
                        ""
                    )

                    return


                apartment = (
                    self.find_apartment()
                )


                if apartment is None:

                    self.oled.show(
                        self.selected_block[
                            "blockName"
                        ].upper(),
                        "",
                        "DAIRE BULUNAMADI",
                        self.apartment_input
                    )


                    self.apartment_input = ""

                    return


                if not self.action_lock.acquire(
                    blocking=False
                ):

                    return


                try:

                    self.selected_apartment = (
                        apartment
                    )


                    apartment_id = apartment[
                        "id"
                    ]


                    print(
                        "[APARTMAN] apartmentId:",
                        apartment_id
                    )


                    self.action_leds.loading()


                    self.oled.show(
                        apartment.get(
                            "apartmentName",
                            ""
                        ),
                        "",
                        "OTURANLAR",
                        "YUKLENIYOR..."
                    )


                    # =======================================
                    # YENI API:
                    # GetApartmentUsers
                    # =======================================

                    self.apartment_users = (
                        self.api.get_apartment_users(
                            apartment_id
                        )
                    )


                    self.user_page = 0

                    self.residence_stage = "users"


                    print(
                        "[APARTMAN] Kullanici sayisi:",
                        len(
                            self.apartment_users
                        )
                    )


                    for user in self.apartment_users:

                        print(
                            " -",
                            user.get(
                                "nameSurname",
                                ""
                            ),
                            "| callable:",
                            user.get(
                                "isCallable"
                            )
                        )


                    # Liste okundu, işlem LEDlerini kapat
                    self.action_leds.off()


                    self.show_users()


                except Exception as e:

                    print(
                        "[KULLANICI HATA]",
                        e
                    )

                    traceback.print_exc()


                    self.action_leds.fail()


                    self.oled.show(
                        "HATA",
                        "",
                        "OTURANLAR",
                        "ALINAMADI"
                    )


                finally:

                    self.action_lock.release()


                return


        # ====================================================
        # 3) OTURANLAR EKRANI
        # ====================================================

        if self.residence_stage == "users":

            # -----------------------------------------------
            # * -> Daire numarasina geri
            # -----------------------------------------------

            if key == "*":

                self.selected_apartment = None

                self.apartment_users = []

                self.user_page = 0

                self.apartment_input = ""

                self.residence_stage = (
                    "apartment"
                )


                self.show_apartment_input()

                return


            # -----------------------------------------------
            # 2 -> sonraki sayfa
            # -----------------------------------------------

            if key == "2":

                if len(
                    self.apartment_users
                ) > 2:

                    self.user_page += 1

                    self.show_users()


                return


            # -----------------------------------------------
            # 8 -> onceki sayfa
            # -----------------------------------------------

            if key == "8":

                if len(
                    self.apartment_users
                ) > 2:

                    self.user_page -= 1

                    self.show_users()


                return


            # -----------------------------------------------
            # # -> Daireyi ara
            # -----------------------------------------------

            if key == "#":

                if (
                    self.selected_apartment
                    is not None
                ):

                    self.run_async(
                        self.residence_call
                    )


                return


    # ========================================================
    # APARTMAN CAGRI
    # ========================================================

    def residence_call(self):

        if not self.action_lock.acquire(
            blocking=False
        ):

            return


        try:

            if (
                self.selected_block is None
                or self.selected_apartment is None
            ):

                return


            block_id = (
                self.selected_block["id"]
            )

            apartment_id = (
                self.selected_apartment["id"]
            )

            apartment_name = (
                self.selected_apartment.get(
                    "apartmentName",
                    ""
                )
            )


            print()
            print("==============================")
            print("APARTMAN CAGRI")
            print(
                "Blok:",
                self.selected_block[
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
            print("==============================")


            self.action_leds.loading()


            self.oled.show(
                self.selected_block[
                    "blockName"
                ].upper(),
                apartment_name.upper(),
                "",
                "ARANIYOR..."
            )


            result = self.api.start_call(
                device_unique_id=(
                    RESIDENCE_CALL_DEVICE_ID
                ),
                guest_name="Keypad",
                block_id=block_id,
                apartment_id=apartment_id,
                apartment_no="undefined"
            )


            print(
                "[APARTMAN CAGRI]",
                result
            )


            self.action_leds.success()


            self.oled.show(
                self.selected_block[
                    "blockName"
                ].upper(),
                apartment_name.upper(),
                "",
                "CAGRI GONDERILDI"
            )


            time.sleep(2)


            self.residence_mode = False

            self.reset_residence()

            self.show_home()


        except Exception as e:

            print(
                "[APARTMAN CAGRI HATA]",
                e
            )

            traceback.print_exc()


            self.action_leds.fail()


            self.oled.show(
                "APARTMAN",
                "",
                "CAGRI HATASI",
                ""
            )


        finally:

            self.action_lock.release()


    # ========================================================
    # CALL REJECTED
    # ========================================================

    def call_rejected(self):

        if not self.system_active:
            return


        print(
            "[SIGNALR] CAGRI REDDEDILDI"
        )


        self.action_leds.fail()


        self.oled.show(
            "CAGRI",
            "",
            "REDDEDILDI",
            ""
        )


    # ========================================================
    # SIGNALR MONITOR
    # ========================================================

    def connection_monitor(self):

        was_connected = None


        while not self.stop_event.is_set():

            if not self.system_active:

                was_connected = None

                time.sleep(0.2)

                continue


            connected = (
                self.signalr
                .connected_event
                .is_set()
            )


            if connected != was_connected:

                if connected:

                    self.boot_leds.success()


                    if was_connected is False:

                        print(
                            "[SIGNALR] Yeniden baglandi."
                        )


                        if self.residence_mode:

                            if (
                                self.residence_stage
                                == "users"
                            ):

                                self.show_users()

                            elif (
                                self.residence_stage
                                == "apartment"
                            ):

                                self.show_apartment_input()

                            else:

                                self.show_blocks()

                        else:

                            self.show_home()


                else:

                    self.boot_leds.loading()


                    print(
                        "[SIGNALR] Baglanti koptu."
                    )


                    self.oled.show(
                        "QRING SISTEM",
                        "",
                        "BAGLANTI KOPTU",
                        "BEKLEYIN..."
                    )


                was_connected = connected


            time.sleep(0.2)


    # ========================================================
    # KEYPAD LOOP
    # ========================================================

    def keypad_loop(self):

        while not self.stop_event.is_set():

            if (
                not self.system_active
                or not self.residence_mode
            ):

                time.sleep(0.1)

                continue


            try:

                key = self.read_key()


                if key is not None:

                    self.process_key(
                        key
                    )


            except Exception as e:

                print(
                    "[KEYPAD HATA]",
                    e
                )

                traceback.print_exc()


            time.sleep(0.01)


    # ========================================================
    # PROGRAM
    # ========================================================

    def run(self):

        threading.Thread(
            target=self.connection_monitor,
            daemon=True
        ).start()


        threading.Thread(
            target=self.keypad_loop,
            daemon=True
        ).start()


        print()
        print("==============================")
        print("QRING SISTEM CALISIYOR")
        print("==============================")


        while not self.stop_event.is_set():

            time.sleep(0.5)


    # ========================================================
    # TEMIZLIK
    # ========================================================

    def shutdown(self):

        print(
            "[SISTEM] GPIO temizleniyor..."
        )


        self.stop_event.set()

        self.system_active = False


        try:

            self.signalr.stop_connection()

        except Exception:

            pass


        self.boot_leds.close()
        self.action_leds.close()


        self.btn_taxi.close()
        self.btn_call.close()
        self.btn_switch.close()
        self.btn_residence.close()
        self.btn_power.close()


        for row in self.keypad_rows:

            row.close()


        for col in self.keypad_cols:

            col.close()


        self.oled.clear()


# ============================================================
# PROGRAM BASLANGICI
# ============================================================

if __name__ == "__main__":

    system = None


    try:

        system = QringSystem()

        system.run()


    except KeyboardInterrupt:

        print(
            "\nCTRL+C -> Program durduruldu."
        )


    except Exception as e:

        print()
        print("==============================")
        print("BEKLENMEYEN PROGRAM HATASI")
        print("==============================")

        print(e)

        traceback.print_exc()


    finally:

        if system is not None:

            system.shutdown()
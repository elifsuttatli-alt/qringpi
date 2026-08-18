from time import sleep

from gpiozero import DigitalOutputDevice, DigitalInputDevice

from interceptor import create_api_session
from api_service import APIService

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas


# ============================================================
# LOGIN
# ============================================================

USERNAME = "samsung.canli@fsitip.com"
PASSWORD = "Aa123456."


# ============================================================
# CALL DEVICE
# ============================================================

CALL_DEVICE_UNIQUE_ID = (
    "289AF5D65ABDC9FFB2FE7DBE1AA66A9D5A2C8D5C5ACF269E87D701CB868E1723"
)


# ============================================================
# KEYPAD GPIO
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

serial = i2c(
    port=1,
    address=0x3C
)

oled = ssd1306(
    serial,
    width=128,
    height=64
)


def oled_show(line1="", line2="", line3="", line4=""):

    with canvas(oled) as draw:

        draw.text((0, 0), line1, fill="white")
        draw.text((0, 16), line2, fill="white")
        draw.text((0, 32), line3, fill="white")
        draw.text((0, 48), line4, fill="white")


# ============================================================
# KEYPAD
# ============================================================

rows = [
    DigitalOutputDevice(pin, initial_value=True)
    for pin in ROWS
]

cols = [
    DigitalInputDevice(pin, pull_up=True)
    for pin in COLS
]


def get_key():

    while True:

        for row_index, row in enumerate(rows):

            row.off()

            sleep(0.002)

            for col_index, col in enumerate(cols):

                if col.is_active:

                    key = KEYS[row_index][col_index]

                    while col.is_active:
                        sleep(0.02)

                    row.on()

                    sleep(0.05)

                    return key

            row.on()

        sleep(0.01)


# ============================================================
# API
# ============================================================

session = create_api_session()
api = APIService(session=session)


print("Login yapiliyor...")

token = api.login(
    USERNAME,
    PASSWORD
)

print("Login basarili.")


# ============================================================
# BLOKLARI AL
# ============================================================

blocks = api.get_block_list()


def find_block(letter):

    target = f"{letter} Blok".casefold()

    for block in blocks:

        if block["blockName"].casefold() == target:
            return block

    return None


# ============================================================
# DAIRE BUL
# ============================================================

def find_apartment(apartments, entered_number):

    # Önce apartmentNo alanına bak
    for apartment in apartments:

        apartment_no = apartment.get("apartmentNo")

        if apartment_no is not None:

            if str(apartment_no) == entered_number:
                return apartment


    # apartmentNo boşsa isimden bulmaya çalış
    target = f"Daire {entered_number}".casefold()

    for apartment in apartments:

        name = apartment.get(
            "apartmentName",
            ""
        ).casefold()

        if name == target:
            return apartment


    return None

# ============================================================
# ANA DONGU
# ============================================================

selected_block = None
apartments = []
apartment_input = ""


oled_show(
    "BLOK SECIN",
    "",
    "A  B  C  D",
    ""
)


print()
print("A/B/C/D ile blok secin.")


try:

    while True:

        key = get_key()

        print("Tus:", key)


        # ====================================================
        # BLOK SECIMI
        # ====================================================

        if selected_block is None:

            if key in ["A", "B", "C", "D"]:

                block = find_block(key)

                if block is None:

                    oled_show(
                        "HATA",
                        "",
                        "BLOK BULUNAMADI",
                        ""
                    )

                    sleep(2)

                    oled_show(
                        "BLOK SECIN",
                        "",
                        "A  B  C  D",
                        ""
                    )

                    continue


                selected_block = block

                apartments = api.get_apartment_list(
                    selected_block["id"]
                )

                apartment_input = ""


                print(
                    "Secilen blok:",
                    selected_block["blockName"],
                    "ID:",
                    selected_block["id"]
                )


                oled_show(
                    selected_block["blockName"].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )


            continue


        # ====================================================
        # * -> GERI
        # ====================================================

        if key == "*":

            selected_block = None
            apartments = []
            apartment_input = ""

            oled_show(
                "BLOK SECIN",
                "",
                "A  B  C  D",
                ""
            )

            print("Blok secimine donuldu.")

            continue


        # ====================================================
        # SAYI GIRISI
        # ====================================================

        if key.isdigit():

            # Maksimum 3 hane
            if len(apartment_input) < 3:

                apartment_input += key


            oled_show(
                selected_block["blockName"].upper(),
                "",
                "DAIRE NO:",
                apartment_input
            )

            continue


        # ====================================================
        # # -> CAGRI
        # ====================================================

        if key == "#":

            if apartment_input == "":

                oled_show(
                    "HATA",
                    "",
                    "DAIRE GIRIN",
                    ""
                )

                sleep(1.5)

                oled_show(
                    selected_block["blockName"].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )

                continue


            apartment = find_apartment(
                apartments,
                apartment_input
            )


            if apartment is None:

                oled_show(
                    "HATA",
                    "",
                    "DAIRE YOK",
                    apartment_input
                )

                print(
                    "Daire bulunamadi:",
                    apartment_input
                )

                sleep(2)

                apartment_input = ""

                oled_show(
                    selected_block["blockName"].upper(),
                    "",
                    "DAIRE NO:",
                    "_"
                )

                continue


            # -----------------------------------------------
            # CAGRI BILGILERI
            # -----------------------------------------------

            block_id = selected_block["id"]
            apartment_id = apartment["id"]

            print()
            print("CAGRI BASLATILIYOR")
            print("Blok:", selected_block["blockName"])
            print("blockId:", block_id)
            print("Daire:", apartment["apartmentName"])
            print("apartmentId:", apartment_id)


            oled_show(
                selected_block["blockName"].upper(),
                apartment["apartmentName"].upper(),
                "",
                "ARANIYOR..."
            )


            try:

                result = api.start_call(
                    device_unique_id=CALL_DEVICE_UNIQUE_ID,
                    guest_name="Keypad",
                    block_id=block_id,
                    apartment_id=apartment_id,
                    apartment_no="undefined"
                )


                print(
                    "CallStart yaniti:",
                    result
                )


                oled_show(
                    selected_block["blockName"].upper(),
                    apartment["apartmentName"].upper(),
                    "",
                    "CAGRI GONDERILDI"
                )


            except Exception as e:

                print(
                    "Cagri hatasi:",
                    e
                )


                oled_show(
                    "CAGRI HATASI",
                    "",
                    "ISTEK",
                    "BASARISIZ"
                )


            sleep(3)


            # Yeni seçim için başa dön
            selected_block = None
            apartments = []
            apartment_input = ""


            oled_show(
                "BLOK SECIN",
                "",
                "A  B  C  D",
                ""
            )


except KeyboardInterrupt:

    print("\nProgram kapatildi.")


finally:

    for row in rows:
        row.close()

    for col in cols:
        col.close()

    oled.clear()
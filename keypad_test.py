from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep


ROWS = [4, 7, 8, 9]
COLS = [10, 11, 18, 19]

KEYS = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]


rows = [
    DigitalOutputDevice(pin, initial_value=True)
    for pin in ROWS
]

cols = [
    DigitalInputDevice(pin, pull_up=True)
    for pin in COLS
]


print("KEYPAD TEST BASLADI")
print("Tuslara basin...")


try:
    while True:

        for row_index, row in enumerate(rows):

            # O an taranan satırı LOW yap
            row.off()
            sleep(0.002)

            for col_index, col in enumerate(cols):

                # Tuşa BASILDIYSA
                if col.is_active:

                    key = KEYS[row_index][col_index]

                    print("BASILAN TUS:", key)

                    # Tuş bırakılana kadar bekle
                    while col.is_active:
                        sleep(0.02)

                    sleep(0.05)

            # Satırı tekrar HIGH yap
            row.on()


except KeyboardInterrupt:
    print("\nTest kapatildi.")


finally:
    for row in rows:
        row.close()

    for col in cols:
        col.close()
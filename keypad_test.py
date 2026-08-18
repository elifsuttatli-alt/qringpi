from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep


# Keypad'in ilk 4 hattı
ROWS = [4, 7, 8, 9]

# Son 4 hattı
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
print("Tuslara tek tek basin...")


try:

    while True:

        for row_index, row in enumerate(rows):

            # Sadece bu satiri LOW yap
            row.off()

            sleep(0.002)

            for col_index, col in enumerate(cols):

                if not col.value:

                    key = KEYS[row_index][col_index]

                    print("BASILAN TUS:", key)

                    # Tus birakilana kadar bekle
                    while not col.value:
                        sleep(0.02)

                    sleep(0.05)

            # Satiri tekrar HIGH yap
            row.on()


except KeyboardInterrupt:

    print("\nTest kapatildi.")


finally:

    for row in rows:
        row.close()

    for col in cols:
        col.close()
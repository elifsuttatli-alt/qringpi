from time import sleep

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

print("OLED testi basliyor...")

serial = i2c(port=1, address=0x3C)
oled = ssd1306(serial, width=128, height=64)

print("OLED baglantisi kuruldu.")

with canvas(oled) as draw:
    draw.rectangle(oled.bounding_box, outline="white", fill="white")

print("Ekran 5 saniye tamamen yanmali.")

sleep(5)

oled.clear()

print("Test bitti.")
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

serial = i2c(port=1, address=0x3C)
oled = ssd1306(serial)

with canvas(oled) as draw:
    draw.text((0, 0), "QRING SISTEM", fill="white")
    draw.text((0, 20), "OLED CALISIYOR", fill="white")
from gpiozero import LED
from time import sleep

red = LED(25)   # GPIO25 = fiziksel Pin 22

red.off()
print("Kırmızı SÖNÜK olmalı")
sleep(5)

red.on()
print("Kırmızı YANIK olmalı")
sleep(5)

red.off()

print("Kırmızı tekrar SÖNÜK olmalı")
sleep(5)

red.close()
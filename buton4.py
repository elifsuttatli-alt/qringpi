from gpiozero import Button
from time import sleep

btn4 = Button(16, pull_up=True, bounce_time=0.1)

print("4. BUTON TESTI")

while True:
    if btn4.is_pressed:
        print("4. BUTONA BASILDI")
        sleep(0.5)

    sleep(0.05)
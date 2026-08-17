from gpiozero import Button
from signal import pause

system_switch = Button(12, pull_up=True, bounce_time=0.05)

def system_on():
    print("SİSTEM ON")

def system_off():
    print("SİSTEM OFF")

system_switch.when_pressed = system_on
system_switch.when_released = system_off

print("Switch testi başladı.")
print("Mevcut durum:", "ON" if system_switch.is_pressed else "OFF")

pause()
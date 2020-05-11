from gpiozero import PWMLED
import time

buzzer = PWMLED(24)
buzzer.value = 0.5
time.sleep(0.02)
buzzer.value = 0
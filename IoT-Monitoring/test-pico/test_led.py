from machine import Pin
import time

# 일반 피코는 무조건 숫자 25를 넣어야 합니다.
led = Pin(25, Pin.OUT)
led.value(1)
while True:
    led.value(0)
    time.sleep_ms(1000)
    led.value(1)
    time.sleep_ms(1000)

print("일반 피코: LED가 켜졌습니다!")
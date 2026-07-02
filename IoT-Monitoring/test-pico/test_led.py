from machine import Pin

# 일반 피코는 무조건 숫자 25를 넣어야 합니다.
led = Pin(25, Pin.OUT)
led.value(1)
print("일반 피코: LED가 켜졌습니다!")
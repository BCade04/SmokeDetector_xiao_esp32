import network
import time

from secrets import WIFI_SSID
from secrets import WIFI_PASSWORD


wlan = network.WLAN(network.STA_IF)
if wlan.isconnected() == False:
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        time.sleep_ms(500)
else:
    pass
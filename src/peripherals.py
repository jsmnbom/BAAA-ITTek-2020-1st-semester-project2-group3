from functools import partial

import board
import digitalio
import adafruit_ssd1306
from lazy_object_proxy import Proxy
from rpi_TM1638 import TMBoards
from gpiozero import Button

# Use lazy object proxy so we can import this project as a library
# without affecting the display and such. This allows us to more
# easily test the libary and to provide fake clients and servers for testing.

LED_KEY = Proxy(partial(TMBoards, dio=18, clk=15, stb=14, brightness=1))

BUTTON = Proxy(partial(Button, 23))

OLED = Proxy(
    partial(adafruit_ssd1306.SSD1306_SPI,
            128,
            64,
            spi=board.SPI(),
            dc=digitalio.DigitalInOut(board.D7),
            reset=digitalio.DigitalInOut(board.D25),
            cs=digitalio.DigitalInOut(board.D8)))

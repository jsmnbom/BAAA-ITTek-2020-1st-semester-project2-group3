import board
import digitalio
import adafruit_ssd1306
from rpi_TM1638 import TMBoards
from gpiozero import Button

LED_KEY = TMBoards(dio=18, clk=15, stb=14, brightness=1)

BUTTON = Button(23)

OLED = adafruit_ssd1306.SSD1306_SPI(128,
                                    64,
                                    spi=board.SPI(),
                                    dc=digitalio.DigitalInOut(board.D7),
                                    reset=digitalio.DigitalInOut(board.D25),
                                    cs=digitalio.DigitalInOut(board.D8))

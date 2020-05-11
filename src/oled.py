from PIL import Image, ImageDraw, ImageFont
import textwrap
import operator
import itertools

from peripherals import OLED


def clear():
    # Fill with black
    OLED.fill(0)
    OLED.show()


def show_msg(msg: str, *, tight=False, big=False, dbg=True):
    if dbg:
        print(f'OLED: {msg!r}')
    # Get an image and a instance of it we can draw on
    image = Image.new('1', (OLED.width, OLED.height))
    draw = ImageDraw.Draw(image)

    # Get the font we want to draw with
    font = ImageFont.truetype('m5x7.ttf', 24 if big else 16)

    # Wrap into multiple lines (preserving excisting newlines)
    # with width depending on the font size
    # Note that not all chars are equal width, so this
    # could be slightly off - so it's a bit pesimistic
    lines = list(
        itertools.chain(*[
            textwrap.wrap(line, width=10 if big else 20)
            for line in msg.split('\n')
        ]))
    # Get pixel sizes for each line. Subtract 2 (or 4 if tight) from the height
    line_sizes = [
        tuple(map(operator.sub, font.getsize(line), (0, (4 if tight else 2))))
        for line in lines
    ]
    # Calculate the full height of the text

    full_h = sum([h for (w, h) in line_sizes])
    # Our current drawing h position, we want it to be at least 0, so that
    # if text is too large, the start of the text is still visible
    current_h = max((OLED.height - full_h) / 2, 0)

    # Loop over each line and (width, height)
    for line, (w, h) in zip(lines, line_sizes):
        # Draw the line in white using the font in the middle of the display (width)
        draw.text(((OLED.width - w) / 2, current_h), line, font=font, fill=255)
        # Go to the next line
        current_h += h

    # Show the image on the display
    OLED.image(image)
    OLED.show()

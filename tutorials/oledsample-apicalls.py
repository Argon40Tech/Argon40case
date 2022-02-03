#!/usr/bin/python3

import os
if os.path.exists("/etc/argon/argoneonoled.py"):
	import sys
	sys.path.append("/etc/argon/")
	from argoneonoled import *
else:
	print("Please install Argon script")
	exit()

print("You may need to disable OLED from argon-config")


# Get Screen dimensions
oledht = oled_getmaxY()
oledwd = oled_getmaxX()

# Ensure display is on
oled_power(True)

# Clear OLED buffer
oled_clearbuffer()

# Write text
xpos = 10
ypos = 0
charwd=12 # Values are 6, 12, 24, 48, these are 8, 16, 32, 64 px tall respectively
oled_writetext("Hello!", xpos, ypos, charwd)

# Draw rectangle
xpos = 10
ypos = 17
rectwd = oledwd - 2*xpos
rectht = 14
oled_drawfilledrectangle(xpos, ypos, rectwd, rectht)

# Draw Pixel (1 or 0)
xpos = 15
ypos = 35
oled_writebuffer(xpos, ypos, 1)

# Draw text
xpos = 15
ypos = 40
charwd = 6
oled_writetext("Dot is above!", xpos, ypos, charwd)


# Draw pixels across the rectangle
xpos = 15
ypos = 17
ctr = 0
while ctr < rectht:
	oled_writebuffer(xpos+ctr, ypos+ctr, 0)
	# Second slash
	oled_writebuffer(xpos+ctr + rectht, ypos+ctr, 0)
	ctr = ctr + 1
oled_writebuffer(xpos, ypos, 0)
oled_writebuffer(xpos+2, ypos+2, 0)
oled_writebuffer(xpos, ypos, 1)

# Update OLED screen with buffer content
oled_flushimage()

# Reset OLED settings
oled_reset()



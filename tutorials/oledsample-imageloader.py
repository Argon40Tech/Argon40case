#!/usr/bin/python3

from PIL import Image
import math

import os
if os.path.exists("/etc/argon/argoneonoled.py"):
	import sys
	sys.path.append("/etc/argon/")
	from argoneonoled import *
else:
	print("Please install Argon script")
	exit()

print("You may need to disable OLED from argon-config")


# Image path
imgfname="/usr/share/plymouth/themes/pix/splash.png"


# Get Screen dimensions
oledht = oled_getmaxY()
oledwd = oled_getmaxX()

# Ensure display is on
oled_power(True)

# Clear OLED buffer
oled_clearbuffer()


# Load image
imgdata = Image.open(imgfname)
imgwd, imght = imgdata.size

# Rescale image to fit screen
scalefactor = oledwd/imgwd
if scalefactor > (oledht/imght):
	scalefactor = oledht/imght
imgwd = math.floor(imgwd*scalefactor)
imght = math.floor(imght*scalefactor)
imgdata = imgdata.resize((imgwd, imght), Image.ANTIALIAS)

# Offsets to center image
xoffset = math.floor((oledwd-imgwd)/2)
yoffset = math.floor((oledht-imght)/2)

xpos = 0
while xpos < imgwd:
	ypos = 0
	while ypos < imght:
		r, g, b, p = imgdata.getpixel((xpos, ypos))

		# Check if we'll write pixel
		if (r+g+b) >= 128:
			oled_writebuffer(xpos+xoffset, ypos+yoffset, 1)
		
		ypos = ypos + 1

	xpos = xpos + 1

# Close image
imgdata.close()

# Update OLED screen with buffer content
oled_flushimage()

# Reset OLED settings
oled_reset()

#!/usr/bin/python

import smbus
import RPi.GPIO as GPIO

rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
	bus = smbus.SMBus(1)
else:
	bus = smbus.SMBus(0)


argononeaddress = 0x1a

bus.write_byte(argononeaddress,0xFF)
bus.close()
print "Shutdown the system to cut power"

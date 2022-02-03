#!/usr/bin/python

import smbus
import RPi.GPIO as GPIO

rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
	bus = smbus.SMBus(1)
else:
	bus = smbus.SMBus(0)

argononeaddress = 0x1a

# Change the value, 0 to 100
fanspeed = 50

bus.write_byte(argononeaddress,fanspeed)
bus.close()
print "Fan speed updated"

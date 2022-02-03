#!/usr/bin/python

import RPi.GPIO as GPIO

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
powerbuttonevent_pin=4
GPIO.setup(powerbuttonevent_pin, GPIO.IN,  pull_up_down=GPIO.PUD_DOWN)


print "Double Tap or Hold and Release Power Button after 3 seconds (CTRL+C to end)..."

try:
	# Listen to GPIO BCM 4 / BOARD P7
	while True:
		pulsetime = 10
		GPIO.wait_for_edge(powerbuttonevent_pin, GPIO.RISING)
		time.sleep(0.01)
		while GPIO.input(powerbuttonevent_pin) == GPIO.HIGH:
			time.sleep(0.01)
			pulsetime += 10
		print pulsetime

except KeyboardInterrupt:  
    print "Done"
except:  
    print "Error"  
finally:  
    GPIO.cleanup() # this ensures a clean exit  

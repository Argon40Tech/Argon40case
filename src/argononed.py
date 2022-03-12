#!/usr/bin/python3

#
# This script set fan speed and monitor power button events.
#
# Fan Speed is set by sending 0 to 100 to the MCU (Micro Controller Unit)
# The values will be interpreted as the percentage of fan speed, 100% being maximum
#
# Power button events are sent as a pulse signal to BCM Pin 4 (BOARD P7)
# A pulse width of 20-30ms indicates reboot request (double-tap)
# A pulse width of 40-50ms indicates shutdown request (hold and release after 3 secs)
#
# Additional comments are found in each function below
#
# Standard Deployment/Triggers:
#  * Raspbian, OSMC: Runs as service via /lib/systemd/system/argononed.service
#  * lakka, libreelec: Runs as service via /storage/.config/system.d/argononed.service
#  * recalbox: Runs as service via /etc/init.d/
#

# For Libreelec/Lakka, note that we need to add system paths
# import sys
# sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import RPi.GPIO as GPIO

import sys
import os
import time
from threading import Thread
from queue import Queue

sys.path.append("/etc/argon/")
from argonsysinfo import *
# Initialize I2C Bus
import smbus

rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
	bus=smbus.SMBus(1)
else:
	bus=smbus.SMBus(0)


OLED_ENABLED=False

if os.path.exists("/etc/argon/argoneonoled.py"):
	import datetime
	from argoneonoled import *
	OLED_ENABLED=True

OLED_CONFIGFILE = "/etc/argoneonoled.conf"

ADDR_FAN=0x1a
PIN_SHUTDOWN=4

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_SHUTDOWN, GPIO.IN,  pull_up_down=GPIO.PUD_DOWN)


# This function is the thread that monitors activity in our shutdown pin
# The pulse width is measured, and the corresponding shell command will be issued

def shutdown_check(writeq):
	while True:
		pulsetime = 1
		GPIO.wait_for_edge(PIN_SHUTDOWN, GPIO.RISING)
		time.sleep(0.01)
		while GPIO.input(PIN_SHUTDOWN) == GPIO.HIGH:
			time.sleep(0.01)
			pulsetime += 1
		if pulsetime >=2 and pulsetime <=3:
			# Testing
			#writeq.put("OLEDSWITCH")
			writeq.put("OLEDSTOP")
			os.system("reboot")
		elif pulsetime >=4 and pulsetime <=5:
			writeq.put("OLEDSTOP")
			os.system("shutdown now -h")
		elif pulsetime >=6 and pulsetime <=7:
			writeq.put("OLEDSWITCH")

# This function converts the corresponding fanspeed for the given temperature
# The configuration data is a list of strings in the form "<temperature>=<speed>"

def get_fanspeed(tempval, configlist):
	for curconfig in configlist:
		curpair = curconfig.split("=")
		tempcfg = float(curpair[0])
		fancfg = int(float(curpair[1]))
		if tempval >= tempcfg:
			if fancfg < 25:
				return 25
			return fancfg
	return 0

# This function retrieves the fanspeed configuration list from a file, arranged by temperature
# It ignores lines beginning with "#" and checks if the line is a valid temperature-speed pair
# The temperature values are formatted to uniform length, so the lines can be sorted properly

def load_config(fname):
	newconfig = []
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				tempval = 0
				fanval = 0
				try:
					tempval = float(tmppair[0])
					if tempval < 0 or tempval > 100:
						continue
				except:
					continue
				try:
					fanval = int(float(tmppair[1]))
					if fanval < 0 or fanval > 100:
						continue
				except:
					continue
				newconfig.append( "{:5.1f}={}".format(tempval,fanval))
		if len(newconfig) > 0:
			newconfig.sort(reverse=True)
	except:
		return []
	return newconfig

# Load OLED Config file
def load_oledconfig(fname):
	output={}
	screenduration=-1
	screenlist=[]
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "switchduration":
					output['screenduration']=int(tmppair[1])
				elif tmppair[0] == "screensaver":
					output['screensaver']=int(tmppair[1])
				elif tmppair[0] == "screenlist":
					output['screenlist']=tmppair[1].replace("\"", "").split(" ")
				elif tmppair[0] == "enabled":
					output['enabled']=tmppair[1].replace("\"", "")
	except:
		return {}
	return output

# This function is the thread that monitors temperature and sets the fan speed
# The value is fed to get_fanspeed to get the new fan speed
# To prevent unnecessary fluctuations, lowering fan speed is delayed by 30 seconds
#
# Location of config file varies based on OS
#
def temp_check():
	fanconfig = ["65=100", "60=55", "55=10"]
	tmpconfig = load_config("/etc/argononed.conf")
	if len(tmpconfig) > 0:
		fanconfig = tmpconfig
	prevspeed=0
	while True:
		val = argonsysinfo_gettemp()
		hddval = argonsysinfo_gethddtemp()
		if hddval > val:
			val = hddval
		newspeed = get_fanspeed(val, fanconfig)
		if newspeed < prevspeed:
			# Pause 30s if reduce to prevent fluctuations
			time.sleep(30)
		prevspeed = newspeed
		try:
			if newspeed > 0:
				# Spin up to prevent issues on older units
				bus.write_byte(ADDR_FAN,100)
				time.sleep(1)
			bus.write_byte(ADDR_FAN,newspeed)
			time.sleep(30)
		except IOError:
			time.sleep(60)

#
# This function is the thread that updates OLED
#
def display_loop(readq):
	weekdaynamelist = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] 
	monthlist = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"] 
	oledscreenwidth = oled_getmaxX()

	fontwdSml = 6	# Maps to 6x8
	fontwdReg = 8	# Maps to 8x16
	stdleftoffset = 54

	screensavermode = False
	screensaversec = 120
	screensaverctr = 0

	screenenabled = ["clock", "ip"]
	prevscreen = ""
	curscreen = ""
	screenid = 0
	screenjogtime = 0
	screenjogflag = 0	# start with screenid 0
	cpuusagelist = []
	curlist = []

	tmpconfig=load_oledconfig(OLED_CONFIGFILE)

	if "screensaver" in tmpconfig:
		screensaversec = tmpconfig["screensaver"]
	if "screenduration" in tmpconfig:
		screenjogtime = tmpconfig["screenduration"]
	if "screenlist" in tmpconfig:
		screenenabled = tmpconfig["screenlist"]

	if "enabled" in tmpconfig:
		if tmpconfig["enabled"] == "N":
			screenenabled = []

	while len(screenenabled) > 0:
		if len(curlist) == 0 and screenjogflag == 1:
			# Reset Screen Saver
			screensavermode = False
			screensaverctr = 0

			# Update screen info
			screenid = screenid + screenjogflag
			if screenid >= len(screenenabled):
				screenid = 0
		prevscreen = curscreen
		curscreen = screenenabled[screenid]

		if screenjogtime == 0:
			# Resets jogflag (if switched manually)
			screenjogflag = 0
		else:
			screenjogflag = 1

		needsUpdate = False
		if curscreen == "cpu":
			# CPU Usage
			if len(curlist) == 0:
				try:
					if len(cpuusagelist) == 0:
						cpuusagelist = argonsysinfo_listcpuusage()
					curlist = cpuusagelist
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgcpu")

				# Display List
				yoffset = 0
				tmpmax = 4
				while tmpmax > 0 and len(curlist) > 0:
					curline = ""
					tmpitem = curlist.pop(0)
					curline = tmpitem["title"]+": "+str(tmpitem["value"])+"%"
					oled_writetext(curline, stdleftoffset, yoffset, fontwdSml)
					oled_drawfilledrectangle(stdleftoffset, yoffset+12, int((oledscreenwidth-stdleftoffset-4)*tmpitem["value"]/100), 2)
					tmpmax = tmpmax - 1
					yoffset = yoffset + 16

				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "storage":
			# Storage Info
			if len(curlist) == 0:
				try:
					tmpobj = argonsysinfo_listhddusage()
					for curdev in tmpobj:
						curlist.append({"title": curdev, "value": argonsysinfo_kbstr(tmpobj[curdev]['total']), "usage": int(100*tmpobj[curdev]['used']/tmpobj[curdev]['total']) })
					#curlist = argonsysinfo_liststoragetotal()
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgstorage")
				
				yoffset = 16
				tmpmax = 3
				while tmpmax > 0 and len(curlist) > 0:
					tmpitem = curlist.pop(0)
					# Right column first, safer to overwrite white space
					oled_writetextaligned(tmpitem["value"], 77, yoffset, oledscreenwidth-77, 2, fontwdSml)
					oled_writetextaligned(str(tmpitem["usage"])+"%", 50, yoffset, 74-50, 2, fontwdSml)
					tmpname = tmpitem["title"]
					if len(tmpname) > 8:
						tmpname = tmpname[0:8]
					oled_writetext(tmpname, 0, yoffset, fontwdSml)
					
					tmpmax = tmpmax - 1
					yoffset = yoffset + 16
				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1

		elif curscreen == "raid":
			# Raid Info
			if len(curlist) == 0:
				try:
					tmpobj = argonsysinfo_listraid()
					curlist = tmpobj['raidlist']
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgraid")
				tmpitem = curlist.pop(0)
				oled_writetextaligned(tmpitem["title"], 0, 0, stdleftoffset, 1, fontwdSml)
				oled_writetextaligned(tmpitem["value"], 0, 8, stdleftoffset, 1, fontwdSml)
				oled_writetextaligned(argonsysinfo_kbstr(tmpitem["info"]["size"]), 0, 56, stdleftoffset, 1, fontwdSml)

				oled_writetext("Used:"+argonsysinfo_kbstr(tmpitem["info"]["used"]), stdleftoffset, 8, fontwdSml)
				oled_writetext("      "+str(int(100*tmpitem["info"]["used"]/tmpitem["info"]["size"]))+"%", stdleftoffset, 16, fontwdSml)
				oled_writetext("Active:"+str(int(tmpitem["info"]["active"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 32, fontwdSml)
				oled_writetext("Working:"+str(int(tmpitem["info"]["working"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 40, fontwdSml)
				oled_writetext("Failed:"+str(int(tmpitem["info"]["failed"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 48, fontwdSml)
				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1

		elif curscreen == "ram":
			# RAM
			try:
				oled_loadbg("bgram")
				tmpraminfo = argonsysinfo_getram()
				oled_writetextaligned(tmpraminfo[0], stdleftoffset, 8, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				oled_writetextaligned("of", stdleftoffset, 24, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				oled_writetextaligned(tmpraminfo[1], stdleftoffset, 40, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "temp":
			# Temp
			try:
				maxht = 21
				oled_loadbg("bgtemp")
				cval = argonsysinfo_gettemp()
				fval = 32+9*cval/5

				# 40C is min, 80C is max
				barht = int(maxht*(cval-40)/40)
				if barht > maxht:
					barht = maxht
				elif barht < 1:
					barht = 1

				tmpcstr = str(cval)
				if len(tmpcstr) > 4:
					tmpcstr = tmpcstr[0:4]
				tmpfstr = str(fval)
				if len(tmpfstr) > 5:
					tmpfstr = tmpfstr[0:5]

				oled_writetextaligned(tmpcstr+ chr(167) +"C", stdleftoffset, 16, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				oled_writetextaligned(tmpfstr+ chr(167) +"F", stdleftoffset, 32, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				oled_drawfilledrectangle(24, 20+(maxht-barht), 3, barht, 2)

				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "ip":
			# IP Address
			try:
				oled_loadbg("bgip")
				oled_writetextaligned(argonsysinfo_getip(), 0, 8, oledscreenwidth, 1, fontwdReg)
				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		else:
			try:
				oled_loadbg("bgtime")
				# Date and Time HH:MM
				curtime = datetime.datetime.now()

				# Month/Day
				outstr = str(curtime.day).strip()
				if len(outstr) < 2:
					outstr = " "+outstr
				outstr = monthlist[curtime.month-1]+outstr
				oled_writetextaligned(outstr, stdleftoffset, 8, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				# Day of Week
				oled_writetextaligned(weekdaynamelist[curtime.weekday()], stdleftoffset, 24, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				
				# Time
				outstr = str(curtime.minute).strip()
				if len(outstr) < 2:
					outstr = "0"+outstr
				outstr = str(curtime.hour)+":"+outstr
				if len(outstr) < 5:
					outstr = "0"+outstr
				oled_writetextaligned(outstr, stdleftoffset, 40, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1

		if needsUpdate == True:
			if screensavermode == False:
				# Update screen if not screen saver mode
				oled_power(True)
				oled_flushimage(prevscreen != curscreen)
				oled_reset()

			timeoutcounter = 0
			while timeoutcounter<screenjogtime or screenjogtime == 0:
				qdata = ""
				if readq.empty() == False:
					qdata = readq.get()

				if qdata == "OLEDSWITCH":
					# Trigger screen switch
					screenjogflag = 1
					# Reset Screen Saver
					screensavermode = False
					screensaverctr = 0

					break
				elif qdata == "OLEDSTOP":
					# End OLED Thread
					display_defaultimg()
					return
				else:
					screensaverctr = screensaverctr + 1
					if screensaversec <= screensaverctr and screensavermode == False:
						screensavermode = True
						oled_fill(0)
						oled_reset()
						oled_power(False)

					if timeoutcounter == 0:
						# Use 1 sec sleep get CPU usage
						cpuusagelist = argonsysinfo_listcpuusage(1)
					else:
						time.sleep(1)

					timeoutcounter = timeoutcounter + 1
					if timeoutcounter >= 60 and screensavermode == False:
						# Refresh data every minute, unless screensaver got triggered
						screenjogflag = 0
						break
	display_defaultimg()

def display_defaultimg():
	# Load default image
	#oled_power(True)
	#oled_loadbg("bgdefault")
	#oled_flushimage()
	oled_fill(0)
	oled_reset()

if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()
	if cmd == "SHUTDOWN":
		# Signal poweroff
		bus.write_byte(ADDR_FAN,0xFF)

		
	elif cmd == "FANOFF":
		# Turn off fan
		bus.write_byte(ADDR_FAN,0)
		if OLED_ENABLED == True:
			display_defaultimg()

	elif cmd == "SERVICE":
		# Starts the power button and temperature monitor threads
		try:
			ipcq = Queue()
			t1 = Thread(target = shutdown_check, args =(ipcq, ))

			t2 = Thread(target = temp_check)
			if OLED_ENABLED == True:
				t3 = Thread(target = display_loop, args =(ipcq, ))

			t1.start()
			t2.start()
			if OLED_ENABLED == True:
				t3.start()
			ipcq.join()
		except:
			GPIO.cleanup()

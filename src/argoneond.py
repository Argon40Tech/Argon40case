#!/usr/bin/python3


import sys
import datetime
import math

import os
import time

# Initialize I2C Bus
import smbus
import RPi.GPIO as GPIO

rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
	bus=smbus.SMBus(1)
else:
	bus=smbus.SMBus(0)


ADDR_RTC=0x51

#################
# Common/Helpers
#################

RTC_CONFIGFILE = "/etc/argoneonrtc.conf"

RTC_ALARM_BIT = 0x8
RTC_TIMER_BIT = 0x4

# PCF8563 number system Binary Coded Decimal (BCD)

# BCD to Decimal
def numBCDtoDEC(val):
	return (val & 0xf)+(((val >> 4) & 0xf)*10)

# Decimal to BCD
def numDECtoBCD(val):
	return (math.floor(val/10)<<4) + (val % 10)
	
# Check if Event Bit is raised
def hasRTCEventFlag(flagbit):
	bus.write_byte(ADDR_RTC,1)
	out = bus.read_byte_data(ADDR_RTC, 1)
	return (out & flagbit) != 0

# Clear Event Bit if raised
def clearRTCEventFlag(flagbit):
	out = bus.read_byte_data(ADDR_RTC, 1)
	if (out & flagbit) != 0:
		# Unset only if fired
		bus.write_byte_data(ADDR_RTC, 1, out&(0xff-flagbit))
		return True
	return False

# Enable Event Flag
def setRTCEventFlag(flagbit, enabled):
	# 0x10 = TI_TP flag, 0 by default
	ti_tp_flag = 0x10
	# flagbit=0x4 for timer flag, 0x1 for enable timer flag
	# flagbit=0x8 for alarm flag, 0x2 for enable alarm flag
	enableflagbit = flagbit>>2
	disableflagbit = 0
	if enabled == False:
		disableflagbit = enableflagbit
		enableflagbit = 0

	out = bus.read_byte_data(ADDR_RTC, 1)
	bus.write_byte_data(ADDR_RTC, 1, (out&(0xff-flagbit-disableflagbit - ti_tp_flag))|enableflagbit)

# Helper method to add proper suffix to numbers
def getNumberSuffix(numval):
	onesvalue = numval % 10
	if onesvalue == 1:
		return "st"
	elif onesvalue == 2:
		return "nd"
	elif onesvalue == 3:
		return "rd"
	return "th"

# Describe Timer Setting
def describeTimer(showsetting):
	out = bus.read_byte_data(ADDR_RTC, 14)
	tmp = out & 3
	if tmp == 3:
		outstr = " Minute(s)"
	elif tmp == 2:
		outstr = " Second(s)"
	elif tmp == 1:
		outstr = "/64th Second"
	elif tmp == 0:
		outstr = "/4096th Second"

	if (out & 0x80) != 0:
		out = bus.read_byte_data(ADDR_RTC, 15)
		return "Every "+(numBCDtoDEC(out)+1)+outstr
	elif showsetting == True:
		return "Disabled (Interval every 1"+outstr+")"
	# Setting might matter to save resources
	return "None"


def describeHourMinute(hour, minute):

	if hour < 0:
		return ""

	outstr = ""
	ampmstr = ""
	if hour <= 0:
		hour = 0
		outstr = outstr + "12"
		ampmstr = "am"
	elif hour <= 12:
		outstr = outstr + str(hour)
		if hour == 12:
			ampmstr = "pm"
		else:
			ampmstr = "am"
	else:
		outstr = outstr + str(hour-12)
		ampmstr = "pm"

	if minute >= 10:
		outstr = outstr+":"
	elif minute > 0:
		outstr = outstr+":0"
	else:
		if hour == 0:
			ampmstr = "mn"
		elif hour == 12:
			ampmstr = "nn"
		return outstr+ampmstr

	if minute <= 0:
		minute = 0
	outstr = outstr+str(minute)

	return outstr+ampmstr

# Describe Schedule Parameter Values
def describeSchedule(monthlist, weekdaylist, datelist, hourlist, minutelist):
	weekdaynamelist = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] 
	monthnamelist = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] 

	curprefix = ""
	hasDate = False
	hasMonth = False
	foundvalue = False
	monthdatestr = ""
	for curmonth in monthlist:
		for curdate in datelist:
			if curdate >= 0:
				hasDate = True
				if curmonth >= 0:
					hasMonth = True
					monthdatestr = monthdatestr + "," + monthnamelist[curmonth-1]+" "+str(curdate) + getNumberSuffix(curdate)
				else:
					monthdatestr = monthdatestr + ","+str(curdate) + getNumberSuffix(curdate)
			else:
				if curmonth >= 0:
					monthdatestr = monthdatestr + "," + monthnamelist[curmonth-1]

	if len(monthdatestr) > 0:
		foundvalue = True
		# Remove Leading Comma
		monthdatestr = monthdatestr[1:]
		if hasMonth == True:
			curprefix = "Annually:"
		else:
			curprefix = "Monthly:"
			monthdatestr = monthdatestr + " of the Month"
		monthdatestr = " Every "+monthdatestr

	weekdaystr = ""
	for curweekday in weekdaylist:
		if curweekday >= 0:
			hasDate = True
			weekdaystr = weekdaystr + "," + weekdaynamelist[curweekday]

	if len(weekdaystr) > 0:
		foundvalue = True
		# Remove Leading Comma
		weekdaystr = weekdaystr[1:]
		if len(curprefix) == 0:
			curprefix = "Weekly:"
			weekdaystr = " on " + weekdaystr
		else:
			weekdaystr = ",on " + weekdaystr

	hasHour = False
	hasMinute = False
	hourminstr = ""
	for curhour in hourlist:
		for curminute in minutelist:
			if curhour >= 0:
				hasHour = True
				if curminute >= 0:
					hasMinute = True
				hourminstr = hourminstr + "," + describeHourMinute(curhour, curminute)
			elif curminute >= 0:
				hasMinute = True
				hourminstr = hourminstr + "," + str(curminute) + getNumberSuffix(curminute)
	
	if len(hourminstr) > 0:
		foundvalue = True
		# Remove Leading Comma
		hourminstr = hourminstr[1:]
		if hasHour == True:
			if hasDate == True:
				hourminstr = "at " + hourminstr
			else:
				hourminstr = "Daily: " + hourminstr
			if hasMinute == False:
				hourminstr = hourminstr + " every minute"
		else:
			if hourminstr == "0":
				hourminstr = "At the start of every hour"
			else:
				hourminstr = "Hourly: At " + hourminstr + " minute"
	else:
		hourminstr = "Every minute"

	if len(curprefix) > 0:
		hourminstr = ","+hourminstr

	return (curprefix + monthdatestr + weekdaystr + hourminstr).strip()


# Describe Alarm Setting
def describeAlarm():
	minute = -1
	hour = -1
	date = -1
	weekday = -1

	out = bus.read_byte_data(ADDR_RTC, 9)
	if (out & 0x80) == 0:
		minute = numBCDtoDEC(out & 0x7f)

	out = bus.read_byte_data(ADDR_RTC, 10)
	if (out & 0x80) == 0:
		hour = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte_data(ADDR_RTC, 11)
	if (out & 0x80) == 0:
		date = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte_data(ADDR_RTC, 12)
	if (out & 0x80) == 0:
		weekday = numBCDtoDEC(out & 0x7)

	if weekday < 0 and date < 0 and hour < 0 and minute < 0:
		return "None"

	# Convert from UTC
	utcschedule = describeSchedule([-1], [weekday], [date], [hour], [minute])
	weekday, date, hour, minute = convertAlarmTimezone(weekday, date, hour, minute, False)

	return describeSchedule([-1], [weekday], [date], [hour], [minute]) + " Local (RTC Schedule: "+utcschedule+" UTC)"


# Describe Control Flags
def describeControlRegisters():
	out = bus.read_byte_data(ADDR_RTC, 1)

	print("\n***************")
	print("Control Status 2")
	print("\tTI_TP Flag:", ((out & 0x10) != 0))
	print("\tAlarm Flag:", ((out & RTC_ALARM_BIT) != 0),"( Enabled =", (out & (RTC_ALARM_BIT>>2)) != 0, ")")
	print("\tTimer Flag:", ((out & RTC_TIMER_BIT) != 0),"( Enabled =", (out & (RTC_TIMER_BIT>>2)) != 0, ")")

	print("Alarm Setting:")
	print("\t"+describeAlarm())

	print("Timer Setting:")
	print("\t"+describeTimer(True))

	print("***************\n")


#########
# Alarm
#########

# Alarm to UTC/Local time
def convertAlarmTimezone(weekday, date, hour, minute, toutc):
	utcdiffsec = getLocaltimeOffset().seconds
	if toutc == False:
		utcdiffsec = utcdiffsec*(-1)

	utcdiffsec = utcdiffsec - (utcdiffsec%60)
	utcdiffmin = utcdiffsec % 3600
	utcdiffhour = int((utcdiffsec - utcdiffmin)/3600)
	utcdiffmin = int(utcdiffmin/60)

	addhour = 0
	if minute >= 0:
		minute = minute - utcdiffmin
		if minute < 0:
			addhour = -1
			minute = minute + 60
		elif minute > 59:
			addhour = 1
			minute = minute - 60
	
	addday = 0
	if hour >= 0:
		hour = hour - utcdiffhour
		tmphour = hour + addhour
		if hour < 0:
			hour = hour + 24
		elif hour > 23:
			hour = hour - 24
		if tmphour < 0:
			addday = -1
		elif tmphour > 23:
			addday = 1

	if addday != 0:
		if weekday >= 0:
			weekday = weekday + addday
			if weekday < 0:
				weekday = weekday + 7
			elif weekday > 6:
				weekday = weekday - 7
		if date > 0:
			# Edge cases might not be handled properly though
			curtime = datetime.datetime.now()
			maxmonthdate = getLastMonthDate(curtime.year, curtime.month)
			date = date + addday
			if date == 0:
				# move to end of the month
				date = maxmonthdate
			elif date > maxmonthdate:
				# move to next month
				date = 1

	return [weekday, date, hour, minute]

# Check if RTC Alarm Flag is ON
def hasRTCAlarmFlag():
	return hasRTCEventFlag(RTC_ALARM_BIT)

# Clear RTC Alarm Flag
def clearRTCAlarmFlag():
	return clearRTCEventFlag(RTC_ALARM_BIT)

# Enables RTC Alarm Register
def enableAlarm(registeraddr, value, mask):
	# 0x00 is Enabled
	bus.write_byte_data(ADDR_RTC, registeraddr, (numDECtoBCD(value)&mask))

# Disables RTC Alarm Register
def disableAlarm(registeraddr):
	# 0x80 is disabled
	bus.write_byte_data(ADDR_RTC, registeraddr, 0x80)

# Removes all alarm settings
def removeRTCAlarm():
	setRTCEventFlag(RTC_ALARM_BIT, False)

	disableAlarm(9)
	disableAlarm(10)
	disableAlarm(11)
	disableAlarm(12)

# Set RTC Alarm (Negative values ignored)
def setRTCAlarm(enableflag, weekday, date, hour, minute):
	if date < 1 and weekday < 0 and hour < 0 and minute < 0:
		return -1
	elif minute > 59:
		return -1
	elif hour > 23:
		return -1
	elif weekday > 6:
		return -1
	elif date > 31:
		return -1

	# Convert to UTC
	weekday, date, hour, minute = convertAlarmTimezone(weekday, date, hour, minute, True)

	clearRTCAlarmFlag()
	setRTCEventFlag(RTC_ALARM_BIT, enableflag)

	if minute >= 0:
		enableAlarm(9, minute, 0x7f)
	else:
		disableAlarm(9)

	if hour >= 0:
		enableAlarm(10, hour, 0x7f)
	else:
		disableAlarm(10)

	if date >= 0:
		enableAlarm(11, date, 0x7f)
	else:
		disableAlarm(11)

	if weekday >= 0:
		enableAlarm(12, weekday, 0x7f)
	else:
		disableAlarm(12)

	return 0

# Set RTC Hourly Alarm
def setRTCAlarmHourly(enableflag, minute):
	return setRTCAlarm(enableflag, -1, -1, -1, minute)

# Set RTC Daily Alarm
def setRTCAlarmDaily(enableflag, hour, minute):
	return setRTCAlarm(enableflag, -1, -1, hour, minute)

# Set RTC Weekly Alarm
def setRTCAlarmWeekly(enableflag, dayofweek, hour, minute):
	return setRTCAlarm(enableflag, dayofweek, -1, hour, minute)

# Set RTC Monthly Alarm
def setRTCAlarmMonthly(enableflag, date, hour, minute):
	return setRTCAlarm(enableflag, -1, date, hour, minute)

#########
# Timer
#########

# Check if RTC Timer Flag is ON
def hasRTCTimerFlag():
	return hasRTCEventFlag(RTC_TIMER_BIT)

# Clear RTC Timer Flag
def clearRTCTimerFlag():
	return clearRTCEventFlag(RTC_TIMER_BIT)

# Remove RTC Timer Setting
def removeRTCTimer():
	setRTCEventFlag(RTC_TIMER_BIT, False)

	# Timer disable and Set Timer frequency to lowest (0x3=1 per minute)
	bus.write_byte_data(ADDR_RTC, 14, 3)
	bus.write_byte_data(ADDR_RTC, 15, 0)

# Set RTC Timer Interval
def setRTCTimerInterval(enableflag, value, inSeconds = False):
	if value > 255 or value < 1:
		return -1
	clearRTCTimerFlag()
	setRTCEventFlag(RTC_TIMER_BIT, enableflag)

	# 0x80 Timer Enabled, mode: 0x3=1/Min, 0x2=1/Sec, 0x1=Per 64th Sec, 0=Per 4096th Sec
	timerconfigFlag = 0x83
	if inSeconds == True:
		timerconfigFlag = 0x82

	bus.write_byte_data(ADDR_RTC, 14, timerconfigFlag)
	bus.write_byte_data(ADDR_RTC, 15, numDECtoBCD(value&0xff))
	return 0

#############
# Date/Time
#############

# Get local time vs UTC
def getLocaltimeOffset():
	localdatetime = datetime.datetime.now()
	utcdatetime = datetime.datetime.fromtimestamp(localdatetime.timestamp(), datetime.timezone.utc)
	# Remove TZ info to allow subtraction
	utcdatetime = utcdatetime.replace(tzinfo = None)

	return localdatetime - utcdatetime

# Returns RTC timestamp as datetime object
def getRTCdatetime():

	# Data Sheet Recommends to read this manner (instead of from registers)
	bus.write_byte(ADDR_RTC,2)

	out = bus.read_byte(ADDR_RTC)
	out = numBCDtoDEC(out & 0x7f)
	second = out
	#warningflag = (out & 0x80)>>7

	out = bus.read_byte(ADDR_RTC)
	minute = numBCDtoDEC(out & 0x7f)

	out = bus.read_byte(ADDR_RTC)
	hour = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte(ADDR_RTC)
	date = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte(ADDR_RTC)
	#weekDay = numBCDtoDEC(out & 7)

	out = bus.read_byte(ADDR_RTC)
	month = numBCDtoDEC(out & 0x1f)

	out = bus.read_byte(ADDR_RTC)
	year = numBCDtoDEC(out)

	#print({"year":year, "month": month, "date": date, "hour": hour, "minute": minute, "second": second})

	if month == 0:
		# Reset, uninitialized RTC
		month = 1

	# Timezone is GMT/UTC +0
	# Year is from 2000
	try:
		return datetime.datetime(year+2000, month, date, hour, minute, second)+getLocaltimeOffset()
	except:
		return datetime.datetime(2000, 1, 1, 0, 0, 0)

# set RTC time using datetime object (Local time)
def setRTCdatetime(localdatetime):
	# Set local time to UTC
	localdatetime = localdatetime - getLocaltimeOffset()

	# python Sunday = 6, RTC Sunday = 0
	weekDay = localdatetime.weekday()
	if weekDay == 6:
		weekDay = 0
	else:
		weekDay = weekDay + 1

	# Write to respective registers
	bus.write_byte_data(ADDR_RTC,2,numDECtoBCD(localdatetime.second))
	bus.write_byte_data(ADDR_RTC,3,numDECtoBCD(localdatetime.minute))
	bus.write_byte_data(ADDR_RTC,4,numDECtoBCD(localdatetime.hour))
	bus.write_byte_data(ADDR_RTC,5,numDECtoBCD(localdatetime.day))
	bus.write_byte_data(ADDR_RTC,6,numDECtoBCD(weekDay))
	bus.write_byte_data(ADDR_RTC,7,numDECtoBCD(localdatetime.month))

	# Year is from 2000
	bus.write_byte_data(ADDR_RTC,8,numDECtoBCD(localdatetime.year-2000))

# Sync Time to RTC Time (for Daemon use)
def syncSystemTime():
	rtctime = getRTCdatetime()
	os.system("date -s '"+rtctime.isoformat()+"' >/dev/null 2>&1")


#########
# Config 
#########

# Load config value as array of integers
def getConfigValue(valuestr):
	try:
		if valuestr == "*":
			return [-1]
		tmplist = valuestr.split(",")
		map_object = map(int, tmplist)
		return list(map_object)
	except:
		return [-1]

# Load config line data as array of Command schedule
def newCommandSchedule(curline):
	result = []
	linedata = curline.split(" ")
	if len(linedata) < 6:
		return result

	minutelist = getConfigValue(linedata[0])
	hourlist = getConfigValue(linedata[1])
	datelist = getConfigValue(linedata[2])
	#monthlist = getConfigValue(linedata[3])
	monthlist = [-1] # Certain edge cases will not be handled properly
	weekdaylist = getConfigValue(linedata[4])

	cmd = ""
	ctr = 5
	while ctr < len(linedata):
		cmd = cmd + " " + linedata[ctr]
		ctr = ctr + 1
	cmd = cmd.strip()

	for curmin in minutelist:
		for curhour in hourlist:
			for curdate in datelist:
				for curmonth in monthlist:
					for curweekday in weekdaylist:
						result.append({ "minute": curmin, "hour": curhour, "date": curdate, "month":curmonth, "weekday": curweekday, "cmd":cmd })

	return result

# Save updated config file
def saveConfigList(fname, configlist):
	f = open(fname, "w")
	f.write("#\n")
	f.write("# Argon RTC Configuration\n")
	f.write("# - Follows cron general format, but with only * and csv support\n")
	f.write("# - Each row follows the following format:\n")
	f.write("#      min hour date month dayOfWeek Command\n")
	f.write("#      e.g. Shutdown daily at 1am\n")
	f.write("#            0 1 * * * off\n")
	f.write("#           Shutdown daily at 1am and 1pm\n")
	f.write("#            0 1,13 * * * off\n")
	f.write("# - Commands are currently on or off only\n")
	f.write("# - Limititations\n")
	f.write("#      Requires MINUTE value\n")
	f.write("#      Month values are ignored (edge cases not supported)\n")
	f.write("#\n")

	for config in configlist:
		f.write(config+"\n")
	f.close()

# Remove config line
def removeConfigEntry(fname, entryidx):
	configlist = loadConfigList(fname)
	if len(configlist) > entryidx:
		configlist.pop(entryidx)
	saveConfigList(fname, configlist)

# Load config list (removes invalid data)
def loadConfigList(fname):
	try:
		result = []
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				curline = curline.strip().replace('\t', ' ')
				# Handle special characters that get encoded
				tmpline = "".join([c if 0x20<=ord(c) and ord(c)<=0x7e else "" for c in curline])

				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				checkdata = tmpline.split(" ")
				if len(checkdata) > 5:
					# Don't include every minute type of schedule
					if checkdata[0] != "*":
						result.append(tmpline)
		return result
	except:
		return []

# Form Command Schedule list from config list 
def formCommandScheduleList(configlist):
	try:
		result = []
		for config in configlist:
			result = result + newCommandSchedule(config)
		return result
	except:
		return []

# Describe config list entry
def describeConfigListEntry(configlistitem):
	linedata = configlistitem.split(" ")
	if len(linedata) < 6:
		return ""

	minutelist = getConfigValue(linedata[0])
	hourlist = getConfigValue(linedata[1])
	datelist = getConfigValue(linedata[2])
	#monthlist = getConfigValue(linedata[3])
	monthlist = [-1] # Certain edge cases will not be handled properly
	weekdaylist = getConfigValue(linedata[4])

	cmd = ""
	ctr = 5
	while ctr < len(linedata):
		cmd = cmd + " " + linedata[ctr]
		ctr = ctr + 1
	cmd = cmd.strip().lower()
	if cmd == "on":
		cmd = "Startup"
	else:
		cmd = "Shutdown"

	return cmd+" | "+describeSchedule(monthlist, weekdaylist, datelist, hourlist, minutelist)

# Describe config list and show indices
def describeConfigList(fname):
	# 1 is reserved for New schedule
	ctr = 2
	configlist = loadConfigList(fname)
	for config in configlist:
		tmpline = describeConfigListEntry(config)
		if len(tmpline) > 0:
			print("  "+str(ctr)+". ", tmpline)
			ctr = ctr + 1
	if ctr == 2:
		print("  No Existing Schedules")

# Check Command schedule if it should fire for the give time
def checkDateForCommandSchedule(commandschedule, datetimeobj):
	testminute = commandschedule.get("minute", -1)
	testhour = commandschedule.get("hour", -1)
	testdate = commandschedule.get("date", -1)
	testmonth = commandschedule.get("month", -1)
	testweekday = commandschedule.get("weekday", -1)

	if testminute < 0 or testminute == datetimeobj.minute:
		if testhour < 0 or testhour == datetimeobj.hour:
			if testdate < 0 or testdate == datetimeobj.day:
				if testmonth < 0 or testmonth == datetimeobj.month:
					if testweekday < 0:
						return True
					else:
						# python Sunday = 6, RTC Sunday = 0
						weekDay = datetimeobj.weekday()
						if weekDay == 6:
							weekDay = 0
						else:
							weekDay = weekDay + 1
						if testweekday == weekDay:
							return True
	return False

# Get current command
def getCommandForTime(commandschedulelist, datetimeobj, checkcmd):
	ctr = 0
	while ctr < len(commandschedulelist):
		testcmd = commandschedulelist[ctr].get("cmd", "")
		if (testcmd.lower() == checkcmd or len(checkcmd) == 0) and len(testcmd) > 0:
			if checkDateForCommandSchedule(commandschedulelist[ctr], datetimeobj) == True:
				return testcmd
		ctr = ctr + 1
	return ""

# Get Last Date of Month
def getLastMonthDate(year, month):
	if month < 12:
		testtime = datetime.datetime(year, month+1, 1)
	else:
		testtime = datetime.datetime(year+1, 1, 1)
	testtime = testtime - datetime.timedelta(days=1)
	return testtime.day

# Increment to the next iteration of command schedule
def incrementCommandScheduleTime(commandschedule, testtime, addmode):
	testminute = commandschedule.get("minute", -1)
	testhour = commandschedule.get("hour", -1)
	testdate = commandschedule.get("date", -1)
	testmonth = commandschedule.get("month", -1)
	testweekday = commandschedule.get("weekday", -1)

	if addmode == "minute":
		testfield = commandschedule.get(addmode, -1)
		if testfield < 0:
			if testtime.minute < 59:
				return testtime + datetime.timedelta(minutes=1)
			else:
				return incrementCommandScheduleTime(commandschedule, testtime.replace(minute=0), "hour")
		else:
			return incrementCommandScheduleTime(commandschedule, testtime, "hour")
	elif addmode == "hour":
		testfield = commandschedule.get(addmode, -1)
		if testfield < 0:
			if testtime.hour < 23:
				return testtime + datetime.timedelta(hours=1)
			else:
				return incrementCommandScheduleTime(commandschedule, testtime.replace(hour=0), "date")
		else:
			return incrementCommandScheduleTime(commandschedule, testtime, "date")
	elif addmode == "date":
		testfield = commandschedule.get(addmode, -1)
		if testfield < 0:
			maxmonthdate = getLastMonthDate(testtime.year, testtime.month)
			if testtime.day < maxmonthdate:
				return testtime + datetime.timedelta(days=1)
			else:
				return incrementCommandScheduleTime(commandschedule, testtime.replace(day=1), "month")
		else:
			return incrementCommandScheduleTime(commandschedule, testtime, "month")
	elif addmode == "month":
		testfield = commandschedule.get(addmode, -1)
		if testfield < 0:
			nextmonth = testtime.month
			nextyear = testtime.year
			while True:
				if nextmonth < 12:
					nextmonth = nextmonth + 1
				else:
					nextmonth = 1
					nextyear = nextyear + 1
				maxmonthdate = getLastMonthDate(nextyear, nextmonth)
				if testtime.day <= maxmonthdate:
					return testtime.replace(month=nextmonth, year=nextyear)
		else:
			return incrementCommandScheduleTime(commandschedule, testtime, "year")
	else:
		# Year
		if testtime.month == 2 and testtime.day == 29:
			# Leap day handling
			nextyear = testtime.year
			while True:
				nextyear = nextyear + 1
				maxmonthdate = getLastMonthDate(nextyear, testtime.month)
				if testtime.day <= maxmonthdate:
					return testtime.replace(year=nextyear)
		else:
			return testtime.replace(year=(testtime.year+1))

# Set Next Alarm on RTC
def setNextAlarm(commandschedulelist, prevdatetime):
	curtime = datetime.datetime.now()
	if prevdatetime > curtime:
		return prevdatetime

	# Divisible by 4 for leap day
	checklimityears = 12
	foundnextcmd = False
	nextcommandschedule = {}
	# To be sure it's later than any schedule
	nextcommandtime = curtime.replace(year=(curtime.year+checklimityears))

	ctr = 0
	while ctr < len(commandschedulelist):
		testcmd = commandschedulelist[ctr].get("cmd", "").lower()
		if testcmd == "on":
			invaliddata = False
			testminute = commandschedulelist[ctr].get("minute", -1)
			testhour = commandschedulelist[ctr].get("hour", -1)
			testdate = commandschedulelist[ctr].get("date", -1)
			testmonth = commandschedulelist[ctr].get("month", -1)
			testweekday = commandschedulelist[ctr].get("weekday", -1)

			tmpminute = testminute
			tmphour = testhour
			tmpdate = testdate
			tmpmonth = testmonth
			tmpyear = curtime.year

			if tmpminute < 0:
				tmpminute = curtime.minute

			if tmphour < 0:
				tmphour = curtime.hour

			if tmpdate < 0:
				tmpdate = curtime.day

			if tmpmonth < 0:
				tmpmonth = curtime.month

			maxmonthdate = getLastMonthDate(tmpyear, tmpmonth)
			if tmpdate > maxmonthdate:
				# Invalid month date
				if testdate < 0:
					tmpdate = maxmonthdate
				else:
					# Date is fixed
					if testminute < 0:
						tmpminute = 0
					if testhour < 0:
						tmphour = 0
					if testmonth < 0 and testdate <= 31:
						# Look for next valid month
						while tmpdate > maxmonthdate:
							if tmpmonth < 12:
								tmpmonth = tmpmonth + 1
							else:
								tmpmonth = 1
								tmpyear = tmpyear + 1
							maxmonthdate = getLastMonthDate(tmpyear, tmpmonth)
					elif tmpdate == 29 and tmpmonth == 2:
						# Fixed to leap day
						while tmpdate > maxmonthdate:
							tmpyear = tmpyear + 1
							maxmonthdate = getLastMonthDate(tmpyear, tmpmonth)
					else:
						invaliddata = True
			if invaliddata == False:
				try:
					testtime = datetime.datetime(tmpyear, tmpmonth, tmpdate, tmphour, tmpminute)
				except:
					# Force time diff
					testtime = curtime - datetime.timedelta(hours=1)
				tmptimediff = (curtime - testtime).total_seconds()
			else:
				tmptimediff = 0

			if testweekday >= 0:
				# Day of Week check
				# python Sunday = 6, RTC Sunday = 0
				weekDay = testtime.weekday()
				if weekDay == 6:
					weekDay = 0
				else:
					weekDay = weekDay + 1


				if weekDay != testweekday or tmptimediff > 0:
					# Resulting 0-ed time will be <= the testtime
					if testminute < 0:
						testtime = testtime.replace(minute=0)
					if testhour < 0:
						testtime = testtime.replace(hour=0)

					dayoffset = testweekday-weekDay
					if dayoffset < 0:
						dayoffset = dayoffset + 7
					elif dayoffset == 0:
						dayoffset = 7

					testtime = testtime + datetime.timedelta(days=dayoffset)

				# Just look for the next valid weekday; Can be optimized
				while checkDateForCommandSchedule(commandschedulelist[ctr], testtime) == False and (testtime.year - curtime.year) < checklimityears:
					testtime = testtime + datetime.timedelta(days=7)

				if (testtime.year - curtime.year) >= checklimityears:
					# Too many iterations, abort/ignore
					tmptimediff = 0
				else:
					tmptimediff = (curtime - testtime).total_seconds()
			if tmptimediff > 0:
				# Find next iteration that's greater than the current time (Day of Week check already handled)
				while tmptimediff >= 0:
					testtime = incrementCommandScheduleTime(commandschedulelist[ctr], testtime, "minute")
					tmptimediff = (curtime - testtime).total_seconds()

			if nextcommandtime > testtime and tmptimediff < 0:
				nextcommandschedule = commandschedulelist[ctr]
				nextcommandtime = testtime
				foundnextcmd = True


		ctr = ctr + 1
	if foundnextcmd == True:
		# Schedule Alarm
		if nextcommandschedule.get("weekday", -1) >=0 or nextcommandschedule.get("date", -1) > 0:
			# Set alarm based on hour/minute of next occurrence to factor in timezone changes if any
			setRTCAlarm(True, nextcommandschedule.get("weekday", -1), nextcommandschedule.get("date", -1), nextcommandtime.hour, nextcommandtime.minute)
		else:
			# no date,weekday involved just shift the hour and minute accordingly
			setRTCAlarm(True, nextcommandschedule.get("weekday", -1), nextcommandschedule.get("date", -1), nextcommandschedule.get("hour", -1), nextcommandschedule.get("minute", -1))
		return nextcommandtime
	else:
		removeRTCAlarm()
	# This will ensure that this will be replaced next iteration
	return curtime

######
if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()

	# Enable Alarm/Timer Flags
	enableflag = True

	if cmd == "CLEAN":
		removeRTCAlarm()
		removeRTCTimer()
	elif cmd == "SHUTDOWN":
		clearRTCAlarmFlag()
		clearRTCTimerFlag()

	elif cmd == "GETRTCTIME":
		print("RTC Time:", getRTCdatetime())

	elif cmd == "UPDATERTCTIME":
		setRTCdatetime(datetime.datetime.now())
		print("RTC Time:", getRTCdatetime())

	elif cmd == "GETSCHEDULELIST":
		describeConfigList(RTC_CONFIGFILE)

	elif cmd == "SHOWSCHEDULE":
		if len(sys.argv) > 2:
			if sys.argv[2].isdigit():
				# Display starts at 2, maps to 0-based index
				configidx = int(sys.argv[2])-2
				configlist = loadConfigList(RTC_CONFIGFILE)
				if len(configlist) > configidx:
					print ("  ",describeConfigListEntry(configlist[configidx]))
				else:
					print("   Invalid Schedule")

	elif cmd == "REMOVESCHEDULE":
		if len(sys.argv) > 2:
			if sys.argv[2].isdigit():
				# Display starts at 2, maps to 0-based index
				configidx = int(sys.argv[2])-2
				removeConfigEntry(RTC_CONFIGFILE, configidx)

	elif cmd == "SERVICE":
		syncSystemTime()
		commandschedulelist = formCommandScheduleList(loadConfigList(RTC_CONFIGFILE))
		nextrtcalarmtime = setNextAlarm(commandschedulelist, datetime.datetime.now())
		serviceloop = True
		while serviceloop==True:
			clearRTCAlarmFlag()
			clearRTCTimerFlag()

			tmpcurrenttime = datetime.datetime.now()
			if nextrtcalarmtime <= tmpcurrenttime:
				# Update RTC Alarm to next iteration
				nextrtcalarmtime = setNextAlarm(commandschedulelist, nextrtcalarmtime)
			elif len(getCommandForTime(commandschedulelist, tmpcurrenttime, "off")) > 0:
				# Shutdown detected, issue command then end service loop
				os.system("shutdown now -h")
				serviceloop = False
				# Don't break to sleep while command executes (prevents service to restart)
			

			time.sleep(60)


elif False:
	print("System Time: ", datetime.datetime.now())
	print("RTC    Time: ", getRTCdatetime())

	describeControlRegisters()

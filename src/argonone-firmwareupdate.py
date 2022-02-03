#!/usr/bin/python3

import urllib.request

import time
import smbus
import RPi.GPIO as GPIO

import serial
import os.path

# For finalization, location of binary to upload
firmwareurl = "https://download.argon40.com/argon1.bin"
firmwarefile = "/dev/shm/fwupdate.bin"

# Serial config
serialdev = "/dev/serial0"
serialrate = 115200
# Uncomment to write to file
#serialdev = ""

# Other Config
MAXRETRY = 0			# Ignore warnings 0, otherwise number of retry
ALWAYSDOWNLOAD = True	# Always download firmware from URL

# Display Packet Data
DUMPPACKETDATA = False

# Set Paths for data dump
TESTPACKETFILE = ""			# Dump packets sent/received
TESTTRANSFERFILE = ""		# Copy sent payload to file (should match source)

# Sample Output paths
#TESTPACKETFILE = "/dev/shm/fwtestpacket.bin"
#TESTTRANSFERFILE = "/dev/shm/fwtesttransfer.bin"


# Constants, no need to edit
I2CADDRESS = 0x1A
I2CCOMMAND = 0xBB
PACKETSIZE = 64

# Methods
def dumpPacket(packet, offset, dumpsize, dumpid, title = "Send Packet"):
	print(title, dumpid)
	idx = 0
	while idx < dumpsize:
		if idx % 8 == 0:
			if idx > 0:
				print("")
			print(getHexString(idx, 0), ":")
		print(getHexString(packet[offset+idx]))
		idx = idx + 1
	print("")

def dumpBytes(packet, offset, dumpsize, dumpid, title = "Receive Packet"):
	print(title, dumpid)
	idx = 0
	while idx < dumpsize:
		if idx % 8 == 0:
			if idx > 0:
				print("")
			print(getHexString(idx, 0), ":")
		print(getHexString(ord(packet[offset+idx])))
		idx = idx + 1
	print("")


def dumpFiledata(filename, fileoffset = 0, maxlength = 0):
	if len(filename) < 1:
		return
	ROWLEN = 8
	print("*** Dump ", filename)
	dumpfp = open(filename,"rb")
	bindata = dumpfp.read()
	dumpfp.close()

	packet = bytearray(ROWLEN)
	filesize = len(bindata)
	idx = fileoffset

	if maxlength > 0:
		dumpsize = idx + maxlength

	if dumpsize > filesize:
		dumpsize = filesize

	while idx < dumpsize:
		dumplen = ROWLEN
		if dumpsize - idx < dumplen:
			dumplen = dumpsize - idx

		print(getHexString(idx, 0), ":")
		while dumplen > 0 and idx < dumpsize:
			print(getHexString(ord(bindata[idx])))
			idx = idx + 1
			dumplen = dumplen - 1
		print("")

def getHexString(value, showbyte = 1):
	if showbyte == 1:
		return "0x{:02x}".format(value)
	return "0x{:08x}".format(value)


def readPacketWord(packet, offset):
	word = 0
	try:
		word = 0
		idx = 4
		while idx > 0:
			idx = idx - 1
			word = (word<<8) + ord(packet[offset + idx])
	except Exception as e:
		word = 0
		idx = 4
		while idx > 0:
			idx = idx - 1
			word = (word<<8) + int(packet[offset + idx])
	return word

def getPacketChecksum(packet, offset, length):
	checksum = 0
	idx = 0
	while idx < length:
		checksum = checksum + packet[offset+idx]
		idx = idx + 1
	return checksum

def writePacketWord(packet, offset, word):
	idx = 0
	while idx < 4:
		packet[offset + idx] = word & 0xff
		word = (word >> 8)
		idx = idx + 1

def writePacketBytes(packet, offset, bytedata, length):
	idx = 0
	while idx < length:
		packet[offset + idx] = bytedata[idx]
		idx = idx + 1

# i2c bus
rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
	bus = smbus.SMBus(1)
else:
	bus = smbus.SMBus(0)

if os.path.isfile(firmwarefile) == False or ALWAYSDOWNLOAD == True:
	print("Downloading Firmware ...")
	urllib.request.urlretrieve(firmwareurl,  firmwarefile)
	print("Download completed")


print("Preparing device...")
attemptcounter = 0
# Send update command to i2c
try:
	bus.write_byte(I2CADDRESS,I2CCOMMAND)
except:
	# Error at first attempt, I2C communication error
	print("Communication Failed.")
	attemptcounter = 100

while attemptcounter<3:
	try:
		time.sleep(1)
		bus.write_byte(I2CADDRESS,I2CCOMMAND)
		attemptcounter = attemptcounter + 1
	except:
		# I2C command failed, MCU in update mode
		print("Update Mode Enabled.")
		attemptcounter = 5

try:
	bus.close()
except:
	print("Communication Failure.")

if attemptcounter < 5:
	print("Error while trying to update.")
	print("Please try again or verify if device supports firmware update.")
	print("")
	exit()
elif attemptcounter > 5:
	print("Unable to connect to Argon Device.")
	print("Please check if device is configured properly.")
	print("")
	exit()


attemptcounter = 0
errorflag = 0
warningflag = 0
state = 0
if os.path.isfile(firmwarefile):
	state = 1		# File Exists
	datafp = open(firmwarefile,"rb")
	bindata = datafp.read()
	datafp.close()

	state = 2		# File loaded to Memory
	datatotal = len(bindata)

	print(datatotal, " bytes for processing")
	try:
		if len(serialdev) > 0:
			conn = serial.Serial(serialdev, serialrate, timeout=3)
			state = 3	# Serial Port Connected
		else:
			state = 4	# File mode

		packetid = 1
		dataidx = 0
		while dataidx < datatotal:

			# Form Packet Header
			packetdata = bytearray(PACKETSIZE)	# Initialize 64-byte packet of zeros (so no need to manually pad zeros)
			packetdataoffset = 8
			if packetid == 1:
				writePacketWord(packetdata, 0, 0xa0)
				writePacketWord(packetdata, 12, datatotal)
				packetdataoffset = 16
			writePacketWord(packetdata, 4, packetid)

			# Form data chunk
			packetendidx = PACKETSIZE 	# For debugging only
			dataidxend = dataidx+(PACKETSIZE-packetdataoffset)
			if dataidxend > datatotal:
				packetendidx = PACKETSIZE-(dataidxend-datatotal)
				dataidxend = datatotal

			writePacketBytes(packetdata, packetdataoffset, bindata[dataidx:dataidxend], dataidxend-dataidx)
			dataidx = dataidxend

			# Should be able to count end since it's all zeros
			datacrc = getPacketChecksum(packetdata, 0, PACKETSIZE)

			# Debug
			if DUMPPACKETDATA == True:
				dumpPacket(packetdata, 0, PACKETSIZE, packetid)

			# Log packets to file(s)
			testfpmode = "ab"		# Append by default
			if packetid == 1:
				testfpmode = "wb"	# First packet, don't append

			# Test Packets
			if TESTPACKETFILE != "":
				testfp = open(TESTPACKETFILE, testfpmode)
				testfp.write(packetdata)
				testfp.close()

			# Test Transfer Data
			if TESTTRANSFERFILE != "":
				testfp = open(TESTTRANSFERFILE, testfpmode)
				testfp.write(packetdata[packetdataoffset:packetendidx])
				testfp.close()

			# Send Packet Data
			if len(serialdev) > 0:
				state = 10
				conn.write(packetdata)
				state = 11
				outdata = conn.read(PACKETSIZE)
				if len(outdata) < PACKETSIZE:
					raise Exception("Serial read timeout")
					break

				state = 3

			else:
				packetdata = bytearray(PACKETSIZE)
				writePacketWord(packetdata, 0, datacrc)
				writePacketWord(packetdata, 4, packetid + 1)
				outdata = bytes(packetdata)

			# Log Packets
			testfpmode = "ab"
			if TESTPACKETFILE != "":
				testfp = open(TESTPACKETFILE, testfpmode)
				testfp.write(outdata)
				testfp.close()

			retpacketcrc = readPacketWord(outdata, 0)
			retpacketid = readPacketWord(outdata, 4)

			# Data Validation
			packetid = packetid + 1

			if DUMPPACKETDATA == True:
				dumpBytes(outdata, 0, PACKETSIZE, packetid)

			if retpacketcrc != datacrc:
				print("ERROR: CRC mismatch in packet ", (packetid - 1))
				print("\tCRC Expected: " + getHexString(datacrc))
				print("\tCRC Returned: " + getHexString(retpacketcrc))
				errorflag = 1

			if retpacketid != packetid:
				print("ERROR: ID mismatch in response packet ", (packetid - 1))
				print("\tID Expected:", (packetid))
				print("\tID Returned:", (retpacketid))
				errorflag = 1

			if errorflag == 1:
				if MAXRETRY > 0:
					attemptcounter = attemptcounter + 1
					if attemptcounter >= MAXRETRY:
						print("Too many failed attempts, aborting...")
						dataidx = datatotal	# Abort
					else:
						print("Restarting transmission...")
						dataidx = 0
						packetid = 0	# Restart
						errorflag = 0
				else:
					print("Ignoring errors, proceeding")
					warningflag = 1
					errorflag = 0

			# Next Packet ID
			packetid = packetid + 1

		if state == 3:
			conn.close()

		state = 200	# Completed
	except:
		if state == 2:
			print("Unable to connect to serial port "+serialdev+", please check permission or if serial is enabled")
		elif state == 3:
			print("Data processing error")
			conn.close()
		elif state == 10:
			print("Error writing to serial port")
		elif state == 11:
			print("Error reading from serial port")
		elif state == 4:
			print("Error during file I/O")
		state = -1

if state == 0:
	print("Firmware file not found")
elif state == 1:
	print("Unable to read file")
elif state == 200:
	if errorflag == 1:
		print("Failed to upload")
	elif warningflag == 1:
		print("Completed with warnings")
	else:
		print(dataidx, "bytes uploaded")


filedumpsize = 0
#filedumpsize = 160
if filedumpsize > 0:
	filedumpoffset = 0
	dumpFiledata(TESTPACKETFILE, filedumpoffset, filedumpsize)
	dumpFiledata(TESTTRANSFERFILE, filedumpoffset, filedumpsize)
	dumpFiledata(firmwarefile, filedumpoffset, filedumpsize)




#!/bin/bash
echo "----------------------"
echo " Argon Uninstall Tool"
echo "----------------------"
echo -n "Press Y to continue:"
read -n 1 confirm
echo
if [ "$confirm" = "y" ]
then
	confirm="Y"
fi

if [ "$confirm" != "Y" ]
then
	echo "Cancelled"
	exit
fi

shortcutfile="/home/pi/Desktop/argonone-config.desktop"
if [ -f "$shortcutfile" ]; then
	sudo rm $shortcutfile
	if [ -f "/usr/share/pixmaps/ar1config.png" ]; then
		sudo rm /usr/share/pixmaps/ar1config.png
	fi
	if [ -f "/usr/share/pixmaps/argoneon.png" ]; then
		sudo rm /usr/share/pixmaps/argoneon.png
	fi
fi


INSTALLATIONFOLDER=/etc/argon

argononefanscript=$INSTALLATIONFOLDER/argononed.py

if [ -f $argononefanscript ]; then
	sudo systemctl stop argononed.service
	sudo systemctl disable argononed.service

	# Turn off the fan
	/usr/bin/python3 $argononefanscript FANOFF

	# Remove files
	sudo rm /lib/systemd/system/argononed.service
fi

# Remove RTC if any
argoneonrtcscript=$INSTALLATIONFOLDER/argoneond.py
if [ -f "$argoneonrtcscript" ]
then
	# Disable Services
	sudo systemctl stop argoneond.service
	sudo systemctl disable argoneond.service

	# No need for sudo
	/usr/bin/python3 $argoneonrtcscript CLEAN
	/usr/bin/python3 $argoneonrtcscript SHUTDOWN

	# Remove files
	sudo rm /lib/systemd/system/argoneond.service
fi

sudo rm /usr/bin/argon-config

if [ -f "/usr/bin/argonone-config" ]
then
		sudo rm /usr/bin/argonone-config
		sudo rm /usr/bin/argonone-uninstall
		sudo rm /usr/bin/argonone-ir
fi

sudo rm /lib/systemd/system-shutdown/argon-shutdown.sh

sudo rm -R -f $INSTALLATIONFOLDER

echo "Removed Argon Services."
echo "Cleanup will complete after restarting the device."

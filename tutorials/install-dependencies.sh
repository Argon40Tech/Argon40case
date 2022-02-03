#!/bin/bash

argon_check_pkg() {
    RESULT=$(dpkg-query -W -f='${Status}\n' "$1" 2> /dev/null | grep "installed")

    if [ "" == "$RESULT" ]; then
        echo "NG"
    else
        echo "OK"
    fi
}

pkglist=(raspi-gpio python-rpi.gpio python3-rpi.gpio python-smbus python3-smbus i2c-tools)
for curpkg in ${pkglist[@]}; do
	sudo apt-get install -y $curpkg
	RESULT=$(argon_check_pkg "$curpkg")
	if [ "NG" == "$RESULT" ]
	then
		echo "********************************************************************"
		echo "Please also connect device to the internet and restart installation."
		echo "********************************************************************"
		exit
	fi
done

# Enable i2c and serial
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_serial 2

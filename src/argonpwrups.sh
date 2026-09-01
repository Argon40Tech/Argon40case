#!/bin/bash

echo "*************"
echo " Argon Setup  "
echo "*************"


# Check time if need to 'fix'
NEEDSTIMESYNC=0
LOCALTIME=$(date -u +%s%N | cut -b1-10)
GLOBALTIME=$(curl -s 'http://worldtimeapi.org/api/ip.txt' | grep unixtime | cut -b11-20)
TIMEDIFF=$((GLOBALTIME-LOCALTIME))

# about 26hrs, max timezone difference
if [ $TIMEDIFF -gt 100000 ]
then
	NEEDSTIMESYNC=1
fi


argon_time_error() {
	echo "**********************************************"
	echo "* WARNING: Device time seems to be incorrect *"
	echo "* This may cause problems during setup.      *"
	echo "**********************************************"
	echo "Possible Network Time Protocol Server issue"
	echo "Try running the following to correct:"
    echo " curl -k https://download.argon40.com/tools/setntpserver.sh | bash"
}

if [ $NEEDSTIMESYNC -eq 1 ]
then
	argon_time_error
fi


# Helper variables
ARGONDOWNLOADSERVER=https://download.argon40.com

INSTALLATIONFOLDER=/etc/argon

versioninfoscript=$INSTALLATIONFOLDER/argon-versioninfo.sh

uninstallscript=$INSTALLATIONFOLDER/argon-uninstall.sh
configscript=$INSTALLATIONFOLDER/argon-config

setupmode="Setup"

if [ -f $configscript ]
then
	setupmode="Update"
	echo "Updating files"
else
	sudo mkdir $INSTALLATIONFOLDER
	sudo chmod 755 $INSTALLATIONFOLDER
fi

##########
# Start code lifted from raspi-config
# is_pifive, get_serial_hw and do_serial_hw based on raspi-config

if [ -e /boot/firmware/config.txt ] ; then
  FIRMWARE=/firmware
else
  FIRMWARE=
fi
CONFIG=/boot${FIRMWARE}/config.txt

is_pifive() {
  grep -q "^Revision\s*:\s*[ 123][0-9a-fA-F][0-9a-fA-F]4[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$" /proc/cpuinfo
  return $?
}


get_serial_hw() {
  if is_pifive ; then
    if grep -q -E "dtparam=uart0=off" $CONFIG ; then
      echo 1
    elif grep -q -E "dtparam=uart0" $CONFIG ; then
      echo 0
    else
      echo 1
    fi
  else
    if grep -q -E "^enable_uart=1" $CONFIG ; then
      echo 0
    elif grep -q -E "^enable_uart=0" $CONFIG ; then
      echo 1
    elif [ -e /dev/serial0 ] ; then
      echo 0
    else
      echo 1
    fi
  fi
}

do_serial_hw() {
  if [ $1 -eq 0 ] ; then
    if is_pifive ; then
      set_config_var dtparam=uart0 on $CONFIG
    else
      set_config_var enable_uart 1 $CONFIG
    fi
  else
    if is_pifive ; then
      sudo sed $CONFIG -i -e "/dtparam=uart0.*/d"
    else
      set_config_var enable_uart 0 $CONFIG
    fi
  fi
}

# End code lifted from raspi-config
##########


set_config_var() {
	# Own version that writes to [all] section
	TARGET="$1=$2"

	# Ensure [all] section exists
	if ! grep -q "^\[all\]" "$3"; then
		echo "[all]" | sudo tee -a "$3" > /dev/null
	fi

	# Extract the [all] section
	ALL_SECTION=$(awk '
		/^\[all\]/ {in_all=1; next}
		/^\[/ && !/^\[all\]/ {in_all=0}
		in_all {print}
	' "$3")

	echo "$ALL_SECTION" | grep -q "^$TARGET$"
	EXISTS=$?

	if [ $EXISTS -ne 0 ]
	then
		TMPCONFIG="/dev/shm/tmpconfig.txt"

		# Append inside [all] section
		sudo awk -v target="$TARGET" '
			/^\[all\]/ {
				print
				in_all=1
				next
			}
			/^\[/ && in_all==1 {
				# We are leaving [all] section → append before next section
				print target
				in_all=0
			}
			{print}
			END {
				# If file ended while still in [all], append at end
				if (in_all==1) {
					print target
				}
			}
		' "$3" > "$TMPCONFIG"

		sudo tee "$3" < "$TMPCONFIG" > /dev/null
		sudo rm "$TMPCONFIG"
	fi
}


# Reuse is_pifive, set_config_var
set_nvme_default() {
  if is_pifive ; then
    set_config_var dtparam nvme $CONFIG
    set_config_var dtparam=pciex1_gen 3 $CONFIG
  fi
}
set_maxusbcurrent() {
  if is_pifive ; then
    #set_config_var max_usb_current 1 $CONFIG
    set_config_var usb_max_current_enable 1 $CONFIG
  fi
}


argon_check_pkg() {
    RESULT=$(dpkg-query -W -f='${Status}\n' "$1" 2> /dev/null | grep "installed")

    if [ "" == "$RESULT" ]; then
        echo "NG"
    else
        echo "OK"
    fi
}

CHECKGPIOMODE="libgpiod" # libgpiod or rpigpio

# Check if Raspbian, Ubuntu, others
CHECKPLATFORM="Others"
CHECKPLATFORMVERSION=""
CHECKPLATFORMVERSIONNUM=""
if [ -f "/etc/os-release" ]
then
	source /etc/os-release
	if [ "$ID" = "raspbian" ]
	then
		CHECKPLATFORM="Raspbian"
		CHECKPLATFORMVERSION=$VERSION_ID
	elif [ "$ID" = "debian" ]
	then
		# For backwards compatibility, continue using raspbian
		CHECKPLATFORM="Raspbian"
		CHECKPLATFORMVERSION=$VERSION_ID
	elif [ "$ID" = "ubuntu" ]
	then
		CHECKPLATFORM="Ubuntu"
		CHECKPLATFORMVERSION=$VERSION_ID
	fi
	echo ${CHECKPLATFORMVERSION} | grep -e "\." > /dev/null
	if [ $? -eq 0 ]
	then
		CHECKPLATFORMVERSIONNUM=`cut -d "." -f2 <<< $CHECKPLATFORMVERSION `
		CHECKPLATFORMVERSION=`cut -d "." -f1 <<< $CHECKPLATFORMVERSION `
	fi
fi

gpiopkg="python3-libgpiod"
if [ "$CHECKGPIOMODE" = "rpigpio" ]
then
	if [ "$CHECKPLATFORM" = "Raspbian" ]
	then
		gpiopkg="raspi-gpio python3-rpi.gpio"
	else
		gpiopkg="python3-rpi.gpio"
	fi
fi

if [ "$CHECKPLATFORM" = "Raspbian" ]
then
	pkglist=($gpiopkg python3-smbus i2c-tools)
else
	# Todo handle lgpio
	# Ubuntu has serial and i2c enabled
	pkglist=($gpiopkg python3-smbus i2c-tools)
fi

echo "Installing/updating dependencies..."

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

echo "Updating configuration ..."

# Ubuntu Mate for RPi has raspi-config too
command -v raspi-config &> /dev/null
if [ $? -eq 0 ]
then
	# Enable i2c and serial
	sudo raspi-config nonint do_i2c 0
	if [ "$CHECKPLATFORM" = "Raspbian" ]
	then
		# bookworm raspi-config prompts user when configuring serial
		if [ $(get_serial_hw) -eq 1 ]; then
			do_serial_hw 0
		fi
	else
		sudo raspi-config nonint do_serial 2
	fi
fi


# Additional config for pi5
set_nvme_default
set_maxusbcurrent

basename="argonone"
daemonname=$basename"d"
upsconfigscript=$INSTALLATIONFOLDER/${basename}-upsconfig.sh
eepromrpiscript="/usr/bin/rpi-eeprom-config"
eepromconfigscript=$INSTALLATIONFOLDER/${basename}-eepromconfig.py

echo "Installing/Updating scripts and services ..."

if [ -f "$eepromrpiscript" ]
then
	# EEPROM Config Script
	sudo wget $ARGONDOWNLOADSERVER/scripts/argon-rpi-eeprom-config-psu.py -O $eepromconfigscript --quiet
	sudo chmod 755 $eepromconfigscript
fi

# UPS Config Script
sudo wget $ARGONDOWNLOADSERVER/scripts/argonone-upsconfig.sh -O $upsconfigscript --quiet
sudo chmod 755 $upsconfigscript


for TMPDIRECTORY in "/lib/systemd/system" "/lib/systemd/system-shutdown"
do
	sudo mkdir -p "$TMPDIRECTORY"
	sudo chmod 755 $TMPDIRECTORY
	sudo chown root:root "$TMPDIRECTORY"
done

# Other utility scripts

sudo wget $ARGONDOWNLOADSERVER/scripts/argon-versioninfo.sh -O $versioninfoscript --quiet
sudo chmod 755 $versioninfoscript

# Argon Uninstall Script
sudo wget $ARGONDOWNLOADSERVER/scripts/argon-uninstall.sh -O $uninstallscript --quiet
sudo chmod 755 $uninstallscript

sudo ln -s $upsconfigscript $configscript


configcmd="$(basename -- $configscript)"

echo "Initializing Services ..."

if [ "$setupmode" = "Setup" ]
then
	if [ -f "/usr/bin/$configcmd" ]
	then
		sudo rm /usr/bin/$configcmd
	fi
	sudo ln -s $upsconfigscript /usr/bin/$configcmd
fi

# Trigger UPS Config Installation sequence
$upsconfigscript "setupmode"


if [ "$CHECKPLATFORM" = "Raspbian" ]
then
	if [ -f "$eepromrpiscript" ]
	then
		echo "Checking EEPROM ..."
		sudo apt-get update && sudo apt-get upgrade -y
		sudo rpi-eeprom-update
		# EEPROM Config Script
		sudo $eepromconfigscript
	fi
else
	echo "WARNING: EEPROM not updated.  Please run this under Raspberry Pi OS"
fi


echo "*********************"
echo "  $setupmode Completed "
echo "*********************"
$versioninfoscript
echo
echo "Use '$configcmd' to configure device"
echo


if [ $NEEDSTIMESYNC -eq 1 ]
then
	argon_time_error
fi


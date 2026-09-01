#!/bin/bash

echo "*************"
echo " Argon Setup  "
echo "*************"

# Helper variables
ARGONDOWNLOADSERVER=https://download.argon40.com

eepromrpiscript="/usr/bin/rpi-eeprom-config"
eepromconfigscript=/dev/shm/argon-eeprom.py

# Check if Raspbian, Ubuntu, others
CHECKPLATFORM="Others"
if [ -f "/etc/os-release" ]
then
	source /etc/os-release
	if [ "$ID" = "raspbian" ]
	then
		CHECKPLATFORM="Raspbian"
	elif [ "$ID" = "debian" ]
	then
		# For backwards compatibility, continue using raspbian
		CHECKPLATFORM="Raspbian"
	elif [ "$ID" = "ubuntu" ]
	then
		CHECKPLATFORM="Ubuntu"
	fi
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

echo "Updating configuration ..."

# Additional config for pi5
set_nvme_default
set_maxusbcurrent


# Check if original eeprom script exists before running
if [ "$CHECKPLATFORM" = "Raspbian" ]
then
  if [  -f "$eepromrpiscript" ]
  then
		echo "Checking EEPROM ..."
    sudo apt-get update && sudo apt-get upgrade -y
    sudo rpi-eeprom-update
    # EEPROM Config Script
    sudo wget $ARGONDOWNLOADSERVER/scripts/argon-rpi-eeprom-config-default.py -O $eepromconfigscript --quiet
    sudo chmod 755 $eepromconfigscript
    sudo $eepromconfigscript
  fi
else
	echo "WARNING: EEPROM not updated.  Please run this under Raspberry Pi OS"
fi



echo "*********************"
echo "  Setup Completed "
echo "*********************"
echo
echo "Please reboot for changes to take effect"

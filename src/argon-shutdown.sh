#!/bin/bash

pythonbin=/usr/bin/python3
argononefanscript=/etc/argon/argononed.py
argoneonrtcscript=/etc/argon/argoneond.py

if [ ! -z "$1" ]
then
	$pythonbin $argononefanscript FANOFF
	if [ "$1" = "poweroff" ] || [ "$1" = "halt" ]
	then
		if [ -f $argoneonrtcscript ]
		then
			$pythonbin $argoneonrtcscript SHUTDOWN
		fi
		$pythonbin $argononefanscript SHUTDOWN
	fi
fi

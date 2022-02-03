#!/bin/bash

daemonconfigfile=/etc/argononed.conf

echo "------------------------------------"
echo " Argon Fan Speed Configuration Tool"
echo "------------------------------------"
echo "WARNING: This will remove existing configuration."
echo -n "Press Y to continue:"
read -n 1 confirm
echo


fanloopflag=1
newmode=0
if [ "$confirm" = "y" ]
then
	confirm="Y"
fi

if [ "$confirm" != "Y" ]
then
	fanloopflag=0
	echo "Cancelled."
else
	echo "Thank you."
fi

get_number () {
	read curnumber
	if [ -z "$curnumber" ]
	then
		echo "-2"
		return
	elif [[ $curnumber =~ ^[+-]?[0-9]+$ ]]
	then
		if [ $curnumber -lt 0 ]
		then
			echo "-1"
			return
		elif [ $curnumber -gt 100 ]
		then
			echo "-1"
			return
		fi	
		echo $curnumber
		return
	fi
	echo "-1"
	return
}

while [ $fanloopflag -eq 1 ]
do
	echo
	echo "Select fan mode:"
	echo "  1. Always on"
	echo "  2. Adjust to temperatures (55C, 60C, and 65C)"
	echo "  3. Customize behavior"
	echo
	echo "  0. Exit"
	echo "NOTE: You can also edit $daemonconfigfile directly"
	echo -n "Enter Number (0-3):"
	newmode=$( get_number )

	if [[ $newmode -eq 0 ]]
	then
		fanloopflag=0
	elif [ $newmode -eq 1 ]
	then
		echo "#" > $daemonconfigfile
		echo "# Argon One Fan Speed Configuration" >> $daemonconfigfile
		echo "#" >> $daemonconfigfile
		echo "# Min Temp=Fan Speed" >> $daemonconfigfile
		echo 1"="100 >> $daemonconfigfile
		sudo systemctl restart argononed.service
		echo "Fan always on."
	elif [ $newmode -eq 2 ]
	then
		echo "Please provide fan speeds for the following temperatures:"
		echo "#" > $daemonconfigfile
		echo "# Argon One Fan Speed Configuration" >> $daemonconfigfile
		echo "#" >> $daemonconfigfile
		echo "# Min Temp=Fan Speed" >> $daemonconfigfile
		curtemp=55
		while [ $curtemp -lt 70 ]
		do
			errorfanflag=1
			while [ $errorfanflag -eq 1 ]
			do
				echo -n ""$curtemp"C (0-100 only):"
				curfan=$( get_number )
				if [ $curfan -ge 0 ]
				then
					errorfanflag=0
				fi
			done
			echo $curtemp"="$curfan >> $daemonconfigfile
			curtemp=$((curtemp+5))
		done

		sudo systemctl restart argononed.service
		echo "Configuration updated."
	elif [ $newmode -eq 3 ]
	then
		echo "Please provide fan speeds and temperature pairs"
		echo

		subloopflag=1
		paircounter=0
		while [ $subloopflag -eq 1 ]
		do
			errortempflag=1
			errorfanflag=1
			echo "(You may set a blank value to end configuration)"
			while [ $errortempflag -eq 1 ]
			do
				echo -n "Provide minimum temperature (in Celsius) then [ENTER]:"
				curtemp=$( get_number )
				if [ $curtemp -ge 0 ]
				then
					errortempflag=0
				elif [ $curtemp -eq -2 ]
				then
					errortempflag=0
					errorfanflag=0
					subloopflag=0
				fi
			done
			while [ $errorfanflag -eq 1 ]
			do
				echo -n "Provide fan speed for "$curtemp"C (0-100) then [ENTER]:"
				curfan=$( get_number )
				if [ $curfan -ge 0 ]
				then
					errorfanflag=0
				elif [ $curfan -eq -2 ]
				then
					errortempflag=0
					errorfanflag=0
					subloopflag=0
				fi
			done
			if [ $subloopflag -eq 1 ]
			then
				if [ $paircounter -eq 0 ]
				then
					echo "#" > $daemonconfigfile
					echo "# Argon Fan Configuration" >> $daemonconfigfile
					echo "#" >> $daemonconfigfile
					echo "# Min Temp=Fan Speed" >> $daemonconfigfile
				fi
				echo $curtemp"="$curfan >> $daemonconfigfile
				
				paircounter=$((paircounter+1))
				
				echo "* Fan speed will be set to "$curfan" once temperature reaches "$curtemp" C"
				echo
			fi
		done

		echo
		if [ $paircounter -gt 0 ]
		then
			echo "Thank you!  We saved "$paircounter" pairs."
			sudo systemctl restart argononed.service
			echo "Changes should take effect now."
		else
			echo "Cancelled, no data saved."
		fi
	fi
done

echo


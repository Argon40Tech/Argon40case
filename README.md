# Argon40 Cases and HATs Scripts

The Argon40 Cases and HATs are the ergonomic and aesthetic case for the Raspberry Pi. This repository provides samples and references on how to customize our scripts and even create your own versions.  You can find out more about it on:
* [argon40.com](https://www.argon40.com/argon-one-raspberry-pi-4-case.html)
* [raspberrypi.org](https://www.raspberrypi.org/blog/argon-one-raspberry-pi-case/)
* [Magpi Magazine](https://magpi.raspberrypi.org/articles/argon-one-review)

## Official Installers
* [Argon ONE](https://download.argon40.com/argon1.sh)
* [Argon EON](https://download.argon40.com/argoneon.sh)


## Standard Mechanisms

Below are the basics on how Argon40 cases and HATs interacts with the Raspberry Pi to enhance the user's experience.  The scripts found in this repository are based on these mechanisms.

### Power Button Events

Cases that come with a power button can turn the computer on and off while ensuring that the files stored are safe.  It works by setting a pulse to BCM 4 (BOARD P7) depending on the action. The software that listens to these events should be able to react accordingly.
* Double Tap - 20-30ms pulse
* Hold and release after 3 seconds - 40-50ms pulse

### Fan Speed

The built-in fan can be controlled via I2C commands. It's MCU (Micro Controller Unit) uses the address 0x1a (26 decimal value).  The fan speed values range from 0 to 100, corresponding to fan speed percentage.  The software can use the fan to manage the temperature as it sees fit.

### Power cut

With the aid of an I2C command, we can cut the power to the devices after shutdown. Sending 0xff (255 decimal value) to 0x1a address informs the MCU (Micro Controller Unit) to cut the power after the device completes shutdown. Device shutdown is detected when the serial pin goes 'down', so it's best that serial/UART is enabled on the Pi.

### IR Receiver/Transmitter

The board has placeholders for IR components.  The transmitter is connected to BCM 22 (BOARD P15), while the receiver is connected to BCM 23 (BOARD P16).


## Repository Files

Below is a summary of the files in this repository.  The codes will have comments in key sections that explain detailed contructs.

### src

Standard scripts and files used by primary daemon/services for reference.
```
Actual scripts installed vary depending on the OS.
```

### tutorials

Sample python scripts that can be ran to interact with Argon40 devices.  Some requires installation of the scripts while others won't work if Argon40 daemon(s) are running.  Please enable:
* I2C
* UART/Serial Port (for power cut)

## Support
Feel free to get in touch through cs@argon40.com if you have any questions.

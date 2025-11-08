# Dumb-Smart-Outlet-Timer
A DIY outlet timer for a Raspberry Pi Pico W, written in MicroPython.

## Disclaimers
I am not an electrical engineer [##Assembly] instructions are not intended to be a strict step-by-step tutorial, it is just a what I did.

No generative AI was used in the creation of this code or device, support real human work.

## Introduction
The Dumb Smart Outlet Timer is an outlet timer that is controlled with a Raspberry Pi Pico W. This is intended to be a cheap WiFi controlled timer that does not interface with a smart-home or require a propietary app to function (hence the dumb-smart). However it is configured via http string queries so it would be pretty easy to make it work with an app or smart-home setup. 

## Required Parts
- Raspberry Pi Pico W (Flashed with MicroPython version 1.26.1)
- A 3v relay that can switch 120v
- A fuze and fuze holder (use one that is the same or less amperage than your relay can handle)
- Old power surge protector (doesn't have to work, but make sure it is big enough to fit all parts inside)
- Sacraficial 5volt charger
- Wire (make sure it is the correct guage, rated for at least the same amperage as the fuze and relay)
- Solder
- Heat shrink
- Soldering Iron

## Setup 
1. Flash Raspberry Pi Pico W with [MicroPython version 1.26.1](https://micropython.org/download/RPI_PICO_W/), follow the guide on Mycropython website.
2. Using your IDE of choice, open main.py and enter your Wifi credentials in the correct spots at the top of the file.
3. Save to Raspberry Pi Pico W's internal storage, also open and save index.html and error.html
4. Run it from IDE to make sure it connects to your WiFi and get it's IP.
5. (Optional) Configure your router settings to set the Pico's new IP to be static. This will allow the Pico to retain the same ip indefinetly.

## Assembly

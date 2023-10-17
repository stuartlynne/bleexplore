# bleexplore.py
# Fri Aug 18 11:03:25 AM PDT 2023

## Overview

This is a Python test script to access and test responses from a range of BLE sensors
using the Python *BLEAK* library for Bluetooth. E.g. Heart Rate straps, Power meters,
FTMS trainers, etc.

This also attempts to demonstrate how to maintain a connection to a device when there
are connection failures, either due to the device reseting, interference, stack issues, etc.

## How to use

Run the script, optionally with enough of the device name to match. 

With one (or more) Polar devices active:
```
python bleexpolorer.py             # default to Polar 
python bleexpolorer.py Pola        # Match Polar
python bleexpolorer.py H10         # Match H10
python bleexpolorer.py 'Polar H10' # Match 'Polar H10'
```

The script will use *BleakScanner* to find all devices available and match each to see if it should explore.

To terminate the script use *Ctrl-C* to interrupt.

For each device found:
1. Connect 
2. Verify the PMD and PFC services are present
3. Get supported Feature list from the PFC service
4. Get the supported Measurements from the PMD service
5. For each supported Measurement start a sample stream
6. Wait for termination

## Contributors
- Stuart Lynne <stuart.lynne@gmail.com>


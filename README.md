# pypolartest
# Sun 02 Jul 2023 06:59:10 AM PDT

## Overview

This is a Python test script to access and test responses from a *Polar Electro Oy* device 
using the Python *BLEAK* library for Bluetooth.

The genesis of this script was a dialogue started in issue #360 at the Polar official *polar-ble-sdk* GitHub archive. 

That archive contains SKD's for *Android* and *IOS* applications. But does not support access to Polar Devices directly, 
as in this case from Python using Bleak to directly interact with the device.

While there are numerous partial examples demonstrating this it seemed useful to show as much as possible in 
a single script demonstrating only the Bluetooth access to Polar devices.

See: [polar-ble-sdk Issue 360 - PMD Control Point Respones)](https://github.com/polarofficial/polar-ble-sdk/issues/360)

Github repository: [pypolartest](https://github.com/stuartlynne/pypolartest)

## How to use

Run the script, optionally with enough of the device name to match. 

With one (or more) Polar devices active:
```
python polartest.py             # default to Polar 
python polartest.py Pola        # Match Polar
python polartest.py H10         # Match H10
python polartest.py 'Polar H10' # Match 'Polar H10'
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

## Tested devices

Currently tested with:
- Polar H10
- Polar OH1

The script can determine what data sources are available and demonstrate how to access them:

Currently tested with:

| Measurment | H10 | OH1 | Verity |
| ---------- | --- | --- | ------ |
| ECG        | yes |     |        |
| ACC        | yes | yes |        |
| PPG        |     | yes |        |
| PPI        | yes | yes |        |
| GYRO       |     |     |        |
| MAG        |     |     |        |

## Operation

```
python pypolartest.py
```
This will:
1. Scan for a Polar Device
2. Determine what type of device it is 
3. Determine what features are available
4. Open data stream for each of the available data sources.
5. Capture data for a short period of time
6. Exit

## Other open source projects

- [Polar SDK](https://github.com/polarofficial/polar-ble-sdk)
- [polarpy](https://github.com/wideopensource/polarpy)


## Polar Services
### - POLAR\_PMD\_SERVICE - Polar Measurement Data Service
```
[Service] fb005c80-02e7-f387-1cad-8acd2d8df0c8 (Handle: 45): POLAR_PMD_SERVICE
    [Characteristic] fb005c82-02e7-f387-1cad-8acd2d8df0c8 (Handle: 49): POLAR_PMD_DATA (notify), Value: None
        [Descriptor] 00002902-0000-1000-8000-00805f9b34fb (Handle: 51): Client Characteristic Configuration) | Value: 00 00
    [Characteristic] fb005c81-02e7-f387-1cad-8acd2d8df0c8 (Handle: 46): POLAR_PMD_CP (read,write,indicate), Value: 0f 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
        [Descriptor] 00002902-0000-1000-8000-00805f9b34fb (Handle: 48): Client Characteristic Configuration) | Value: 00 00
```

### POLAR\_PFC\_SERVICE - Polar Features Configuration Service
```
[Service] 6217ff4b-fb31-1140-ad5a-a45545d7ecf3 (Handle: 39): POLAR_PFC_SERVICE
    [Characteristic] 6217ff4d-91bb-91d0-7e2a-7cd3bda8a1f3 (Handle: 42): POLAR_PFC_CP (write-without-response,indicate), Value: None
        [Descriptor] 00002902-0000-1000-8000-00805f9b34fb (Handle: 44): Client Characteristic Configuration) | Value: 00 00
    [Characteristic] 6217ff4c-c8ec-b1fb-1380-3ad986708e2d (Handle: 40): POLAR_PFC_FEATURE (read), Value: bf 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

## Documentation
Most of the information used to implement this was from the (now withdrawn) documents in the Polar SDK Git Archive:
- SdkModeExplained.md
- Polar\_Measurement\_Data\_Specification.pdf

## Contributors
- Stuart Lynne <stuart.lynne@gmail.com>
- Guido Muesch <g.muesch@gmail.com>


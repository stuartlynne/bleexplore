#!/usr/bin/env python3
# 
# Copyright(c)2023 stuart.lynne@gmail.com
# Made available under the MIT License
# See LICENSE.md
#
## Contributors
# Stuart Lynne <stuart.lynne@gmail.com>
# Guido Muesch <g.muesch@gmail.com>
# 

import sys
import asyncio
import signal
from bleak import BleakClient
from bleak.exc import BleakError
from bleak.uuids import uuid16_dict, uuid128_dict, uuidstr_to_str, register_uuids

import platform
from functools import partial
from bleak import BleakScanner
from enum import Enum, IntEnum

import traceback

# some small helper functions
def bytes2str(bytes):
    return ' '.join(str('%02x'%b) for b in bytes)

# uuid_to_name - map uuid to uuid name
def uuid_to_name(uuid):
    return None if uuid is None else uuidstr_to_str(uuid)

def name_to_uuid(name):
    _name = name.lower()
    uuids = [ k for k, v in uuid128_dict.items() if v.lower() == _name ]
    if uuids is not None and len(uuids) > 0:
        return uuids[0]
    uuids = [ k for k, v in uuid16_dict.items() if v == name ]
    if uuids is None and len(uuids) < 1:
        return None
    uuid = f"0000{uuids[0]:x}-0000-1000-8000-00805f9b34fb"
    return uuid

# List of Polar UUIDS, register with Bleak
Polar_UUIDS = {
    "fb005c81-02e7-f387-1cad-8acd2d8df0c8": "POLAR_PMD_CP",
    "fb005c82-02e7-f387-1cad-8acd2d8df0c8": "POLAR_PMD_DATA",
    "fb005c80-02e7-f387-1cad-8acd2d8df0c8": "POLAR_PMD_SERVICE",
    "6217ff4b-fb31-1140-ad5a-a45545d7ecf3": "POLAR_PFC_SERVICE",
    "6217ff4c-c8ec-b1fb-1380-3ad986708e2d": "POLAR_PFC_FEATURE",
    "6217ff4d-91bb-91d0-7e2a-7cd3bda8a1f3": "POLAR_PFC_CP",
    "fb005c51-02e7-f387-1cad-8acd2d8df0c8": "RFC77_PFTP_MTU_CHARACTERISTIC",
    "fb005c52-02e7-f387-1cad-8acd2d8df0c8": "RFC77_PFTP_D2H_CHARACTERISTIC",
    "fb005c53-02e7-f387-1cad-8acd2d8df0c8": "RFC77_PFTP_H2D_CHARACTERISTIC",
    }

register_uuids(Polar_UUIDS)

POLAR_PFC_SERVICE = name_to_uuid("POLAR_PFC_SERVICE")
POLAR_PFC_CP = name_to_uuid("POLAR_PFC_CP")
POLAR_PFC_FEATURE = name_to_uuid("POLAR_PFC_FEATURE")

POLAR_PMD_SERVICE = name_to_uuid("POLAR_PMD_SERVICE")
POLAR_PMD_CP = name_to_uuid("POLAR_PMD_CP")
POLAR_PMD_DATA = name_to_uuid("POLAR_PMD_DATA")


# PFC - supported feature flags
class PFCFlags(IntEnum):
    pfc_Broadcast = 1 << 0
    pfc_5khz      = 1 << 1
    otaUdate      = 1 << 2
    unknown3      = 1 << 3
    whisperMode   = 1 << 4
    unknown5      = 1 << 5
    bleMode       = 1 << 6
    pfc_MC        = 1 << 7
    pfc_ANT       = 1 << 8



# PMD Requests
pmdRequestMeasurementSettings = 0x01
pmdStartMeasurement = 0x02
pmdStopMeasurement = 0x03

# PMD Measurement Types
pmdMeasurementECG = 0
pmdMeasurementPPG = 1
pmdMeasurementACC = 2
pmdMeasurementPPI = 3
pmdMeasurementGYRO = 5
pmdMeasurementMAG = 6

pmdMeasurementTypes = {
    0: "ECG", 
    1: "PPG", 
    2: "ACC", 
    3: "PPI", 
    5: "GYRO", 
    6: "MAG", 
}

# PMD Setting Types
pmdSetSampleRate = 0x01
pmdSetSampleRate = 0x02
pmdSetSampleResolution = 0x01
pmdSetSampleRate = 0x01

def polar_command(command, measurement, sample_rate=None, resolution=None, 
        range=None, range_milliunit=None, channels=None, factor=None):
    command = bytearray([command, measurement],)
    if sample_rate:
        command += bytearray([0x00, 0x01, sample_rate&0xff, sample_rate>>8])
    if resolution:
        command += bytearray([0x01, 0x01, resolution&0xff, resolution>>8])
    if range:
        command += bytearray([0x02, 0x01, range&0xff, range>>8])
    if range_milliunit:
        command += bytearray([0x03, 0x01, range_milliunit&0xff, range_milliunit>>8])
    if channels:
        command += bytearray([0x04, 0x01, channels&0xff, channels>>8])
    if factor:
        command += bytearray([0x05, 0x01, factor&0xff, factor>>8])
    return command

def polar_start_stream(measurement, **kwargs):
    return polar_command(pmdStartMeasurement, measurement, **kwargs)

# PMD Control Point Error Codes
pmdErrorCodes = {
    0: "pmdCPSuccess",
    1: "pmdCPInvalidOPCode",
    2: "pmdCPInvalidMeasurementType",
    3: "pmdCPNotSupported",
    4: "pmdCPInvalidLength",
    5: "pmdCPInvalidParameter",
    6: "pmdCPAlreadInState",
    7: "pmdCPInvalidResolution",
    8: "pmdCPInvalidSampleRate",
    9: "pmdCPInvalidRange",
    10: "pmdCPInvalidMTU",
    11: "pmdCPInvalidNumberOfChannels",
    12: "pmdCPInvalidState",
    13: "pmdCPDeviceInCharger",
    }

pmdCPResponse = 0x0f
pmdFeatureECGsupported  = (1) << 0
pmdFeaturePPGsupported  = (1) << 1
pmdFeatureACCsupported  = (1) << 2
pmdFeaturePPIsupported  = (1) << 3
pmdFeatureRFUsupported  = (1) << 4
pmdFeatureGYROsupported = (1) << 5
pmdFeatureMAGsupported  = (1) << 6

FeaturesFields = [
    (pmdFeatureECGsupported, 'ECG'),
    (pmdFeaturePPGsupported, 'PPG'),
    (pmdFeatureACCsupported, 'ACC'),
    (pmdFeaturePPIsupported, 'PPI'),
    (pmdFeatureRFUsupported, 'RFU'),
    (pmdFeatureGYROsupported,'GYRO'),
    (pmdFeatureMAGsupported, 'MAG'),
    ]

def control_notification(sender, data, name=None, msg=None ):
    print("[%-28s %6s] %s" % (name, msg, bytes2str(data)), file=sys.stderr)

statistics = {}

def pmd_data_notification(sender, data, name=None):
    measurement = data[0]
    measurement_name = pmdMeasurementTypes[measurement]
    if name not in statistics:
        statistics[name] = {}
    if measurement_name not in statistics[name]:
        statistics[name][measurement_name] = 0
    statistics[name][measurement_name] += 1
    frametype = data[9]
    raw = data[:10]
    ms = int.from_bytes(data[1:8], byteorder='little', signed=False)
    print("[%-30s %4s] %3d %02x len: %s" % 
        (name, measurement_name, statistics[name][measurement_name], frametype,  len(data)), file=sys.stderr)

async def write_gatt_char(client, name, service, cp, command, msg ):
    print('[%-30s %4s] %s %s' % (name, service, bytes2str(command), msg), file=sys.stderr)
    try:
        await client.write_gatt_char(cp, command)

    except EOFError as e:
        print('[%-30s %4s] EOFError %s ...' % (name, service, e), file=sys.stderr)
    except BleakError as e:
        print('[%-30s %4s] BleakDBusError %s ...' % (name, service, e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        if platform.system() == 'Linux':
            print('[%-30s     ] You may need to restart Linux Bluetooth!' % (name), file=sys.stderr)

async def device_explore(device, stop_event):
    try:
        async with BleakClient(device) as client:

            # The Linux Bleak backend provides the name differently than Windows
            if platform.system() == 'Linux':
                device_name = client._properties['Name']
            else:
                for service in client.services:
                    for char in service.characteristics:
                        if uuidstr_to_str(char.uuid) == 'Device Name':
                            device_name = await client.read_gatt_char(char)

            print('[%-30s     ] Client Connected' % (device_name), file=sys.stderr)

            # Look at Services
            services = {}
            for service in client.services:
                service_name = uuid_to_name(service.uuid)
                services[service_name] = []
                for char in service.characteristics:
                    services[service_name].append(uuid_to_name(char.uuid)) 

            for service_name, characteristics in services.items():
                if not service_name.startswith('POLAR_'):
                    continue
                print('[%-30s     ] Service[%s] %s' % (device_name, service_name, characteristics), file=sys.stderr)


            for uuid, name in Polar_UUIDS.items():
                if not name.startswith('POLAR_'):
                    continue
                if name.endswith('_SERVICE'):
                    if name not in services:
                        print('uuid: %s NOT FOUND' % (name), file=sys.stderr)

            # get PFC features
            response = await client.read_gatt_char(POLAR_PFC_FEATURE)
            if response is not None and len(response) > 1:
                pfc_flags = response[1] << 8 | response[0]
                pfc_available = [ (f.name, bool(pfc_flags&f)) 
                    for f in PFCFlags if f in [PFCFlags.pfc_Broadcast, PFCFlags.pfc_5khz, PFCFlags.pfc_MC, PFCFlags.pfc_ANT, ]]
                print('[%-30s     ] pfc_flags: %0x pfc_available: %s' % (device_name, pfc_flags, pfc_available), file=sys.stderr)
            else:
                print('[%-30s     ] PFC Feature response not valid: %s' % (device_name, response), file=sys.stderr)
                return



            # get PMD features
            response = await client.read_gatt_char(POLAR_PMD_CP)
            pmd_features = response[1]
            pmd_available = [ n for b, n in FeaturesFields if pmd_features & b]
            print('[%-30s     ] pmd_features: %s pmd_available: %s' % (device_name, pmd_features, pmd_available), file=sys.stderr)

            # Start POLAR_PMD_CP and POLAR_PMD_DATA notifications
            try:
                await client.start_notify(POLAR_PFC_CP, partial(control_notification, name=device_name, msg='PFC_CP'))
                await client.start_notify(POLAR_PMD_CP, partial(control_notification, name=device_name, msg='PMD_CP'))
                await client.start_notify(POLAR_PMD_DATA, partial(pmd_data_notification, name=device_name, ))
            except BleakError as e:
                print('[%-30s     ] BleakDBusError %s ...' % (device_name, e), file=sys.stderr)
                if platform.system() == 'Linux':
                    print('[%-30s     ] You may need to restart Linux Bluetooth!' % (device_name), file=sys.stderr)
                #print(traceback.format_exc(), file=sys.stderr)
                return


            if 'ACC' in pmd_available:
                await write_gatt_char(client, device_name, 'ACC', POLAR_PMD_CP, 
                    polar_command(pmdRequestMeasurementSettings, pmdMeasurementACC), "Get ACC Settings")
                await write_gatt_char(client, device_name, 'ACC', POLAR_PMD_CP, 
                    polar_start_stream (pmdMeasurementACC, sample_rate=0x32, resolution=0x10, range=0x08), "Start ACC measurement")

            if 'ECG' in pmd_available:
                await write_gatt_char(client, device_name, 'ECG', POLAR_PMD_CP, 
                    polar_command(pmdRequestMeasurementSettings, pmdMeasurementECG), "Get ECG Settings")
                await write_gatt_char(client, device_name, 'ECG', POLAR_PMD_CP, 
                    polar_start_stream(pmdMeasurementECG, sample_rate=130, resolution=14), "Start ECG measurement")

            if 'PPG' in pmd_available:
                await write_gatt_char(client, device_name, 'PPG', POLAR_PMD_CP, 
                    polar_command(pmdRequestMeasurementSettings, pmdMeasurementPPG), "Get PPG Settings")
                await write_gatt_char(client, device_name, 'PPG', POLAR_PMD_CP, 
                    polar_start_stream(pmdMeasurementPPG, sample_rate=130, resolution=22), "Start PPG measurement")

            if 'PPI' in pmd_available:
                await write_gatt_char(client, device_name, 'PPI', POLAR_PMD_CP, polar_command(pmdRequestMeasurementSettings, pmdMeasurementPPI), "Get PPI Settings")
                await write_gatt_char(client, device_name, 'PPI', POLAR_PMD_CP, 
                    polar_start_stream(pmdMeasurementPPI, ), "Start PPI measurement")

            # Sleep a few seconds while streaming data comes in
            #await asyncio.sleep(60)
            await stop_event.wait()
            print('[%-30s     ] device_explore stopping' % (device.name))


            # Stop measurement
            # N.b. To stop only one measurement, you need to stop all and restart the ones still needed.
            if 'ACC' in pmd_available:
                await write_gatt_char(client, device_name, 'ACC', POLAR_PMD_CP, polar_command(pmdStopMeasurement, pmdMeasurementACC), 'Stop ACC Measurement', )
            if 'ECG' in pmd_available:
                await write_gatt_char(client, device_name, 'ECG', POLAR_PMD_CP, polar_command(pmdStopMeasurement, pmdMeasurementECG), 'Stop ECG Measurement', )
            if 'PPG' in pmd_available:
                await write_gatt_char(client, device_name, 'PPG', POLAR_PMD_CP, polar_command(pmdStopMeasurement, pmdMeasurementPPG), 'Stop PPG Measurement', )
            if 'PPI' in pmd_available:
                await write_gatt_char(client, device_name, 'PPI', POLAR_PMD_CP, polar_command(pmdStopMeasurement, pmdMeasurementPPI), 'Stop PPI Measurement', )

            # Stop notifications
            try:
                await client.stop_notify(POLAR_PMD_DATA)
                await client.stop_notify(POLAR_PMD_CP)
                await client.stop_notify(POLAR_PFC_CP)
            except BleakError as e:
                print('BleakDBusError %s ...' % (e), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                if platform.system() == 'Linux':
                    print('[%-30s     ] You may need to restart Linux Bluetooth!' % (''), file=sys.stderr)
    except asyncio.exceptions.TimeoutError as e:
        print('BleakClient timeout: %s' % (e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
    
    print('[%-30s     ] device_explore exiting' % (device.name))


async def main(wanted_name):

    print('[%-35s] looking for %s' % ('Main', wanted_name), file=sys.stderr)
    tasks = {}
    stop_event = asyncio.Event()
    def sigint_handler():
        print()
        #print('sigint_handler: ', file=sys.stderr)
        #for name, task in tasks.items():
        #    task.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigint_handler())


    def callback(dev, ad):
        if wanted_name.lower() in dev.name.lower() and dev.name not in tasks:
            tasks[dev.name] = asyncio.create_task(device_explore(dev, stop_event))

    try:
        async with BleakScanner(detection_callback=callback, scanning_mode="active") as scanner:
            print('[%-35s] waiting' % ('BleakScanner'), file=sys.stderr)
            await stop_event.wait()
            print('[%-35s] exiting, gathering tasks: %s' % ('BleakScanner', len(tasks)), file=sys.stderr)
            #done_list = [x for x in tasks if x.done() ]
            await asyncio.gather(*[ task for name, task in tasks.items()])
            print('[%-35s] exiting, tasks gathered' % ('BleakScanner'), file=sys.stderr)

        for device_name, stats in statistics.items():
            print('')
            for measurement_name, count in stats.items():
                print('[%-30s %4s] data notifications: %3d  ' % (device_name, measurement_name, count, ))
        print('')



    except BleakError as e:
        print('BleakDBusError %s ...' % (e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        if platform.system() == 'Linux':
            print('[%-30s     ] You may need to restart Linux Bluetooth!' % (''), file=sys.stderr)
        await asyncio.sleep(2)
    except OSError as e:
        print('OSError %s ...' % (e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        await asyncio.sleep(2)
    except Exception as e:
        print('BLE_Scanner.task: e: %s' % (e, ), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        await asyncio.sleep(2)

    exit()





if __name__ == "__main__":
    name = 'Polar' if len(sys.argv) == 1 else sys.argv[1]
    asyncio.run(main(name))  # H10
    print("DONE", file=sys.stderr)

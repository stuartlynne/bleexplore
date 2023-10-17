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
import async_timeout
import signal
from colored import cprint, fg, bg, attr, set_tty_aware
from time import time, sleep
from datetime import timedelta, datetime
from bleak import BleakClient
from bleak.exc import BleakError
from bleak.uuids import uuid16_dict, uuid128_dict, uuidstr_to_str, register_uuids

#from bleak.backends.corebluetooth import CBCharacteristicProperties

#from bleak_retry_connector import establish_connection

import platform
from functools import partial
from bleak import BleakScanner
from enum import Enum, IntEnum

import traceback
from lib import bytes2str, uuid_to_name, name_to_uuid, xreport
#from polar import polar, pmd_data_notification, POLAR_PMD_DATA, Polar_Supported_Characteristics, Polar_UUIDS
from polar import Polar
from moxy import Moxy
from vo2master import VO2Master

#register_uuids(Polar_UUIDS)

#OxySmart_UUIDS = {
#}
#6e400001-b5a3-f393-e0a9-e50e24dcca9e (Handle: 6): Nordic UART Service
#6e400002-b5a3-f393-e0a9-e50e24dcca9e (Handle: 7): Nordic UART RX (write-without-response,write), Value: None
#6e400003-b5a3-f393-e0a9-e50e24dcca9e (Handle: 9): Nordic UART TX (notify), Value: None

statistics = {}

def xnotification(sender, data, myclient=None, device_name=None, supported_devices=None ):
    try:
        xreport(device_name, 'notification', '%s:%s' % (uuid_to_name(sender.uuid), len(data), ))
        if device_name not in statistics:
            statistics[device_name] = {}
        for device in supported_devices:
            if device.data_check(sender.uuid):
                device.notification(sender.uuid, data, myclient=myclient, device_name=device_name, statistics=statistics)
        #if sender.uuid == POLAR_PMD_DATA:
        #    notification(sender, data, device_name)
        #    return
        measurement_name = uuid_to_name(sender.uuid)
        if measurement_name not in statistics[device_name]:
            statistics[device_name][measurement_name] = 0
        statistics[device_name][measurement_name] += 1
    except Exception as e:
        print(e)
        print(traceback.format_exc(), file=sys.stderr)

supported_characteristics = {
    'Battery Service': {
        'read': ['Battery Level'],
        'notify': [],
        'ignore': [],
    },
    'Current Time Service': None, 
    'Heart Rate': {
        'read': ['Heart Rate Control Point'],
        'notify': ['Heart Rate Measurement'],
        'ignore': ['Body Sensor Location'],
    },
    'Device Information': {
        'read': [
            'Manufacturer Name String', 'Model Number String', 'Serial Number String', 
            'Hardware Revision String', 'Firmware Revision String', 'Software Revision String', 
            ],
        'ignore': ['PnP ID', 'System ID', 'IEEE 11073-20601 Regulatory Certification Data List', ],
    },
    "Moxy SMO2 Service": { 
        'read': [],
        'notify': ["Moxy SMO2 Data"],
        'ignore': [
            "Moxy SMO2 Data Packet",
            "Moxy SMO2 Data Point Value",
            "Moxy SMO2 Data Point Control",
            "Moxy SMO2 Data Range Request",
            "Moxy SMO2 Data Point Upload",
        ]
    },
    "Polar Feature Configuration Service": { 
        'notify': ["Polar PFC Control Point"],
    },
    "Polar Measurement Data Service": {
        'notify': [
            "Polar PMD Control Point",
            "Polar PMD Data",
        ],
    }, 
    "ZwiftPlay Service": {
        'notify': ["ZwiftPlay Data", "ZwiftPlay Left", "ZwiftPlay Right", "ZwiftPlay Response" ],
        #'notify': ["ZWIFTPLAY_DATA", ],
        #'read': ["ZWIFTPLAY_CP", ],
    },
    "VO2_MASTER_CUSTOM_SERVICE": {
        'notify': ["COM_OUT_UUID", 
                   "AMBIENT_GAS_CALIBRATION_CHARACTERISTIC",
                   "VENTILATORY_CHARACTERISTIC",
                   "GAS_EXCHANGE_CHARACTERISTIC",
                   "SYRINGE_FLOW_CALIBRATION_CHARACTERISTIC",
                   "ENVIRONMENT_CHARACTERISTIC",
                   ],
    },

    "Nordic UART Service": {
        'notify': ["Nordic UART TX", "Nordic UART RX", ],
    },
}

#def report(device_name, operation='', msg='', fore='black', back='white'):
#    cprint ('[%-30s %22s] %s' % (device_name, operation, msg), file=sys.stderr, fore_256=fore, back_256=back)




# explore the device, use start_notify to receive updates of characteristics and start data collection,
# await stop_notify to stop receiving updates and stop data collection
async def device_explore(myclient, device, task_stop_event, supported_devices,):
    client = myclient.client
    myclient.report('Connected', '', fore='black', back='light_yellow', ) 
    print('supported_devices: %s' % ([supported_devices], ), file=sys.stderr)

    def supported_characteristic(service_name, characteristic_name, characteristic_type):
        if service_name not in supported_characteristics or supported_characteristics[service_name] is None:
            #print('[%-28s %6s] not supported: %s:%s UNKNOWN' % (device_name, characteristic_type, service_name, characteristic_name), file=sys.stderr)
            return False
        if characteristic_type not in supported_characteristics[service_name]:
            #print('[%-28s %6s] not supported: %s:%s NONE' % (device_name, characteristic_type, service_name, characteristic_name), file=sys.stderr)
            return False
        if uuid_to_name(char_uuid) not in supported_characteristics[service_name][characteristic_type]:
            #print('[%-28s %6s] not supported: %s:%s' % (device_name, characteristic_type, service_name, characteristic_name), file=sys.stderr)
            return False
        return True

    device_name = device.name

    # Look at Services
    try:
        services = {}
        for service in client.services:
            service_name = uuid_to_name(service.uuid)
            services[service.uuid] = []
            myclient.report('service', '%s' % (service_name, ))

            reads = [ char.uuid for char in service.characteristics if 'read' in char.properties ]
            read_names = [ uuid_to_name(char.uuid) for char in service.characteristics if 'read' in char.properties ]
            notifications = [ char.uuid for char in service.characteristics if 'notify' in char.properties or 'indicate' in char.properties ]
            notification_names = [ uuid_to_name(char.uuid) for char in service.characteristics if 'notify' in char.properties or 'indicate' in char.properties ]

            if reads != []:
                for i, r in enumerate(read_names):
                    myclient.report('reads', '%d: %s' % (i, r, ))
            if notifications != []:
                #myclient.report('notifications', '%s' % (notifications, ))
                for i, n in enumerate(notification_names):
                    myclient.report('notifications', '%d: %s' % (i, n, ))

            for char_uuid in reads:
                characteristic_name = uuid_to_name(char_uuid)
                if not supported_characteristic(service_name, characteristic_name, 'read'):
                    continue
                response = await myclient.read_gatt_char(char_uuid)
                #print('READ: %s' % (char_uuid, ), file=sys.stderr)
                #print('READ: %s' % (uuid_to_name(char_uuid), ), file=sys.stderr)
                if response is None:
                    myclient.report('read', '%s read failed' % (char_uuid, ))
                    return False
                if 'string' in uuid_to_name(char_uuid):
                    response = bytes2str(response)
                myclient.report('read', '%s:%s %s' % 
                    (service_name, characteristic_name,
                     ''.join(map(chr, response)) if 'string' in uuid_to_name(char_uuid).lower() else bytes2str(response), 
                                                          ))

            for char_uuid in notifications:
                if not supported_characteristic(service_name, uuid_to_name(char_uuid), 'notify'):
                    continue
                if not await myclient.start_notify(char_uuid, myclient.notification, supported_devices, ):
                    myclient.report('start_notify', 'Failed') 
                    return False
    except Exception as e:
        print('Exception: %s' % (e, ), file=sys.stderr)
        traceback.print_exc()
        return False

    try:
        for device in supported_devices:
            if device.service_check(services):
                myclient.report(name, 'found') 
                await device.start(myclient, device_name, services)
            #else:
            #    report(device.name, device.name, 'not found') 
    except Exception as e:
        print('Exception: %s' % (e, ), file=sys.stderr)
        traceback.print_exc()

    myclient.report('device_task', 'waiting for stop event')
    await task_stop_event.wait()
    myclient.report('device_task', 'stopping', fore='black', back='light_yellow', )

    return True


# super class ble client to handle notifications and data collection and get consistent exception handling
class MyClient:
    def __init__(self, device, task_stop_event, support_list):
        self.device = device
        self.task_stop_event = task_stop_event
        self.client = None
        self.services = {}
        self.characteristics = {}
        self.support_list = support_list
        self.start_time = time()

    def notification(self, sender, data, device_name=None, supported_devices=None ):
        try:
            found = False
            if device_name not in statistics:
                statistics[device_name] = {}

            for device in supported_devices:
                if device.data_check(sender.uuid):
                    #self.report('notification', 'data_check %s True' % (device.name), )
                    device.notification(sender.uuid, data, myclient=self, device_name=device_name, statistics=statistics)
                    found = True
                #else:
                #    self.report('notification', 'data_check %s False' % (device.name), )

            if not found:
                self.report('notification', '%s:%s' % (uuid_to_name(sender.uuid), len(data), ))
            #if sender.uuid == POLAR_PMD_DATA:
            #    notification(sender, data, device_name)
            #    return
            measurement_name = uuid_to_name(sender.uuid)
            if measurement_name not in statistics[device_name]:
                statistics[device_name][measurement_name] = 0
            statistics[device_name][measurement_name] += 1
        except Exception as e:
            print(e)
            print(traceback.format_exc(), file=sys.stderr)

    
    def report(self, operation='', msg='', fore='black', back='white'):
        elapsed = int(time() - self.start_time)
        cprint ('[%3d:%02d %-20s %22s] %s' % (elapsed//60, elapsed%60, self.device.name, operation, msg), file=sys.stderr, fore_256=fore, back_256=back)

    def disconnected_callback(self, client, device_name=None, disconnect_event=None):
        self.report(operation='disconnected', msg='', fore='black', back='light_yellow', )
        disconnect_event.set()

    def is_connected(self):
        return self.client.is_connected

    async def disconnect(self):
        return await self.client.disconnect()

    async def connect(self):
        self.task_stop_event.clear()

       ## test establish_connection from bleak retry package
       #if False:
       #    self.report('device_task connecting')
       #    try:
       #        self.client = await establish_connection(
       #            client_class=BleakClient, 
       #            device=self.device, 
       #            name=self.device.name, 
       #            disconnected_callback=partial(self.disconnected_callback, device_name=self.device.name, disconnect_event=self.task_stop_event), max_attempts=1, timeout=4)
       #    except asyncio.exceptions.TimeoutError as e:
       #        self.report('Timeout', 'Not Connected', fore='black', back='light_yellow', )
       #        self.task_stop_event.set()
       #        return False
       #    return True

        # Connect to device, catch exceptions and retry using BleakClient, 
        # N.b. Creating client and then calling client.connect() allows us to have standalone client handle
        #
        try:
            self.client = BleakClient(
                self.device, timeout=10,
                disconnected_callback=partial(self.disconnected_callback, device_name=self.device.name, disconnect_event=self.task_stop_event), 
                ) 
            if self.client is None:
                self.report('Connection', 'BleakClient Failed', fore='black', back='light_yellow', )
                self.task_stop_event.set()
                return False

            self.report('Connection', 'Connecting', fore='black', back='light_yellow', )

            # await connection
            await self.client.connect(timeout=10.)
            self.report('Connection', 'Connected')

        # catch exceptions and retry as necessary
        except asyncio.exceptions.TimeoutError as e:
            self.report('Connection', 'Timeout')
            self.task_stop_event.set()
            return False
        except BleakError as e:
            self.report('BleakError waiting for client.connect e: %s' % (e), fore='black', back='indian_red_1c', )
            self.task_stop_event.set()
            return False
        except Exception as e:
            self.report('Exception waiting for client.connect e: %s' % (e), fore='black', back='indian_red_1c', )
            self.task_stop_event.set()
            return False
        return True

    async def write_gatt_char(self, char_uuid, command, ):

        if self.task_stop_event.is_set():
            self.report('write_gatt_char', '%s %s task_stop_event set' % (bytes2str(command ), uuid_to_name(char_uuid), ))
            return False

        self.report('write_gatt_char', '%s %s' % (bytes2str(command ), uuid_to_name(char_uuid), ))
       # print('[%-30s %4s] %s %s' % (name, service, bytes2str(command), msg), file=sys.stderr)
        try:
            await self.client.write_gatt_char(char_uuid, command)

        except EOFError as e:
            self.task_stop_event.set()
            self.report('write_gatt_char', 'EOFError %s ...' % (e, ), fore='black', back='indian_red_1c', )
            await asyncio.sleep(2)
            return False
            #print('[%-30s %4s] EOFError %s ...' % (name, service, e), file=sys.stderr)
        except BleakError as e:
            self.task_stop_event.set()
            self.report('write_gatt_char', 'BleakDBusError %s ...' % (e, ), fore='black', back='light_red', )
            await asyncio.sleep(2)
            return False
        except Exception as e:
            await asyncio.sleep(2)
            print(traceback.format_exc(), file=sys.stderr)
            return False
        return True

    async def read_gatt_char(self, char_uuid, ):

        if self.task_stop_event.is_set():
            self.report('read_gatt_char', '%s task_stop_event set' % (uuid_to_name(char_uuid), ))
            return None

        response = None
        try:
            #self.report('read_gatt_char', '%s: start' % (char_uuid, ))
            #self.report('read_gatt_char', '%s: start' % (uuid_to_name(char_uuid), ))
            response = await self.client.read_gatt_char(char_uuid)

        except EOFError as e:
            self.task_stop_event.set()
            self.report('read_gatt_char', 'EOFError %s ...' % (e, ), fore='black', back='indian_red_1c', )
            await asyncio.sleep(2)
            return None
        except BleakError as e:
            self.task_stop_event.set()
            self.report('read_gatt_char', 'BleakDBusError %s ...' % (e, ), fore='black', back='indian_red_1c', )
            print(traceback.format_exc(), file=sys.stderr)
            await asyncio.sleep(2)
            return None
        self.report('read_gatt_char', '%s: %s' % (uuid_to_name(char_uuid), bytes2str(response) if response else 'None'))
        return response

    async def start_notify(self, char_uuid, notification, supported_devices, ):

        if self.task_stop_event.is_set():
            self.report('start_notify', '%s task_stop_event set' % (uuid_to_name(char_uuid), ))
            return False

        #self.report('start_notify', '%s' % (uuid_to_name(char_uuid), ))
        try:
            await self.client.start_notify(char_uuid, partial(self.notification, device_name=self.device.name, supported_devices=supported_devices, ))

        except BleakError as e:
            self.report('start_notify', 'BleakDBusError %s ...' % (e, ), fore='black', back='indian_red_1c', )
            await asyncio.sleep(2)
            return False
        self.report('start_notify', '%s OK' % (uuid_to_name(char_uuid), ))
        return True

    

async def device_task(device, task_stop_event, supported_devices, ):
    try:
        xreport(device.name, 'device_task starting')

        # task_stop_event is set when the connection stops
        myclient = MyClient(device, task_stop_event, supported_devices,)

        while True:
            if not await myclient.connect():
                continue


            # Explore device
            result = await device_explore(myclient, device, task_stop_event, supported_devices, )
            if myclient.is_connected():
                await myclient.disconnect()
            task_stop_event.clear()
            xreport(device.name, 'Connection', 'Normal Disconnect')
            continue

    except asyncio.CancelledError:
        xreport(device.name, 'device_task', 'asyncio.CancelledError', fore='black', back='light_yellow', )
        xreport(device.name, 'device_task', e, fore='black', back='light_yellow', )
        raise asyncio.CancelledError()
    except asyncio.exceptions.CancelledError as e:
        xreport(device.name, 'device_task', 'asyncio.exceptions.CancelledError', fore='black', back='light_yellow', )
        xreport(device.name, 'device_task', e, fore='black', back='light_yellow', )
        raise asyncio.exceptions.CancelledError()
    except Exception as e: 
        xreport(device.name, 'device_task', 'Exception', fore='black', back='light_yellow', )
        xreport(device.name, 'device_task', e, fore='black', back='light_yellow', )
        print(traceback.format_exc(), file=sys.stderr)
        raise asyncio.exceptions.CancelledError()
    finally:
        try:
            xreport(device.name, 'device_task', 'Finally Disconnecting')
            await myclient.disconnect()
            xreport(device.name, 'Connection', 'Final Disconnect')
        except Exception as e:
            xreport(device.name, 'device_task', 'Exception %s' % (e, ), fore='black', back='indian_red_1c', )
            print(traceback.format_exc(), file=sys.stderr)
        finally:
            xreport(device.name, 'device_task', 'finished', fore='black', back='light_yellow', )
        return True

def handle_task_result(task):
    name = task.get_name()
    try:
        value = task.result()
        xreport(name, 'Finished', fore='black', back='light_yellow',  )
    except asyncio.CancelledError:
        xreport(name, 'Cancelled', fore='black', back='light_yellow',  )
    except Exception as e:
        xreport(name, 'Exception', e, fore='black', back='light_yellow',  )
        print(traceback.format_exc(), file=sys.stderr)
    finally:
        pass
        

async def main(argv):

    xreport('Scanner', 'Scanning', '%s' % (argv), )
    tasks = {}
    stop_event = asyncio.Event()
    task_stop_events = {}
    def sigint_handler():
        stop_event.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigint_handler())

    supported_devices = [Polar(), Moxy(), VO2Master(), ]

    def detection_callback(dev=None, ad=None, ):
        #print('[%-35s] detection_callback dev: %s' % ('BleakScanner', dir(dev), ), file=sys.stderr)
        #print('[%-35s] detection_callback tasks: %s' % ('BleakScanner', tasks), file=sys.stderr)

        #if dev.name is not None and wanted_name.lower() in dev.name.lower() and dev.name not in tasks:
        if dev.name is not None and dev.name not in tasks:
            for a in argv:
                if a.lower() in dev.name.lower():
                    xreport('Scanner', 'Found', dev.name, )
                    task_stop_event = asyncio.Event()
                    task_stop_events[dev.name] = task_stop_event
                    tasks[dev.name] = asyncio.create_task(device_task(dev, task_stop_event, supported_devices, ), name=dev.name,)
                    tasks[dev.name].add_done_callback(handle_task_result)   
                    print('--------------------------------------------------------------------------------', file=sys.stderr)
                    break
    try:
        last_stop_time = 0
        async with BleakScanner(detection_callback=detection_callback, scanning_mode="active") as scanner:
            xreport('Scanner', 'Waiting', 'tasks: %s' % ([t for t in tasks.keys()]), )
            while stop_event.is_set() == False:
                await stop_event.wait()
                stop_time = time()
                if stop_time - last_stop_time > 4:
                    stop_event.clear()
                    for name in tasks.keys():
                        task_stop_events[name].set()
                    last_stop_time = stop_time

            for name, task in tasks.items():
                #task.stop()
                xreport('Scanner', 'Stopping', name, )
                # XXX
                # was_cancelled = task.cancel('SIGINT Cancelled')
                was_cancelled = task.cancel()
                try:
                    await task
                    value = task.result()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(traceback.format_exc(), file=sys.stderr)
                    pass
            xreport('Scanner', 'Gathering', '%s' % ([t for t in tasks.keys()]))
            #done_list = [x for x in tasks if x.done() ]
            await asyncio.gather(*[ task for name, task in tasks.items()], return_exceptions=True)
            xreport('Scanner', 'Tasks Gathered', '')

        for device_name, stats in statistics.items():
            print('')
            for measurement_name, count in stats.items():
                xreport(device_name, measurement_name, 'Count: %d' % (count), )
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

if __name__ == "__main__":
    set_tty_aware(awareness=False)
    if len(sys.argv) < 1:
        print('Usage: %s <device names>' % (sys.argv[0], ), file=sys.stderr)
        sys.exit(1)
    name = 'Polar' if len(sys.argv) == 1 else sys.argv[1]
    asyncio.run(main(sys.argv[1:]))  # H10

# Firmware – Pico W BLE UART Sender
# This extends the existing MAX30102 + MPU6500 firmware to add
# Bluetooth LE UART output for the Flutter app to receive.
# 
# Hardware: Raspberry Pi Pico W
# Sensors: MAX30102 (HR/SpO2) + MPU6500 (Accelerometer)
# BLE Service: Nordic UART Service (NUS)
#
# NOTE: This is a MicroPython stub showing the BLE integration.
# The C++ firmware (provided by user) handles sensor reading.
# This file shows how to add BLE transmission to it.

import bluetooth
import struct
import time
from micropython import const

# Nordic UART Service
_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX   = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
              bluetooth.FLAG_NOTIFY,)
_UART_RX   = (bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
              bluetooth.FLAG_WRITE,)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX,),)

_ADV_TYPE_FLAGS         = const(0x01)
_ADV_TYPE_NAME          = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x03)

class BLEUARTSender:
    """
    Minimal Nordic UART Service sender for Pico W.
    Sends formatted sensor data strings to connected Flutter app.
    """

    def __init__(self, ble: bluetooth.BLE, name: str = "AVIRA_PICO"):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        ((self._tx_handle, self._rx_handle),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._connections = set()
        self._advertise(name)

    def _irq(self, event, data):
        if event == 1:   # Connect
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == 2: # Disconnect
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self._advertise("AVIRA_PICO")
        elif event == 3: # RX write
            pass

    def _advertise(self, name: str):
        name_bytes = name.encode()
        payload = (
            bytes([2, _ADV_TYPE_FLAGS, 0x06]) +
            bytes([len(name_bytes) + 1, _ADV_TYPE_NAME]) + name_bytes
        )
        self._ble.gap_advertise(100_000, adv_data=payload)

    def send(self, data: str):
        """Send a UTF-8 string to all connected clients via BLE notify."""
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._tx_handle, data.encode())

    def send_sensor_packet(
        self,
        heart_rate: int,
        hr_valid: bool,
        spo2: int,
        spo2_valid: bool,
        accel_x: float,
        accel_y: float,
        accel_z: float,
        motion_magnitude: float,
    ):
        """Format and send a complete sensor data packet."""
        packet = "\n=========== DATA ===========\n"
        
        if hr_valid:
            packet += f"Heart Rate : {heart_rate} BPM\n"
        else:
            packet += "Heart Rate : Invalid\n"
        
        if spo2_valid:
            packet += f"SpO2       : {spo2} %\n"
        else:
            packet += "SpO2       : Invalid\n"
        
        packet += f"Accel X    : {accel_x:.3f}\n"
        packet += f"Accel Y    : {accel_y:.3f}\n"
        packet += f"Accel Z    : {accel_z:.3f}\n"
        packet += f"Motion Mag : {motion_magnitude:.3f}\n"
        packet += "============================\n"
        
        self.send(packet)
        return packet


# ─────────────────────────────────────────────
#  Example Usage (in main loop)
# ─────────────────────────────────────────────
# ble = bluetooth.BLE()
# uart = BLEUARTSender(ble)
# 
# while True:
#     # (sensor reading happens as per the C++ firmware)
#     uart.send_sensor_packet(
#         heart_rate=65, hr_valid=True,
#         spo2=98, spo2_valid=True,
#         accel_x=0.012, accel_y=0.031, accel_z=0.981,
#         motion_magnitude=1.023,
#     )
#     time.sleep_ms(1000)

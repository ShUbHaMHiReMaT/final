/// AVIRA Bluetooth Service
/// Manages BLE scanning, connection and data reception from the Pico device.
/// The Pico sends data via BLE UART (Nordic UART Service).
library;

import 'dart:async';
import 'dart:convert';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../models/sensor_data.dart';

// Nordic UART Service UUIDs
const String _nuartServiceUuid     = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
const String _nuartTxCharUuid      = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // Peripheral TX → App RX
const String _nuartRxCharUuid      = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // App TX → Peripheral RX

// Device name filter (Pico will advertise as this)
const String _deviceNameFilter     = 'AVIRA_PICO';

/// Callback types
typedef SensorDataCallback   = void Function(SensorData data);
typedef ConnectionCallback   = void Function(bool connected, String deviceName);
typedef ErrorCallback        = void Function(String error);
typedef ScanResultCallback   = void Function(List<ScanResult> results);

class BluetoothService {
  BluetoothDevice? _device;
  BluetoothCharacteristic? _txCharacteristic;
  StreamSubscription<List<int>>? _notifySubscription;
  StreamSubscription<BluetoothConnectionState>? _connStateSubscription;

  // Buffered incoming data from BLE (accumulate across packets)
  final StringBuffer _dataBuffer = StringBuffer();

  // Callbacks
  SensorDataCallback?  onSensorData;
  ConnectionCallback?  onConnectionChanged;
  ErrorCallback?       onError;
  ScanResultCallback?  onScanResults;

  bool _connected = false;
  bool _scanning  = false;

  bool get isConnected => _connected;
  bool get isScanning  => _scanning;
  String? get connectedDeviceName => _device?.platformName;

  // ── Scan ─────────────────────────────────────────────────────────────

  /// Start BLE scan for AVIRA Pico devices.
  Future<void> startScan() async {
    if (_scanning) return;

    final state = await FlutterBluePlus.adapterState.first;
    if (state != BluetoothAdapterState.on) {
      onError?.call('Bluetooth is not enabled. Please enable Bluetooth and try again.');
      return;
    }

    _scanning = true;
    final List<ScanResult> results = [];

    await FlutterBluePlus.startScan(
      withNames: [],      // empty = all devices
      timeout: const Duration(seconds: 10),
    );

    FlutterBluePlus.onScanResults.listen((scanResults) {
      results.clear();
      results.addAll(scanResults);
      onScanResults?.call(List.from(results));
    });

    await Future.delayed(const Duration(seconds: 10));
    _scanning = false;
  }

  /// Stop an in-progress BLE scan.
  Future<void> stopScan() async {
    await FlutterBluePlus.stopScan();
    _scanning = false;
  }

  // ── Connect ───────────────────────────────────────────────────────────

  /// Connect to a discovered BLE device.
  Future<void> connect(BluetoothDevice device) async {
    try {
      _device = device;
      await device.connect(timeout: const Duration(seconds: 15));

      // Monitor connection state
      _connStateSubscription = device.connectionState.listen((state) {
        _connected = (state == BluetoothConnectionState.connected);
        onConnectionChanged?.call(_connected, device.platformName);
        if (!_connected) {
          _cleanup();
        }
      });

      await _discoverServicesAndSubscribe(device);
    } catch (e) {
      onError?.call('Connection failed: ${e.toString()}');
      _connected = false;
    }
  }

  /// Disconnect from the current device.
  Future<void> disconnect() async {
    await _device?.disconnect();
    _cleanup();
  }

  // ── Internal ─────────────────────────────────────────────────────────

  Future<void> _discoverServicesAndSubscribe(BluetoothDevice device) async {
    final services = await device.discoverServices();

    for (final service in services) {
      if (service.uuid.toString().toLowerCase() == _nuartServiceUuid) {
        for (final char in service.characteristics) {
          if (char.uuid.toString().toLowerCase() == _nuartTxCharUuid) {
            _txCharacteristic = char;
            await char.setNotifyValue(true);

            _notifySubscription = char.onValueReceived.listen((data) {
              final chunk = utf8.decode(data, allowMalformed: true);
              _dataBuffer.write(chunk);
              _processBuffer();
            });

            onConnectionChanged?.call(true, device.platformName);
            return;
          }
        }
      }
    }

    onError?.call('AVIRA UART service not found on device. '
        'Ensure correct firmware is loaded on the Pico.');
  }

  /// Parse accumulated buffer for complete sensor data packets.
  void _processBuffer() {
    final content = _dataBuffer.toString();

    // Look for the separator pattern used by the Pico firmware
    const endMarker = '============================';
    final endIdx = content.indexOf(endMarker);
    if (endIdx == -1) return; // Packet not yet complete

    final packet = content.substring(0, endIdx + endMarker.length);
    _dataBuffer.clear();

    // Remaining bytes after packet
    final remainder = content.substring(endIdx + endMarker.length);
    _dataBuffer.write(remainder);

    // Parse and emit
    try {
      final sensorData = SensorData.fromBlePacket(packet);
      onSensorData?.call(sensorData);
    } catch (e) {
      onError?.call('Failed to parse sensor packet: ${e.toString()}');
    }
  }

  void _cleanup() {
    _notifySubscription?.cancel();
    _connStateSubscription?.cancel();
    _notifySubscription = null;
    _connStateSubscription = null;
    _txCharacteristic = null;
    _dataBuffer.clear();
    _connected = false;
  }
}

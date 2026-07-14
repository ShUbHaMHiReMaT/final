/// AVIRA Sensor Data Model
/// Represents a single snapshot from the Pico device (MAX30102 + MPU6500).
library;

/// Immutable value object for a sensor reading.
class SensorData {
  final double? heartRate;
  final bool heartRateValid;
  final double? spo2;
  final bool spo2Valid;
  final double? accelX;
  final double? accelY;
  final double? accelZ;
  final double? motionMagnitude;
  final DateTime timestamp;

  const SensorData({
    this.heartRate,
    this.heartRateValid = false,
    this.spo2,
    this.spo2Valid = false,
    this.accelX,
    this.accelY,
    this.accelZ,
    this.motionMagnitude,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? const _DefaultDateTime();

  factory SensorData.fromBlePacket(String packet) {
    // BLE packet format (line-separated key:value pairs from Pico serial output)
    // =========== DATA ===========
    // Heart Rate : 65 BPM
    // SpO2       : 98 %
    // Accel X    : 0.012
    // ...
    final lines = packet.split('\n');
    final Map<String, String> values = {};

    for (final line in lines) {
      if (line.contains(':')) {
        final parts = line.split(':');
        if (parts.length >= 2) {
          final key = parts[0].trim().toLowerCase().replaceAll(' ', '_');
          final val = parts.sublist(1).join(':').trim();
          values[key] = val;
        }
      }
    }

    double? parseVal(String raw) {
      final cleaned = raw.replaceAll(RegExp(r'[a-zA-Z%° ]'), '').trim();
      return double.tryParse(cleaned);
    }

    bool isValid(String raw) => !raw.toLowerCase().contains('invalid');

    return SensorData(
      heartRate: parseVal(values['heart_rate'] ?? ''),
      heartRateValid: isValid(values['heart_rate'] ?? ''),
      spo2: parseVal(values['spo2'] ?? ''),
      spo2Valid: isValid(values['spo2'] ?? ''),
      accelX: parseVal(values['accel_x'] ?? ''),
      accelY: parseVal(values['accel_y'] ?? ''),
      accelZ: parseVal(values['accel_z'] ?? ''),
      motionMagnitude: parseVal(values['motion_mag'] ?? ''),
      timestamp: DateTime.now(),
    );
  }

  Map<String, dynamic> toJson(String cowId, {String? deviceId}) => {
    'cow_id': cowId,
    'device_id': deviceId ?? 'PICO_01',
    'heart_rate': heartRate,
    'heart_rate_valid': heartRateValid,
    'spo2': spo2,
    'spo2_valid': spo2Valid,
    'accel_x': accelX,
    'accel_y': accelY,
    'accel_z': accelZ,
    'motion_magnitude': motionMagnitude,
    'timestamp': timestamp.toIso8601String(),
  };

  @override
  String toString() =>
    'SensorData(HR=${heartRate?.toStringAsFixed(0)} BPM, '
    'SpO2=${spo2?.toStringAsFixed(1)}%, '
    'Motion=${motionMagnitude?.toStringAsFixed(3)})';
}

/// Workaround: const default timestamp value
class _DefaultDateTime implements DateTime {
  const _DefaultDateTime();

  @override
  DateTime toLocal() => DateTime.now();

  @override
  String toIso8601String() => DateTime.now().toIso8601String();

  // All other DateTime interface methods delegate to DateTime.now()
  @override
  dynamic noSuchMethod(Invocation invocation) => DateTime.now();
}

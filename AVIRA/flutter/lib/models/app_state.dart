/// AVIRA App State Provider
/// Manages all global application state using Provider pattern.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import 'sensor_data.dart';
import 'analysis_result.dart';
import '../services/api_service.dart';

/// Global application state managed with ChangeNotifier.
class AppState extends ChangeNotifier {
  // ── Identity ─────────────────────────────────────────────────────────
  String _cowId = 'COW_PICO_01';
  String _sessionId = '';
  String _serverUrl = 'https://final-qj39.onrender.com/api/v1'; // Render default

  // ── Bluetooth ─────────────────────────────────────────────────────────
  bool _isScanning = false;
  bool _isConnected = false;
  String _connectedDeviceName = '';
  String _connectedDeviceId = '';

  // ── Live Sensor Data ──────────────────────────────────────────────────
  SensorData _latestSensor = const SensorData();
  final List<SensorData> _sensorHistory = [];

  // ── Analysis ──────────────────────────────────────────────────────────
  AnalysisResult? _latestAnalysis;
  bool _isAnalysing = false;

  // ── UI State ──────────────────────────────────────────────────────────
  bool _isLoading = false;
  String _statusMessage = '';
  String _errorMessage = '';

  // ── Getters ───────────────────────────────────────────────────────────
  String get cowId => _cowId;
  String get sessionId => _sessionId;
  String get serverUrl => _serverUrl;
  bool get isScanning => _isScanning;
  bool get isConnected => _isConnected;
  String get connectedDeviceName => _connectedDeviceName;
  String get connectedDeviceId => _connectedDeviceId;
  SensorData get latestSensor => _latestSensor;
  List<SensorData> get sensorHistory => List.unmodifiable(_sensorHistory);
  AnalysisResult? get latestAnalysis => _latestAnalysis;
  bool get isAnalysing => _isAnalysing;
  bool get isLoading => _isLoading;
  String get statusMessage => _statusMessage;
  String get errorMessage => _errorMessage;

  // ── Initialiser ───────────────────────────────────────────────────────

  AppState() {
    _generateNewSession();
    _loadPreferences();
  }

  void _generateNewSession() {
    _sessionId = 'SES_${const Uuid().v4().replaceAll('-', '').substring(0, 12).toUpperCase()}';
  }

  Future<void> _loadPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    _cowId = prefs.getString('cow_id') ?? _cowId;
    _serverUrl = prefs.getString('server_url') ?? _serverUrl;
    // Sync static ApiService fields
    ApiService.currentCowId = _cowId;
    ApiService.setBaseUrl(_serverUrl);
    notifyListeners();
  }

  // ── Setters ───────────────────────────────────────────────────────────

  Future<void> setCowId(String id) async {
    _cowId = id.toUpperCase().trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('cow_id', _cowId);
    ApiService.currentCowId = _cowId;  // keep static in sync
    notifyListeners();
  }

  Future<void> setServerUrl(String url) async {
    _serverUrl = url.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', _serverUrl);
    ApiService.setBaseUrl(_serverUrl);  // keep static in sync
    notifyListeners();
  }

  void newSession() {
    _generateNewSession();
    _latestAnalysis = null;
    _sensorHistory.clear();
    _latestSensor = const SensorData();
    _statusMessage = 'New session started';
    ApiService.currentSessionId = _sessionId;  // keep static in sync
    notifyListeners();
  }

  // ── Bluetooth State ───────────────────────────────────────────────────

  void setScanning(bool scanning) {
    _isScanning = scanning;
    notifyListeners();
  }

  void setConnected({
    required bool connected,
    String deviceName = '',
    String deviceId = '',
  }) {
    _isConnected = connected;
    _connectedDeviceName = deviceName;
    _connectedDeviceId = deviceId;
    _statusMessage = connected ? 'Connected to $deviceName' : 'Disconnected';
    notifyListeners();
  }

  // ── Sensor Data ───────────────────────────────────────────────────────

  void updateSensorData(SensorData data) {
    _latestSensor = data;
    _sensorHistory.add(data);
    // Keep only last 100 readings in memory
    if (_sensorHistory.length > 100) {
      _sensorHistory.removeAt(0);
    }
    notifyListeners();
  }

  // ── Analysis State ─────────────────────────────────────────────────────

  void setAnalysing(bool analysing) {
    _isAnalysing = analysing;
    if (analysing) {
      _statusMessage = 'Running AI pipeline…';
    }
    notifyListeners();
  }

  void setAnalysisResult(AnalysisResult result) {
    _latestAnalysis = result;
    _isAnalysing = false;
    _statusMessage = 'Analysis complete';
    notifyListeners();
  }

  // ── UI Helpers ─────────────────────────────────────────────────────────

  void setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void setStatus(String message) {
    _statusMessage = message;
    notifyListeners();
  }

  void setError(String message) {
    _errorMessage = message;
    _isLoading = false;
    notifyListeners();
  }

  void clearError() {
    _errorMessage = '';
    notifyListeners();
  }
}

/// AVIRA API Service
/// HTTP client for all backend communication.
/// All methods throw [ApiException] on failure.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

/// Structured API error.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final List<String> errors;

  const ApiException(this.message, {this.statusCode, this.errors = const []});

  @override
  String toString() => 'ApiException: $message (status=$statusCode)';
}

class ApiService {
  final String baseUrl;
  final Duration timeout;

  // ── Static state (app-wide singleton values) ──────────────────────────
  // Stored here so CowSimulationScreen and other widgets can read the
  // current cow/session without needing a Provider lookup.
  static String? currentCowId;
  static String? currentSessionId;
  static String _baseUrlStatic = 'https://final-qj39.onrender.com/api/v1';

  /// Update the static base URL whenever the user saves settings.
  static void setBaseUrl(String url) => _baseUrlStatic = url;

  const ApiService({
    required this.baseUrl,
    this.timeout = const Duration(seconds: 30),
  });

  // ── Static convenience getters ────────────────────────────────────────
  static ApiService get instance => ApiService(baseUrl: _baseUrlStatic);

  /// Fetch report – static helper for CowSimulationScreen.
  static Future<Map<String, dynamic>?> fetchReport(
      String cowId, String sessionId) async {
    try {
      return await instance.getReport(cowId, sessionId);
    } catch (_) {
      return null;
    }
  }

  /// Fetch history – static helper.
  static Future<Map<String, dynamic>?> fetchHistory(
      String cowId, {int limit = 20}) async {
    try {
      return await instance.getHistory(cowId: cowId, limit: limit);
    } catch (_) {
      return null;
    }
  }

  // ── HTTP Helpers ──────────────────────────────────────────────────────

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'AVIRA-Flutter/1.0',
  };

  Future<Map<String, dynamic>> _get(String path) async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl$path'), headers: _headers)
          .timeout(timeout);
      return _parseResponse(response);
    } on SocketException {
      throw const ApiException('Cannot connect to server – check your network and server URL');
    } on TimeoutException {
      throw const ApiException('Request timed out');
    }
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl$path'),
            headers: _headers,
            body: jsonEncode(body),
          )
          .timeout(timeout);
      return _parseResponse(response);
    } on SocketException {
      throw const ApiException('Cannot connect to server – check your network and server URL');
    } on TimeoutException {
      throw const ApiException('Request timed out');
    }
  }

  Map<String, dynamic> _parseResponse(http.Response response) {
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw ApiException(
        'Invalid response format from server',
        statusCode: response.statusCode,
      );
    }

    if (!body['success'] as bool) {
      final errors = (body['errors'] as List?)?.cast<String>() ?? [];
      throw ApiException(
        body['message']?.toString() ?? 'API returned an error',
        statusCode: response.statusCode,
        errors: errors,
      );
    }

    return body;
  }

  // ── Endpoints ─────────────────────────────────────────────────────────

  /// Upload sensor data from BLE device.
  Future<Map<String, dynamic>> uploadSensor(Map<String, dynamic> sensorData) =>
      _post('/device/upload', sensorData);

  /// Upload manual farmer observations.
  Future<Map<String, dynamic>> uploadManual(Map<String, dynamic> manualData) =>
      _post('/manual/upload', manualData);

  /// Trigger AI analysis for a session.
  Future<Map<String, dynamic>> runAnalysis(String cowId, String sessionId) =>
      _post('/analyse', {'cow_id': cowId, 'session_id': sessionId});

  /// Fetch report for a session.
  Future<Map<String, dynamic>> getReport(String cowId, String sessionId) =>
      _get('/report?cow_id=$cowId&session_id=$sessionId');

  /// Fetch session history.
  Future<Map<String, dynamic>> getHistory({String? cowId, int limit = 20}) {
    final params = <String>[];
    if (cowId != null) params.add('cow_id=$cowId');
    params.add('limit=$limit');
    return _get('/history?${params.join('&')}');
  }

  /// Fetch device status.
  Future<Map<String, dynamic>> getDeviceStatus(String cowId) =>
      _get('/device/status?cow_id=$cowId');

  /// Fetch dashboard summary.
  Future<Map<String, dynamic>> getDashboard() => _get('/dashboard');

  /// Upload image file for vision analysis.
  Future<Map<String, dynamic>> uploadImage({
    required String cowId,
    required String sessionId,
    required File imageFile,
  }) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/image/upload'),
      );
      request.fields['cow_id'] = cowId;
      request.fields['session_id'] = sessionId;
      request.headers['User-Agent'] = 'AVIRA-Flutter/1.0';

      final ext = imageFile.path.split('.').last.toLowerCase();
      final contentType = ext == 'png' ? MediaType('image', 'png') : MediaType('image', 'jpeg');
      request.files.add(await http.MultipartFile.fromPath(
        'image', imageFile.path, contentType: contentType,
      ));

      final streamedResponse = await request.send().timeout(const Duration(seconds: 60));
      final response = await http.Response.fromStream(streamedResponse);
      return _parseResponse(response);
    } on SocketException {
      throw const ApiException('Cannot connect to server for image upload');
    }
  }

  /// Health check ping.
  Future<bool> ping() async {
    try {
      final uri = Uri.parse(baseUrl.replaceAll('/api/v1', '') + '/health');
      final response = await http.get(uri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}

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
  // ★ FIX: Maintained persistent fallback default states to prevent dynamic session drift 
  // on your dashboard screens.
  static String? currentCowId = 'COW_PICO_01';
  static String? currentSessionId = 'SES_LIVE_PICO_01';
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
      return {'success': false, 'message': 'Cannot connect to server – check your network and server URL'};
    } on TimeoutException {
      return {'success': false, 'message': 'Request timed out'};
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
      return {'success': false, 'message': 'Cannot connect to server – check your network and server URL'};
    } on TimeoutException {
      return {'success': false, 'message': 'Request timed out'};
    }
  }

  Map<String, dynamic> _parseResponse(http.Response response) {
    // Try to parse as JSON
    Map<String, dynamic>? body;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        body = decoded;
      } else if (decoded is Map) {
        body = decoded.cast<String, dynamic>();
      }
    } catch (_) {
      // Non-JSON response
      throw ApiException(
        'Server returned unexpected response (status ${response.statusCode})',
        statusCode: response.statusCode,
      );
    }

    if (body == null) {
      throw ApiException('Empty or invalid server response', statusCode: response.statusCode);
    }

    if (body.containsKey('success') && body['success'] == false) {
      final errors = (body['errors'] as List?)?.cast<String>() ?? [];
      throw ApiException(
        body['message']?.toString() ?? 'API returned an error',
        statusCode: response.statusCode,
        errors: errors,
      );
    }

    // Non-2xx without success:false — still throw
    if (response.statusCode >= 400) {
      throw ApiException(
        body['message']?.toString() ?? 'HTTP ${response.statusCode}',
        statusCode: response.statusCode,
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
  /// Returns the raw server response map — the caller should unwrap 'result' if present.
  Future<Map<String, dynamic>> runAnalysis(String cowId, String sessionId) async {
    try {
      final raw = await _post('/analyse', {'cow_id': cowId, 'session_id': sessionId});
      // The server wraps the pipeline output under 'result' key.
      // Flatten it so callers always get a consistent Map.
      if (raw.containsKey('result') && raw['result'] is Map<String, dynamic>) {
        return raw['result'] as Map<String, dynamic>;
      }
      return raw;
    } catch (e) {
      rethrow;
    }
  }

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

  /// Fetch_device status.
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
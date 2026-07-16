/// AVIRA – Main Dashboard Screen with BottomNavigationBar
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/app_state.dart';
import '../models/analysis_result.dart';
import '../models/sensor_data.dart';
import 'dart:async';
import '../services/api_service.dart';
import '../bluetooth/bluetooth_service.dart';
import '../utils/theme.dart';
import '../utils/i18n.dart';
import '../utils/tts_service.dart';
import 'upload_image_screen.dart';
import 'history_screen.dart';
import 'cow_simulation_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _currentTab = 0;
  final _bluetoothService = BluetoothService();

  @override
  void initState() {
    super.initState();
    _setupBluetooth();
  }

  void _setupBluetooth() {
    final appState = context.read<AppState>();
    _bluetoothService.onSensorData = (data) {
      appState.updateSensorData(data);
      // Auto-upload to backend
      _autoUploadSensor(data, appState);
    };
    _bluetoothService.onConnectionChanged = (connected, name) {
      appState.setConnected(connected: connected, deviceName: name);
    };
    _bluetoothService.onError = (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error), backgroundColor: AviraTheme.brandDanger),
        );
      }
    };
  }

  Future<void> _autoUploadSensor(SensorData data, AppState appState) async {
    try {
      final api = ApiService(baseUrl: appState.serverUrl);
      await api.uploadSensor(data.toJson(appState.cowId));
    } catch (_) {
      // Silent fail for auto-upload – show in UI separately
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = [
      _HomeTab(bluetoothService: _bluetoothService),
      _BluetoothTab(bluetoothService: _bluetoothService),
      const _ManualTab(),
      const _AnalysisTab(),
      const _SettingsTab(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          const Text('🐄 ', style: TextStyle(fontSize: 20)),
          const Text('AVIRA', style: TextStyle(
            fontWeight: FontWeight.w900,
            color: AviraTheme.brandPrimary,
            letterSpacing: 3,
          )),
          const Spacer(),
          Consumer<AppState>(builder: (_, state, __) => Text(
            state.cowId,
            style: const TextStyle(
              color: AviraTheme.brandPrimary, fontSize: 13,
              fontFamily: 'monospace', fontWeight: FontWeight.w600,
            ),
          )),
        ]),
        actions: [
          Consumer<AppState>(builder: (_, state, __) => Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Row(children: [
              Container(
                width: 8, height: 8,
                decoration: BoxDecoration(
                  color: state.isConnected ? AviraTheme.brandSuccess : AviraTheme.brandDanger,
                  shape: BoxShape.circle,
                ),
              ),
            ]),
          )),
        ],
      ),
      body: IndexedStack(index: _currentTab, children: tabs),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: Colors.white.withOpacity(0.08))),
          color: AviraTheme.bgDeep,
        ),
        child: BottomNavigationBar(
          currentIndex: _currentTab,
          onTap: (i) => setState(() => _currentTab = i),
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.transparent,
          elevation: 0,
          selectedItemColor: AviraTheme.brandPrimary,
          unselectedItemColor: AviraTheme.textMuted,
          selectedFontSize: 11,
          unselectedFontSize: 10,
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
            BottomNavigationBarItem(icon: Icon(Icons.bluetooth), label: 'Bluetooth'),
            BottomNavigationBarItem(icon: Icon(Icons.edit_note), label: 'Manual'),
            BottomNavigationBarItem(icon: Icon(Icons.psychology), label: 'Analysis'),
            BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
//  HOME TAB  (polls server every 5 s for live WiFi sensor data)
// ─────────────────────────────────────────────

class _HomeTab extends StatefulWidget {
  final BluetoothService bluetoothService;
  const _HomeTab({required this.bluetoothService});
  @override
  State<_HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<_HomeTab> {
  Timer? _pollTimer;

  // Latest values polled from the server
  double? _hr;
  double? _spo2;
  double? _motion;
  bool _hrValid = false;
  bool _spo2Valid = false;
  String _serverSessionId = '';   // Pico's real session ID from server
  DateTime? _lastSeen;
  bool _deviceOnline = false;
  bool _polling = false;

  @override
  void initState() {
    super.initState();
    // Poll immediately on open, then every 5 seconds
    WidgetsBinding.instance.addPostFrameCallback((_) => _pollServer());
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) => _pollServer());
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  // ── Poll /device/status for the cow's latest WiFi readings ────────────────
  Future<void> _pollServer() async {
    if (!mounted || _polling) return;
    _polling = true;
    try {
      final appState = context.read<AppState>();
      final api = ApiService(baseUrl: appState.serverUrl);
      final resp = await api.getDeviceStatus(appState.cowId);

      // resp = {"success": true, "device": {...}} or {"status": "OFFLINE"}
      final device = resp['device'] as Map<String, dynamic>?;
      if (device == null) {
        if (mounted) setState(() => _deviceOnline = false);
        _polling = false;
        return;
      }

      final vitals = device['latest_vitals'] as Map<String, dynamic>? ?? device;

      final hr    = _toDouble(vitals['heart_rate']);
      final spo2  = _toDouble(vitals['spo2']);
      final mot   = _toDouble(vitals['motion_magnitude']);
      final hrV   = vitals['heart_rate_valid'] == true;
      final spo2V = vitals['spo2_valid'] == true;
      final sid   = (device['session_id'] ?? vitals['session_id'] ?? '').toString();

      if (mounted) {
        setState(() {
          _hr              = hrV   ? hr   : null;
          _spo2            = spo2V ? spo2 : null;
          _motion          = mot;
          _hrValid         = hrV;
          _spo2Valid       = spo2V;
          _deviceOnline    = true;
          _lastSeen        = DateTime.now();
          if (sid.isNotEmpty) _serverSessionId = sid;
        });

        // Also update AppState so the connection dot turns green
        if (!appState.isConnected) {
          appState.setConnected(connected: true, deviceName: 'Pico W (WiFi)');
        }

        // Save the real session ID so analysis uses the correct data
        if (sid.isNotEmpty) {
          ApiService.currentSessionId = sid;
        }
      }
    } catch (_) {
      // Server unreachable or OFFLINE response – don't crash
      if (mounted) setState(() => _deviceOnline = false);
    }
    _polling = false;
  }

  double? _toDouble(dynamic v) {
    if (v == null) return null;
    return double.tryParse(v.toString());
  }

  // ── Run analysis using the server's session ID, not the app's local one ──
  Future<void> _runAnalysis(BuildContext context, AppState state) async {
    // Use the real session from Pico; fall back to app session if not yet polled
    final sessionToUse = _serverSessionId.isNotEmpty
        ? _serverSessionId
        : state.sessionId;

    state.setAnalysing(true);
    try {
      final api = ApiService(baseUrl: state.serverUrl);
      // runAnalysis() already unwraps the 'result' key
      final resultMap = await api.runAnalysis(state.cowId, sessionToUse);
      state.setAnalysisResult(AnalysisResult.fromJson(resultMap));
    } catch (e) {
      state.setAnalysing(false);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Analysis failed: $e'),
            backgroundColor: AviraTheme.brandDanger,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(builder: (context, state, _) {
      final analysis = state.latestAnalysis;

      // Prefer BLE data if connected, else show WiFi-polled values
      final bleSensor = state.latestSensor;
      final useBle    = state.isConnected && bleSensor.heartRate != null;

      final hrDisplay   = useBle
          ? (bleSensor.heartRateValid ? '${bleSensor.heartRate?.toInt() ?? "--"}' : '--')
          : (_hrValid && _hr != null ? '${_hr!.toInt()}' : '--');
      final spo2Display = useBle
          ? (bleSensor.spo2Valid ? '${bleSensor.spo2?.toStringAsFixed(1) ?? "--"}' : '--')
          : (_spo2Valid && _spo2 != null ? '${_spo2!.toStringAsFixed(1)}' : '--');
      final motDisplay  = useBle
          ? (bleSensor.motionMagnitude?.toStringAsFixed(2) ?? '--')
          : (_motion?.toStringAsFixed(2) ?? '--');

      final sessionDisplay = _serverSessionId.isNotEmpty
          ? _serverSessionId.replaceFirst('SES_', '').substring(0, 6)
          : state.sessionId.substring(4, 10);

      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Device status pill ──────────────────────────────────────────
          _deviceStatusBadge(),
          const SizedBox(height: 12),

          // Alert Banner
          if (analysis != null) _alertBanner(analysis),
          if (analysis != null) const SizedBox(height: 12),

          // Sensor grid
          _sectionTitle('Live Sensor  ${_polling ? "⟳" : ""}'),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.6,
            children: [
              _metricCard('Heart Rate', hrDisplay,   'BPM', AviraTheme.brandSuccess),
              _metricCard('SpO2',       spo2Display, '%',   AviraTheme.brandInfo),
              _metricCard('Motion',     motDisplay,  'mag', AviraTheme.brandAccent),
              _metricCard('Session',    sessionDisplay, 'ID', AviraTheme.brandPrimary),
            ],
          ),
          if (_lastSeen != null) ...[
            const SizedBox(height: 6),
            Text(
              'Last update: ${_formatAge(_lastSeen!)}',
              style: const TextStyle(color: AviraTheme.textMuted, fontSize: 10),
              textAlign: TextAlign.right,
            ),
          ],
          const SizedBox(height: 16),

          // Quick actions
          _sectionTitle('Quick Actions'),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: _actionBtn(context, '🔬 Vision', Icons.camera_alt,
              () => Navigator.push(context, MaterialPageRoute(builder: (_) => const UploadImageScreen())))),
            const SizedBox(width: 10),
            Expanded(child: _actionBtn(context, '🗂 History', Icons.history,
              () => Navigator.push(context, MaterialPageRoute(builder: (_) => const HistoryScreen())))),
          ]),
          const SizedBox(height: 10),
          ElevatedButton.icon(
            onPressed: state.isAnalysing ? null : () => _runAnalysis(context, state),
            icon: state.isAnalysing
                ? const SizedBox(width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AviraTheme.bgDark))
                : const Text('🧠'),
            label: Text(state.isAnalysing ? 'Analysing…' : 'Run AI Analysis'),
          ),

          // Session info when analysis uses a specific session
          if (_serverSessionId.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              'Will analyse session: $_serverSessionId',
              style: const TextStyle(color: AviraTheme.textMuted, fontSize: 10),
              textAlign: TextAlign.center,
            ),
          ],
          const SizedBox(height: 16),

          // Latest analysis summary
          if (analysis != null) ...[
            _sectionTitle('Latest Analysis'),
            const SizedBox(height: 8),
            ...analysis.diseaseCandidates.take(3).map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _diseaseRow(d),
            )),
          ],
        ],
      );
    });
  }

  // ── Device status badge ────────────────────────────────────────────────
  Widget _deviceStatusBadge() {
    final color  = _deviceOnline ? AviraTheme.brandSuccess : AviraTheme.textMuted;
    final label  = _deviceOnline ? '🟢 Pico W — WiFi connected' : '🔴 Waiting for device…';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(children: [
        Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
        const Spacer(),
        GestureDetector(
          onTap: _pollServer,
          child: Icon(Icons.refresh, color: color, size: 16),
        ),
      ]),
    );
  }

  String _formatAge(DateTime t) {
    final secs = DateTime.now().difference(t).inSeconds;
    if (secs < 60) return '${secs}s ago';
    return '${(secs / 60).floor()}m ago';
  }

  Widget _alertBanner(AnalysisResult analysis) {
    final color = AviraTheme.alertColor(analysis.alertLevel);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(children: [
        Text(_alertIcon(analysis.alertLevel), style: const TextStyle(fontSize: 24)),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Alert: ${analysis.alertLevel}',
            style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 14)),
          if (analysis.vetRequired)
            const Text('⚠️ Veterinary consultation required',
              style: TextStyle(color: Color(0xFFFCA5A5), fontSize: 12)),
        ])),
      ]),
    );
  }

  String _alertIcon(String level) {
    switch (level) {
      case 'CRITICAL': return '🔴';
      case 'HIGH':     return '🟠';
      case 'MODERATE': return '🟡';
      default:         return '🟢';
    }
  }

  Widget _sectionTitle(String title) => Text(
    title,
    style: const TextStyle(
      color: AviraTheme.textSecondary, fontSize: 11,
      fontWeight: FontWeight.w700, letterSpacing: 1.2,
    ),
  );

  Widget _metricCard(String label, String value, String unit, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AviraTheme.bgMedium.withOpacity(0.6),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: TextStyle(color: AviraTheme.textMuted, fontSize: 10, letterSpacing: 1)),
        const Spacer(),
        Text(value, style: TextStyle(
          color: color, fontSize: 28, fontWeight: FontWeight.w800, fontFamily: 'monospace',
        )),
        Text(unit, style: TextStyle(color: AviraTheme.textMuted, fontSize: 11)),
      ]),
    );
  }

  Widget _actionBtn(BuildContext ctx, String label, IconData icon, VoidCallback onTap) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 16),
      label: Text(label, style: const TextStyle(fontSize: 13)),
    );
  }

  Widget _diseaseRow(DiseaseCandidate d) {
    final color = d.probability >= 0.6 ? AviraTheme.brandDanger
        : d.probability >= 0.35 ? AviraTheme.brandWarning
        : AviraTheme.brandPrimary;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AviraTheme.bgMedium.withOpacity(0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(d.disease, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          const SizedBox(height: 4),
          LinearProgressIndicator(
            value: d.probability,
            backgroundColor: Colors.white.withOpacity(0.08),
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ])),
        const SizedBox(width: 10),
        Text('${(d.probability * 100).toInt()}%',
          style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 15, fontFamily: 'monospace')),
      ]),
    );
  }
}

// ─────────────────────────────────────────────
//  BLUETOOTH TAB
// ─────────────────────────────────────────────

class _BluetoothTab extends StatefulWidget {
  final BluetoothService bluetoothService;
  const _BluetoothTab({required this.bluetoothService});
  @override
  State<_BluetoothTab> createState() => _BluetoothTabState();
}

class _BluetoothTabState extends State<_BluetoothTab> {
  List<dynamic> _scanResults = [];
  bool _scanning = false;

  Future<void> _startScan() async {
    setState(() { _scanResults = []; _scanning = true; });
    widget.bluetoothService.onScanResults = (results) {
      if (mounted) setState(() => _scanResults = results);
    };
    await widget.bluetoothService.startScan();
    if (mounted) setState(() => _scanning = false);
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(builder: (context, state, _) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Connection status
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AviraTheme.bgMedium.withOpacity(0.5),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: state.isConnected
                    ? AviraTheme.brandSuccess.withOpacity(0.4)
                    : Colors.white.withOpacity(0.08),
              ),
            ),
            child: Row(children: [
              Icon(Icons.bluetooth,
                color: state.isConnected ? AviraTheme.brandSuccess : AviraTheme.textMuted),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  state.isConnected ? 'Connected' : 'Not Connected',
                  style: TextStyle(
                    color: state.isConnected ? AviraTheme.brandSuccess : AviraTheme.textMuted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (state.connectedDeviceName.isNotEmpty)
                  Text(state.connectedDeviceName,
                    style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 12)),
              ])),
              if (state.isConnected)
                OutlinedButton(
                  onPressed: () async {
                    await widget.bluetoothService.disconnect();
                  },
                  style: OutlinedButton.styleFrom(foregroundColor: AviraTheme.brandDanger,
                    side: const BorderSide(color: AviraTheme.brandDanger)),
                  child: const Text('Disconnect'),
                ),
            ]),
          ),
          const SizedBox(height: 16),

          if (!state.isConnected) ...[
            ElevatedButton.icon(
              onPressed: _scanning ? null : _startScan,
              icon: _scanning
                  ? const SizedBox(width: 16, height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: AviraTheme.bgDark))
                  : const Icon(Icons.search),
              label: Text(_scanning ? 'Scanning…' : 'Scan for AVIRA Devices'),
            ),
            const SizedBox(height: 12),

            if (_scanResults.isNotEmpty)
              Expanded(
                child: ListView.builder(
                  itemCount: _scanResults.length,
                  itemBuilder: (context, idx) {
                    final result = _scanResults[idx];
                    return ListTile(
                      leading: const Icon(Icons.bluetooth, color: AviraTheme.brandPrimary),
                      title: Text(result.device.platformName.isEmpty
                          ? 'Unknown Device' : result.device.platformName),
                      subtitle: Text(result.device.remoteId.toString()),
                      trailing: ElevatedButton(
                        onPressed: () async {
                          await widget.bluetoothService.connect(result.device);
                        },
                        child: const Text('Connect'),
                      ),
                    );
                  },
                ),
              )
            else
              Expanded(
                  child: Center(
                  child: Text(
                    _scanning
                        ? 'Searching for AVIRA_PICO devices…'
                        : 'Press Scan to discover devices',
                    style: const TextStyle(color: AviraTheme.textMuted),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
          ] else ...[
            const SizedBox(height: 8),
            const Text('📊 Live Sensor Readings',
              style: TextStyle(color: AviraTheme.textSecondary, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Consumer<AppState>(builder: (_, s, __) {
              final sensor = s.latestSensor;
              return Column(children: [
                _liveReading('Heart Rate',
                  sensor.heartRateValid ? '${sensor.heartRate?.toInt()} BPM' : 'Invalid',
                  sensor.heartRateValid ? AviraTheme.brandSuccess : AviraTheme.textMuted),
                _liveReading('SpO2',
                  sensor.spo2Valid ? '${sensor.spo2?.toStringAsFixed(1)}%' : 'Invalid',
                  sensor.spo2Valid ? AviraTheme.brandInfo : AviraTheme.textMuted),
                _liveReading('Motion', '${sensor.motionMagnitude?.toStringAsFixed(3)}', AviraTheme.brandAccent),
                _liveReading('Accel X/Y/Z',
                  '${sensor.accelX?.toStringAsFixed(3)} / ${sensor.accelY?.toStringAsFixed(3)} / ${sensor.accelZ?.toStringAsFixed(3)}',
                  AviraTheme.textSecondary),
              ]);
            }),
          ],
        ]),
      );
    });
  }

  Widget _liveReading(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: AviraTheme.bgMedium.withOpacity(0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white.withOpacity(0.07)),
        ),
        child: Row(children: [
          Text(label, style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 13)),
          const Spacer(),
          Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 13, fontFamily: 'monospace')),
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────
//  MANUAL TAB
// ─────────────────────────────────────────────

class _ManualTab extends StatefulWidget {
  const _ManualTab();
  @override
  State<_ManualTab> createState() => _ManualTabState();
}

class _ManualTabState extends State<_ManualTab> {
  final _formKey = GlobalKey<FormState>();
  final _tempCtrl  = TextEditingController();
  final _milkCtrl  = TextEditingController();
  final _appCtrl   = TextEditingController();
  final _rumCtrl   = TextEditingController();
  final _waterCtrl = TextEditingController();
  final _feedCtrl  = TextEditingController();
  final _obsCtrl   = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    for (final c in [_tempCtrl, _milkCtrl, _appCtrl, _rumCtrl, _waterCtrl, _feedCtrl, _obsCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSubmitting = true);
    final appState = context.read<AppState>();
    final api = ApiService(baseUrl: appState.serverUrl);
    try {
      await api.uploadManual({
        'cow_id': appState.cowId,
        'session_id': appState.sessionId,
        'temperature': double.tryParse(_tempCtrl.text),
        'milk_production': double.tryParse(_milkCtrl.text),
        'appetite': int.tryParse(_appCtrl.text),
        'rumination': int.tryParse(_rumCtrl.text),
        'water_intake': double.tryParse(_waterCtrl.text),
        'feed_intake': double.tryParse(_feedCtrl.text),
        'observations': _obsCtrl.text,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✅ Manual data uploaded!'),
            backgroundColor: AviraTheme.brandSuccess),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e'), backgroundColor: AviraTheme.brandDanger),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Form(
        key: _formKey,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('📝 Manual Observations',
            style: TextStyle(color: AviraTheme.textSecondary, fontWeight: FontWeight.w700, letterSpacing: 1)),
          const SizedBox(height: 4),
          Text('Session: ${context.read<AppState>().sessionId}',
            style: const TextStyle(color: AviraTheme.textMuted, fontSize: 11, fontFamily: 'monospace')),
          const SizedBox(height: 16),
          _numField(_tempCtrl, 'Body Temperature (°C)', '38.5', min: 35, max: 42),
          _numField(_milkCtrl, 'Milk Production (L/day)', '20.0'),
          _numField(_appCtrl, 'Appetite (0-10)', '7', isInt: true, min: 0, max: 10),
          _numField(_rumCtrl, 'Rumination (0-10)', '7', isInt: true, min: 0, max: 10),
          _numField(_waterCtrl, 'Water Intake (L/day)', '80'),
          _numField(_feedCtrl, 'Feed Intake (kg/day)', '15'),
          const SizedBox(height: 4),
          TextFormField(
            controller: _obsCtrl,
            maxLines: 3,
            style: const TextStyle(color: AviraTheme.textPrimary),
            decoration: const InputDecoration(
              labelText: 'Observations (optional)',
              hintText: 'Describe any symptoms, behaviour changes…',
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _isSubmitting ? null : _submit,
            style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
            child: _isSubmitting
                ? const CircularProgressIndicator(strokeWidth: 2, color: AviraTheme.bgDark)
                : const Text('📤 Upload Observations'),
          ),
        ]),
      ),
    );
  }

  Widget _numField(TextEditingController ctrl, String label, String hint,
      {bool isInt = false, double? min, double? max}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: ctrl,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        style: const TextStyle(color: AviraTheme.textPrimary),
        decoration: InputDecoration(labelText: label, hintText: hint),
        validator: (v) {
          if (v == null || v.isEmpty) return null;
          final n = double.tryParse(v);
          if (n == null) return 'Enter a valid number';
          if (min != null && n < min) return 'Minimum is $min';
          if (max != null && n > max) return 'Maximum is $max';
          return null;
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────
//  ANALYSIS TAB
// ─────────────────────────────────────────────

class _AnalysisTab extends StatelessWidget {
  const _AnalysisTab();

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(builder: (context, state, _) {
      final analysis = state.latestAnalysis;

      if (analysis == null) {
        return Center(
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Text('🧠', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 16),
            const Text('No analysis run yet',
              style: TextStyle(color: AviraTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text('Upload sensor or manual data,\nthen press Run AI Analysis on the Dashboard.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AviraTheme.textMuted, fontSize: 13)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: state.isAnalysing ? null : () => _runAnalysis(context, state),
              icon: const Text('🧠'),
              label: const Text('Run AI Analysis'),
            ),
          ]),
        );
      }

      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Confidence bar
          _AnalysisSection(
            title: 'Pipeline Confidence',
            child: Column(children: [
              Row(children: [
                Expanded(child: LinearProgressIndicator(
                  value: analysis.pipelineConfidence,
                  backgroundColor: Colors.white.withOpacity(0.08),
                  valueColor: const AlwaysStoppedAnimation<Color>(AviraTheme.brandPrimary),
                  minHeight: 8,
                  borderRadius: BorderRadius.circular(4),
                )),
                const SizedBox(width: 10),
                Text('${(analysis.pipelineConfidence * 100).toInt()}%',
                  style: const TextStyle(color: AviraTheme.brandPrimary, fontWeight: FontWeight.w800)),
              ]),
            ]),
          ),
          const SizedBox(height: 12),

          // Vet required
          if (analysis.vetRequired)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AviraTheme.brandDanger.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AviraTheme.brandDanger.withOpacity(0.4)),
              ),
              child: const Row(children: [
                Text('⚠️', style: TextStyle(fontSize: 20)),
                SizedBox(width: 10),
                Expanded(child: Text('Veterinary consultation required',
                  style: TextStyle(color: Color(0xFFFCA5A5), fontWeight: FontWeight.w700))),
              ]),
            ),
          const SizedBox(height: 12),

          // Disease candidates
          const Text('Disease Probability Indicators',
            style: TextStyle(color: AviraTheme.textMuted, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1)),
          const SizedBox(height: 4),
          const Text('⚠️ These are monitoring indicators, NOT diagnoses.',
            style: TextStyle(color: AviraTheme.textMuted, fontSize: 10)),
          const SizedBox(height: 8),
          ...analysis.diseaseCandidates.take(3).map((d) {
            final color = d.probability >= 0.6 ? AviraTheme.brandDanger
                : d.probability >= 0.35 ? AviraTheme.brandWarning
                : AviraTheme.brandPrimary;
            return _DiseaseCandidateTile(disease: d, color: color);
          }),
          const SizedBox(height: 12),

          // Recommendations
          _AnalysisSection(
            title: '📋 Recommendations',
            child: Column(children: analysis.recommendations.take(6).map((r) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    width: 6, height: 6, margin: const EdgeInsets.only(top: 5, right: 8),
                    decoration: BoxDecoration(
                      color: r.priority == 1 ? AviraTheme.brandDanger
                           : r.priority <= 3 ? AviraTheme.brandWarning
                           : AviraTheme.brandInfo,
                      shape: BoxShape.circle,
                    ),
                  ),
                  Expanded(child: Text(r.action,
                    style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 13))),
                ]),
              );
            }).toList()),
          ),
        ],
      );
    });
  }

  Future<void> _runAnalysis(BuildContext context, AppState state) async {
    state.setAnalysing(true);
    try {
      final api = ApiService(baseUrl: state.serverUrl);
      final resp = await api.runAnalysis(state.cowId, state.sessionId);
      state.setAnalysisResult(AnalysisResult.fromJson(resp));
    } catch (e) {
      state.setError('Analysis failed: $e');
    }
  }
}

class _DiseaseCandidateTile extends StatefulWidget {
  final DiseaseCandidate disease;
  final Color color;
  const _DiseaseCandidateTile({required this.disease, required this.color});
  @override
  State<_DiseaseCandidateTile> createState() => _DiseaseCandidateTileState();
}

class _DiseaseCandidateTileState extends State<_DiseaseCandidateTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final d = widget.disease;
    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AviraTheme.bgMedium.withOpacity(0.5),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: widget.color.withOpacity(0.25)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(d.disease,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14))),
            Text('${(d.probability * 100).toInt()}%',
              style: TextStyle(color: widget.color, fontWeight: FontWeight.w800, fontSize: 15)),
            const SizedBox(width: 4),
            Icon(_expanded ? Icons.expand_less : Icons.expand_more,
              color: AviraTheme.textMuted, size: 18),
          ]),
          const SizedBox(height: 6),
          LinearProgressIndicator(
            value: d.probability,
            backgroundColor: Colors.white.withOpacity(0.08),
            valueColor: AlwaysStoppedAnimation<Color>(widget.color),
            borderRadius: BorderRadius.circular(3),
          ),
          const SizedBox(height: 4),
          Row(children: [
            _chip(d.confidence, AviraTheme.brandInfo),
            const SizedBox(width: 6),
            _chip(d.urgency, widget.color),
          ]),
          if (_expanded) ...[
            const SizedBox(height: 8),
            ...d.matchedEvidence.take(3).map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Row(children: [
                const Text('✓ ', style: TextStyle(color: AviraTheme.brandSuccess, fontSize: 12)),
                Expanded(child: Text(e, style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 11))),
              ]),
            )),
          ],
        ]),
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }
}

class _AnalysisSection extends StatelessWidget {
  final String title;
  final Widget child;
  const _AnalysisSection({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AviraTheme.bgMedium.withOpacity(0.4),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(
          color: AviraTheme.textSecondary, fontSize: 12,
          fontWeight: FontWeight.w700, letterSpacing: 0.5)),
        const SizedBox(height: 8),
        child,
      ]),
    );
  }
}

// ─────────────────────────────────────────────
//  SETTINGS TAB
// ─────────────────────────────────────────────

class _SettingsTab extends StatefulWidget {
  const _SettingsTab();
  @override
  State<_SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends State<_SettingsTab> {
  late TextEditingController _cowCtrl;
  late TextEditingController _urlCtrl;
  bool _ttsTestRunning = false;

  @override
  void initState() {
    super.initState();
    final state = context.read<AppState>();
    _cowCtrl = TextEditingController(text: state.cowId);
    _urlCtrl = TextEditingController(text: state.serverUrl);
    // Init TTS on first load
    TtsService.instance.init();
  }

  @override
  void dispose() {
    _cowCtrl.dispose();
    _urlCtrl.dispose();
    super.dispose();
  }

  // ── Language picker ────────────────────────────────────────────────
  void _showLanguagePicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AviraTheme.bgDark,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Select Language / भाषा चुनें',
              style: TextStyle(
                color: AviraTheme.brandPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: AviraI18n.supportedLanguages.map((lang) {
                final isSelected = AviraI18n.currentLang == lang['code'];
                return GestureDetector(
                  onTap: () async {
                    AviraI18n.setLanguage(lang['code']!);
                    await TtsService.instance.setLanguage(lang['code']!);
                    if (mounted) setState(() {});
                    Navigator.pop(ctx);
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('Language set: ${lang['name']}'),
                          backgroundColor: AviraTheme.brandSuccess,
                        ),
                      );
                    }
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AviraTheme.brandPrimary.withOpacity(0.15)
                          : AviraTheme.bgMedium,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isSelected ? AviraTheme.brandPrimary : Colors.white12,
                        width: isSelected ? 1.5 : 0.5,
                      ),
                    ),
                    child: Text(
                      lang['name']!,
                      style: TextStyle(
                        color: isSelected ? AviraTheme.brandPrimary : Colors.white70,
                        fontWeight: isSelected ? FontWeight.w700 : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  // ── TTS test ───────────────────────────────────────────────────────
  Future<void> _testTTS() async {
    setState(() => _ttsTestRunning = true);
    try {
      await TtsService.instance.speakAlert('NORMAL', 'No disease detected');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('TTS error: $e'), backgroundColor: AviraTheme.brandDanger),
        );
      }
    } finally {
      if (mounted) setState(() => _ttsTestRunning = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentLangName = AviraI18n.supportedLanguages
        .firstWhere((l) => l['code'] == AviraI18n.currentLang,
            orElse: () => {'name': 'English'})
        .values
        .first;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('⚙️ Settings',
          style: TextStyle(
            color: AviraTheme.textSecondary,
            fontWeight: FontWeight.w700,
            fontSize: 15,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 16),

        // ── Server & Animal ──────────────────────────────────────────
        TextFormField(
          controller: _cowCtrl,
          style: const TextStyle(color: AviraTheme.textPrimary, fontFamily: 'monospace'),
          decoration: const InputDecoration(
            labelText: 'Default Cow ID',
            prefixIcon: Icon(Icons.pets, color: AviraTheme.brandPrimary),
          ),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _urlCtrl,
          style: const TextStyle(
            color: AviraTheme.textPrimary,
            fontFamily: 'monospace',
            fontSize: 12,
          ),
          decoration: const InputDecoration(
            labelText: 'Backend Server URL',
            prefixIcon: Icon(Icons.cloud, color: AviraTheme.brandPrimary),
          ),
        ),
        const SizedBox(height: 16),

        ElevatedButton(
          onPressed: () async {
            final state = context.read<AppState>();
            await state.setCowId(_cowCtrl.text);
            await state.setServerUrl(_urlCtrl.text);
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('✅ Settings saved'),
                  backgroundColor: AviraTheme.brandSuccess,
                ),
              );
            }
          },
          child: const Text('💾 Save Settings'),
        ),

        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: () {
            context.read<AppState>().newSession();
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('🔄 New session started'),
                backgroundColor: AviraTheme.brandInfo,
              ),
            );
          },
          icon: const Icon(Icons.refresh),
          label: const Text('Start New Session'),
        ),

        const SizedBox(height: 24),

        // ── Language Settings ────────────────────────────────────────
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AviraTheme.bgMedium.withOpacity(0.5),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '🌍 Language / भाषा',
                style: TextStyle(
                  color: AviraTheme.brandPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Supports: EN, हिंदी, ಕನ್ನಡ, தமிழ், తెలుగు, मराठी, ગુજ, বাংলা',
                style: TextStyle(color: AviraTheme.textMuted, fontSize: 11),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _showLanguagePicker,
                      icon: const Text('🌐', style: TextStyle(fontSize: 16)),
                      label: Text(
                        'Current: ${AviraI18n.currentLang.toUpperCase()} ($currentLangName)',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // ── TTS Settings ─────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AviraTheme.bgMedium.withOpacity(0.5),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '🔊 Voice Alerts (TTS)',
                style: TextStyle(
                  color: AviraTheme.brandPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Health alerts are spoken in the selected Indian language',
                style: TextStyle(color: AviraTheme.textMuted, fontSize: 11),
              ),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AviraTheme.brandSecondary,
                  foregroundColor: Colors.white,
                ),
                onPressed: _ttsTestRunning ? null : _testTTS,
                icon: _ttsTestRunning
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.volume_up),
                label: Text(_ttsTestRunning ? 'Speaking...' : 'Test Voice Alert'),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // ── Digital Cow Twin ─────────────────────────────────────────
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AviraTheme.bgMedium.withOpacity(0.5),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AviraTheme.brandPrimary.withOpacity(0.25)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '🐄 Digital Cow Twin',
                style: TextStyle(
                  color: AviraTheme.brandPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'View animated cow body with disease region highlighting',
                style: TextStyle(color: AviraTheme.textMuted, fontSize: 11),
              ),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AviraTheme.brandPrimary,
                  foregroundColor: AviraTheme.bgDark,
                ),
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const CowSimulationScreen(),
                  ),
                ),
                icon: const Text('🐄', style: TextStyle(fontSize: 18)),
                label: const Text(
                  'Open Digital Twin',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // ── About ────────────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AviraTheme.bgMedium.withOpacity(0.4),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.white.withOpacity(0.07)),
          ),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'About AVIRA v2',
                style: TextStyle(
                  color: AviraTheme.textSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'Version: 2.0.0\n'
                'Pipeline: 12 AI Agents\n'
                'LLM: NVIDIA NIM (Llama 3.1 Nemotron)\n'
                'Algorithms: ARIMA, Isolation Forest,\n'
                '            DeepSurv, XGBoost, PPO\n'
                'Knowledge Base: 16 diseases\n'
                'Hardware: MAX30102 + MPU6500 (Pico W)\n'
                'Languages: EN/HI/KN/TA/TE/MR/GU/BN\n'
                'By: PRANIVA',
                style: TextStyle(
                  color: AviraTheme.textMuted,
                  fontSize: 12,
                  height: 1.7,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 40),
      ],
    );
  }
}

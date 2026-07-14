/// AVIRA – Report Viewer Screen
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../models/app_state.dart';
import '../models/analysis_result.dart';
import '../services/api_service.dart';
import '../utils/theme.dart';

class ReportScreen extends StatefulWidget {
  final String cowId;
  final String sessionId;

  const ReportScreen({
    super.key,
    required this.cowId,
    required this.sessionId,
  });

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _reportData;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _loadReport();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadReport() async {
    setState(() { _isLoading = true; _errorMessage = null; });
    final appState = context.read<AppState>();
    try {
      final api = ApiService(baseUrl: appState.serverUrl);
      final resp = await api.getReport(widget.cowId, widget.sessionId);
      setState(() { _reportData = resp; _isLoading = false; });
    } catch (e) {
      setState(() { _errorMessage = e.toString(); _isLoading = false; });
    }
  }

  void _copyReport() {
    final text = _reportData?['report_text'] ?? _reportData?['report_preview'] ?? '';
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('📋 Report copied to clipboard'),
        backgroundColor: AviraTheme.brandSuccess),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.cowId,
            style: const TextStyle(color: AviraTheme.brandPrimary, fontFamily: 'monospace', fontSize: 16)),
          Text(widget.sessionId,
            style: const TextStyle(color: AviraTheme.textMuted, fontSize: 10, fontFamily: 'monospace')),
        ]),
        actions: [
          IconButton(icon: const Icon(Icons.copy), onPressed: _copyReport, tooltip: 'Copy'),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadReport, tooltip: 'Refresh'),
        ],
        bottom: TabBar(
          controller: _tabCtrl,
          indicatorColor: AviraTheme.brandPrimary,
          labelColor: AviraTheme.brandPrimary,
          unselectedLabelColor: AviraTheme.textMuted,
          tabs: const [
            Tab(text: 'Summary'),
            Tab(text: 'Diseases'),
            Tab(text: 'Raw Report'),
          ],
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: AviraTheme.brandPrimary));
    }
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.error_outline, color: AviraTheme.brandDanger, size: 48),
            const SizedBox(height: 12),
            Text(_errorMessage!, textAlign: TextAlign.center,
              style: const TextStyle(color: AviraTheme.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadReport, child: const Text('Retry')),
          ]),
        ),
      );
    }

    return TabBarView(
      controller: _tabCtrl,
      children: [
        _SummaryTab(reportData: _reportData ?? {}),
        _DiseasesTab(reportData: _reportData ?? {}),
        _RawReportTab(reportData: _reportData ?? {}),
      ],
    );
  }
}

class _SummaryTab extends StatelessWidget {
  final Map<String, dynamic> reportData;
  const _SummaryTab({required this.reportData});

  @override
  Widget build(BuildContext context) {
    final files = List<String>.from(reportData['files_available'] ?? []);
    final preview = reportData['report_preview'] as String? ?? '';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Files available
        if (files.isNotEmpty) ...[
          const Text('Available Files',
            style: TextStyle(color: AviraTheme.textMuted, fontSize: 11,
              fontWeight: FontWeight.w700, letterSpacing: 1)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: files.map((f) => Chip(
              label: Text(f, style: const TextStyle(fontSize: 11)),
              backgroundColor: AviraTheme.bgMedium,
              side: BorderSide(color: Colors.white.withOpacity(0.1)),
              padding: EdgeInsets.zero,
            )).toList(),
          ),
          const SizedBox(height: 16),
        ],

        // Report available
        _infoRow('Report Available', reportData['report_available'] == true ? '✅ Yes' : '❌ No'),
        _infoRow('Prediction Available', reportData['prediction_available'] == true ? '✅ Yes' : '❌ No'),
        const SizedBox(height: 12),

        if (preview.isNotEmpty) ...[
          const Text('Report Preview',
            style: TextStyle(color: AviraTheme.textMuted, fontSize: 11,
              fontWeight: FontWeight.w700, letterSpacing: 1)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AviraTheme.bgMedium.withOpacity(0.4),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.white.withOpacity(0.07)),
            ),
            child: SelectableText(
              preview,
              style: const TextStyle(
                fontFamily: 'monospace', fontSize: 12,
                color: AviraTheme.textSecondary, height: 1.6,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Text(label, style: const TextStyle(color: AviraTheme.textMuted, fontSize: 13)),
        const Spacer(),
        Text(value, style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 13, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _DiseasesTab extends StatelessWidget {
  final Map<String, dynamic> reportData;
  const _DiseasesTab({required this.reportData});

  @override
  Widget build(BuildContext context) {
    // The report is a text report; diseases not structured here.
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text('🦠', style: TextStyle(fontSize: 48)),
          SizedBox(height: 12),
          Text('Disease probability data is available in the Analysis tab\nof the Dashboard.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AviraTheme.textMuted)),
        ]),
      ),
    );
  }
}

class _RawReportTab extends StatelessWidget {
  final Map<String, dynamic> reportData;
  const _RawReportTab({required this.reportData});

  @override
  Widget build(BuildContext context) {
    final text = reportData['report_text'] ?? reportData['report_preview'] ?? 'No report text available.';
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Container(
        decoration: BoxDecoration(
          color: AviraTheme.bgMedium.withOpacity(0.3),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white.withOpacity(0.07)),
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(12),
          child: SelectableText(
            text.toString(),
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 11,
              color: AviraTheme.textSecondary,
              height: 1.7,
            ),
          ),
        ),
      ),
    );
  }
}

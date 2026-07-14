/// AVIRA – Session History Screen
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/app_state.dart';
import '../services/api_service.dart';
import '../utils/theme.dart';
import 'report_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _sessions = [];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() { _isLoading = true; _errorMessage = null; });
    final appState = context.read<AppState>();
    try {
      final api = ApiService(baseUrl: appState.serverUrl);
      final resp = await api.getHistory(cowId: appState.cowId, limit: 30);
      setState(() {
        _sessions = List<Map<String, dynamic>>.from(resp['sessions'] ?? []);
        _isLoading = false;
      });
    } catch (e) {
      setState(() { _errorMessage = e.toString(); _isLoading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🗂 Session History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadHistory,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AviraTheme.brandPrimary),
      );
    }
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.error_outline, color: AviraTheme.brandDanger, size: 48),
            const SizedBox(height: 12),
            Text(_errorMessage!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AviraTheme.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadHistory, child: const Text('Retry')),
          ]),
        ),
      );
    }
    if (_sessions.isEmpty) {
      return Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Text('🗂', style: TextStyle(fontSize: 48)),
          const SizedBox(height: 12),
          const Text('No sessions yet',
            style: TextStyle(color: AviraTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const Text('Upload sensor or manual data to create a session.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AviraTheme.textMuted)),
        ]),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadHistory,
      color: AviraTheme.brandPrimary,
      backgroundColor: AviraTheme.bgMedium,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _sessions.length,
        itemBuilder: (context, index) {
          final session = _sessions[index];
          return _SessionCard(session: session);
        },
      ),
    );
  }
}

class _SessionCard extends StatelessWidget {
  final Map<String, dynamic> session;
  const _SessionCard({required this.session});

  @override
  Widget build(BuildContext context) {
    final cowId    = session['cow_id']?.toString()    ?? '—';
    final sessionId = session['session_id']?.toString() ?? '—';
    final date     = session['date']?.toString()      ?? '';
    final files    = List<String>.from(session['files'] ?? []);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ReportScreen(cowId: cowId, sessionId: sessionId),
          ),
        ),
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Container(
              width: 42, height: 42,
              decoration: BoxDecoration(
                color: AviraTheme.brandPrimary.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Center(child: Text('🐄', style: TextStyle(fontSize: 20))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(cowId,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 14,
                    color: AviraTheme.brandPrimary, fontFamily: 'monospace',
                  ),
                ),
                const SizedBox(height: 2),
                Text(sessionId,
                  style: const TextStyle(
                    color: AviraTheme.textMuted, fontSize: 11, fontFamily: 'monospace',
                  ),
                ),
                if (date.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(_formatDate(date),
                    style: const TextStyle(color: AviraTheme.textMuted, fontSize: 11)),
                ],
                if (files.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 4,
                    children: files.take(4).map((f) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.06),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: Text(f, style: const TextStyle(fontSize: 9, color: AviraTheme.textMuted)),
                    )).toList(),
                  ),
                ],
              ]),
            ),
            const Icon(Icons.chevron_right, color: AviraTheme.textMuted, size: 20),
          ]),
        ),
      ),
    );
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      return '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return dateStr;
    }
  }
}

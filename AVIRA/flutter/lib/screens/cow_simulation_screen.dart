/// AVIRA – Digital Cow Simulation Screen
/// Full-screen view of the animated cow digital twin with disease overlay,
/// TTS report reading, and regional language support.
/// PRANIVA – Advanced Veterinary Intelligence Research & Analytics
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../utils/theme.dart';
import '../utils/i18n.dart';
import '../utils/tts_service.dart';
import '../widgets/cow_simulation.dart';
import '../services/api_service.dart';

class CowSimulationScreen extends StatefulWidget {
  const CowSimulationScreen({super.key});

  @override
  State<CowSimulationScreen> createState() => _CowSimulationScreenState();
}

class _CowSimulationScreenState extends State<CowSimulationScreen> {
  Map<String, dynamic>? _analysis;
  bool _loading = false;
  bool _speaking = false;
  String _errorMsg = '';

  @override
  void initState() {
    super.initState();
    _loadAnalysis();
  }

  // ── Load latest analysis from API ─────────────────────────────────────────

  Future<void> _loadAnalysis() async {
    setState(() {
      _loading = true;
      _errorMsg = '';
    });

    try {
      final prefs = await _getPrefs();
      final cowId = prefs['cow_id'] ?? 'COW_001';
      final sessionId = prefs['session_id'] ?? '';

      if (sessionId.isEmpty) {
        setState(() {
          _loading = false;
          _errorMsg = 'No active session. Run an analysis first.';
        });
        return;
      }

      final result = await ApiService.fetchReport(cowId, sessionId);
      if (result != null) {
        setState(() => _analysis = result);
      } else {
        setState(() => _errorMsg = 'No analysis found for $cowId');
      }
    } catch (e) {
      setState(() => _errorMsg = 'Error loading analysis: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<Map<String, String>> _getPrefs() async {
    final prefs = <String, String>{};
    try {
      final sp = await _loadSharedPrefs();
      return sp;
    } catch (_) {
      return prefs;
    }
  }

  Future<Map<String, String>> _loadSharedPrefs() async {
    // Using ApiService state which has SharedPreferences loaded
    return {
      'cow_id': ApiService.currentCowId ?? 'COW_001',
      'session_id': ApiService.currentSessionId ?? '',
    };
  }

  // ── TTS: Speak the health report ──────────────────────────────────────────

  Future<void> _speakReport() async {
    if (_analysis == null) {
      _showSnack('No analysis loaded. Cannot speak report.');
      return;
    }

    final tts = TtsService.instance;
    final alertLevel = (_analysis!['final_alert'] ??
            _analysis!['alert_level'] ??
            'NORMAL')
        .toString()
        .toUpperCase();

    final candidates = _analysis!['top_diseases'] as List? ??
        _analysis!['disease_candidates'] as List? ??
        [];

    final topDisease = candidates.isNotEmpty
        ? (candidates[0]['disease'] ?? 'Unknown').toString()
        : 'No specific condition detected';

    final narrative = (_analysis!['llm_narrative'] ?? '').toString();

    setState(() => _speaking = true);

    try {
      if (narrative.isNotEmpty) {
        await tts.speak(narrative);
      } else {
        await tts.speakAlert(alertLevel, topDisease);
      }
    } catch (e) {
      _showSnack('TTS error: $e');
    } finally {
      if (mounted) setState(() => _speaking = false);
    }
  }

  Future<void> _stopSpeaking() async {
    await TtsService.instance.stop();
    if (mounted) setState(() => _speaking = false);
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: AviraTheme.cardBg,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // ── Disease body region legend ─────────────────────────────────────────────

  Widget _buildRegionLegend() {
    final regions = [
      {'icon': '🐮', 'region': 'Head / Mouth', 'diseases': 'FMD, LSD, Theileriosis'},
      {'icon': '🫁', 'region': 'Chest / Lungs', 'diseases': 'Pneumonia, Babesiosis'},
      {'icon': '🟤', 'region': 'Abdomen / Rumen', 'diseases': 'Bloat, Johne\'s, Worms'},
      {'icon': '🍼', 'region': 'Udder', 'diseases': 'Mastitis'},
      {'icon': '🦶', 'region': 'Legs / Hooves', 'diseases': 'FMD, Tick Fever'},
      {'icon': '🔴', 'region': 'Skin', 'diseases': 'LSD, Heat Stress, Theileriosis'},
      {'icon': '❤️', 'region': 'Heart Region', 'diseases': 'Babesiosis, Theileriosis'},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            'Body Region Map',
            style: TextStyle(
              color: AviraTheme.brandPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 14,
              fontFamily: 'Inter',
            ),
          ),
        ),
        ...regions.map((r) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Text(r['icon']!, style: const TextStyle(fontSize: 18)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          r['region']!,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                          ),
                        ),
                        Text(
                          r['diseases']!,
                          style: TextStyle(
                            color: AviraTheme.textMuted,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            )),
      ],
    );
  }

  // ── Disease probability list ──────────────────────────────────────────────

  Widget _buildDiseaseList() {
    final candidates = _analysis == null
        ? <dynamic>[]
        : (_analysis!['top_diseases'] as List? ??
            _analysis!['disease_candidates'] as List? ??
            []);

    if (candidates.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          AviraI18n.t('no_data'),
          style: TextStyle(color: AviraTheme.textMuted, fontSize: 13),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            AviraI18n.t('disease_alert'),
            style: TextStyle(
              color: AviraTheme.brandPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 14,
              fontFamily: 'Inter',
            ),
          ),
        ),
        ...candidates.take(5).map<Widget>((d) {
          final name = (d['disease'] ?? 'Unknown').toString();
          final prob = ((d['probability'] ?? 0.0) as num).toDouble();
          final urgency =
              (d['urgency'] ?? 'MEDIUM').toString().toUpperCase();
          final vetRequired = d['vet_required'] == true;

          Color barColor;
          if (prob >= 0.6) {
            barColor = AviraTheme.alertCritical;
          } else if (prob >= 0.35) {
            barColor = AviraTheme.alertHigh;
          } else {
            barColor = AviraTheme.brandPrimary;
          }

          return Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AviraTheme.cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AviraTheme.borderGlass),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        name,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    if (vetRequired)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AviraTheme.alertCritical.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                              color: AviraTheme.alertCritical, width: 0.5),
                        ),
                        child: Text(
                          '⚕ VET',
                          style: TextStyle(
                            color: AviraTheme.alertCritical,
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: prob.clamp(0.0, 1.0),
                          backgroundColor: Colors.white12,
                          valueColor: AlwaysStoppedAnimation<Color>(barColor),
                          minHeight: 6,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${(prob * 100).toStringAsFixed(0)}%',
                      style: TextStyle(
                        color: barColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        fontFamily: 'JetBrains Mono',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Urgency: $urgency',
                  style: TextStyle(color: AviraTheme.textMuted, fontSize: 10),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  // ── LLM Narrative ─────────────────────────────────────────────────────────

  Widget _buildNarrative() {
    final narrative = _analysis?['llm_narrative'] as String? ?? '';
    if (narrative.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(top: 12, bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AviraTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AviraTheme.brandPrimary.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🧠', style: TextStyle(fontSize: 16)),
              const SizedBox(width: 6),
              Text(
                'AI Clinical Narrative',
                style: TextStyle(
                  color: AviraTheme.brandPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF76B900).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                      color: const Color(0xFF76B900).withOpacity(0.5),
                      width: 0.5),
                ),
                child: const Text(
                  'NVIDIA NIM',
                  style: TextStyle(
                    color: Color(0xFF76B900),
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            narrative,
            style: TextStyle(
              color: AviraTheme.textSecondary,
              fontSize: 12.5,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  // ── Survival Risk Summary ─────────────────────────────────────────────────

  Widget _buildRiskSummary() {
    final survival = _analysis?['survival_risk'] as Map? ?? {};
    final structured = _analysis?['structured_risk'] as Map? ?? {};
    final trend = _analysis?['temporal_trend'] as Map? ?? {};

    if (survival.isEmpty && structured.isEmpty) return const SizedBox.shrink();

    final risk24h = ((survival['risk_24h'] ?? 0.0) as num).toDouble();
    final healthScore =
        ((structured['health_score'] ?? 50.0) as num).toDouble();
    final trendDir =
        (trend['trend_direction'] ?? 'INSUFFICIENT_DATA').toString();

    Color trendColor;
    String trendIcon;
    switch (trendDir) {
      case 'WORSENING':
        trendColor = AviraTheme.alertCritical;
        trendIcon = '↘ WORSENING';
        break;
      case 'IMPROVING':
        trendColor = const Color(0xFF6BCB77);
        trendIcon = '↗ IMPROVING';
        break;
      case 'STABLE':
        trendColor = AviraTheme.alertModerate;
        trendIcon = '→ STABLE';
        break;
      default:
        trendColor = AviraTheme.textMuted;
        trendIcon = '? UNKNOWN';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AviraTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AviraTheme.borderGlass),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Risk & Trend Summary',
            style: TextStyle(
              color: AviraTheme.brandPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _riskChip('Health Score', '${healthScore.toStringAsFixed(0)}/100',
                  healthScore >= 70
                      ? const Color(0xFF6BCB77)
                      : healthScore >= 40
                          ? AviraTheme.alertModerate
                          : AviraTheme.alertCritical),
              const SizedBox(width: 8),
              _riskChip('24h Risk', '${(risk24h * 100).toStringAsFixed(0)}%',
                  risk24h < 0.2
                      ? const Color(0xFF6BCB77)
                      : risk24h < 0.5
                          ? AviraTheme.alertModerate
                          : AviraTheme.alertCritical),
              const SizedBox(width: 8),
              _riskChip('Trend', trendIcon, trendColor),
            ],
          ),
        ],
      ),
    );
  }

  Widget _riskChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(
          children: [
            Text(
              label,
              style: TextStyle(
                  color: AviraTheme.textMuted,
                  fontSize: 9,
                  fontWeight: FontWeight.w500),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 3),
            Text(
              value,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                fontFamily: 'JetBrains Mono',
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  // ── Main Build ────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final alertLevel = _analysis == null
        ? 'NORMAL'
        : (_analysis!['final_alert'] ?? _analysis!['alert_level'] ?? 'NORMAL')
            .toString()
            .toUpperCase();

    return Scaffold(
      backgroundColor: AviraTheme.bgDeep,
      appBar: AppBar(
        backgroundColor: AviraTheme.bgCard,
        foregroundColor: Colors.white,
        title: Row(
          children: [
            const Text('🐄', style: TextStyle(fontSize: 20)),
            const SizedBox(width: 8),
            Text(
              'Digital Twin',
              style: TextStyle(
                color: AviraTheme.brandPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 18,
                fontFamily: 'Inter',
              ),
            ),
          ],
        ),
        actions: [
          // Language badge
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: TextButton(
              onPressed: () => _showLanguagePicker(context),
              child: Text(
                AviraI18n.currentLang.toUpperCase(),
                style: TextStyle(
                  color: AviraTheme.brandPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
            ),
          ),
          // Speak / Stop TTS button
          IconButton(
            icon: Icon(
              _speaking ? Icons.stop_circle_outlined : Icons.volume_up_rounded,
              color: _speaking ? AviraTheme.alertCritical : AviraTheme.brandPrimary,
            ),
            tooltip: _speaking ? 'Stop Speaking' : 'Speak Report',
            onPressed: _speaking ? _stopSpeaking : _speakReport,
          ),
          // Refresh
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Colors.white54),
            tooltip: 'Refresh',
            onPressed: _loadAnalysis,
          ),
        ],
      ),
      body: _loading
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(
                      color: AviraTheme.brandPrimary),
                  const SizedBox(height: 16),
                  Text(
                    AviraI18n.t('loading'),
                    style: TextStyle(color: AviraTheme.textMuted),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              color: AviraTheme.brandPrimary,
              backgroundColor: AviraTheme.bgCard,
              onRefresh: _loadAnalysis,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ── Error state ──────────────────────────────────────
                    if (_errorMsg.isNotEmpty)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AviraTheme.alertCritical.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                          border:
                              Border.all(color: AviraTheme.alertCritical.withOpacity(0.4)),
                        ),
                        child: Text(
                          '⚠️ $_errorMsg',
                          style: TextStyle(
                              color: AviraTheme.alertCritical, fontSize: 13),
                        ),
                      ),

                    // ── Cow Simulation Widget ────────────────────────────
                    CowSimulationWidget(
                      analysisResult: _analysis,
                      alertLevel: alertLevel,
                    ),

                    const SizedBox(height: 16),

                    // ── Speak Report Button ──────────────────────────────
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _speaking
                              ? AviraTheme.alertCritical
                              : AviraTheme.brandPrimary,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                        icon: Icon(
                          _speaking
                              ? Icons.stop_rounded
                              : Icons.record_voice_over_rounded,
                        ),
                        label: Text(
                          _speaking
                              ? 'Stop Speaking'
                              : 'Speak Report (${AviraI18n.currentLang.toUpperCase()})',
                          style: const TextStyle(
                              fontWeight: FontWeight.w700, fontSize: 14),
                        ),
                        onPressed: _speaking ? _stopSpeaking : _speakReport,
                      ),
                    ),

                    const SizedBox(height: 16),

                    // ── Survival / risk summary ──────────────────────────
                    _buildRiskSummary(),

                    // ── LLM Narrative ────────────────────────────────────
                    _buildNarrative(),

                    // ── Disease list ─────────────────────────────────────
                    _buildDiseaseList(),

                    const SizedBox(height: 12),

                    // ── Region legend ────────────────────────────────────
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AviraTheme.cardBg,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AviraTheme.borderGlass),
                      ),
                      child: _buildRegionLegend(),
                    ),

                    const SizedBox(height: 80),
                  ],
                ),
              ),
            ),
    );
  }

  // ── Language picker bottom sheet ──────────────────────────────────────────

  void _showLanguagePicker(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AviraTheme.bgCard,
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
                    await TtsService.instance
                        .setLanguage(lang['code']!);
                    if (mounted) setState(() {});
                    Navigator.pop(ctx);
                    _showSnack('Language: ${lang['name']}');
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AviraTheme.brandPrimary.withOpacity(0.2)
                          : AviraTheme.bgDeep,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isSelected
                            ? AviraTheme.brandPrimary
                            : AviraTheme.borderGlass,
                        width: isSelected ? 1.5 : 0.5,
                      ),
                    ),
                    child: Text(
                      lang['name']!,
                      style: TextStyle(
                        color: isSelected
                            ? AviraTheme.brandPrimary
                            : Colors.white70,
                        fontWeight: isSelected
                            ? FontWeight.w700
                            : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}

/// AVIRA – Disease Candidate Card Widget
library;

import 'package:flutter/material.dart';
import '../models/analysis_result.dart';
import '../utils/theme.dart';

class DiseaseCard extends StatefulWidget {
  final DiseaseCandidate disease;
  final int rank;

  const DiseaseCard({
    super.key,
    required this.disease,
    this.rank = 0,
  });

  @override
  State<DiseaseCard> createState() => _DiseaseCardState();
}

class _DiseaseCardState extends State<DiseaseCard>
    with SingleTickerProviderStateMixin {
  bool _expanded = false;
  late AnimationController _barCtrl;
  late Animation<double> _barAnim;

  Color get _color {
    final p = widget.disease.probability;
    if (p >= 0.60) return AviraTheme.brandDanger;
    if (p >= 0.35) return AviraTheme.brandWarning;
    return AviraTheme.brandPrimary;
  }

  @override
  void initState() {
    super.initState();
    _barCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _barAnim = Tween<double>(begin: 0, end: widget.disease.probability)
        .animate(CurvedAnimation(parent: _barCtrl, curve: Curves.easeOut));
    Future.delayed(Duration(milliseconds: widget.rank * 100), () {
      if (mounted) _barCtrl.forward();
    });
  }

  @override
  void dispose() {
    _barCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.disease;
    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(
          color: AviraTheme.bgMedium.withOpacity(0.55),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _color.withOpacity(0.25)),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    // Rank badge
                    Container(
                      width: 24, height: 24,
                      decoration: BoxDecoration(
                        color: _color.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Center(
                        child: Text('${widget.rank}',
                          style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.w800)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(d.disease,
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                    ),
                    // Probability
                    Text('${(d.probability * 100).toInt()}%',
                      style: TextStyle(
                        color: _color, fontWeight: FontWeight.w900,
                        fontSize: 18, fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(_expanded ? Icons.expand_less : Icons.expand_more,
                      color: AviraTheme.textMuted, size: 18),
                  ]),
                  const SizedBox(height: 10),

                  // Animated progress bar
                  AnimatedBuilder(
                    animation: _barAnim,
                    builder: (_, __) => ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: _barAnim.value,
                        backgroundColor: Colors.white.withOpacity(0.07),
                        valueColor: AlwaysStoppedAnimation<Color>(_color),
                        minHeight: 7,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Badges row
                  Wrap(spacing: 6, runSpacing: 4, children: [
                    _chip(d.confidence, AviraTheme.brandInfo),
                    _chip(d.urgency, _color),
                    if (d.vetRequired) _chip('🏥 VET REQUIRED', AviraTheme.brandDanger),
                    if (d.vetRequired == false && d.urgency == 'LOW')
                      _chip('Monitor', AviraTheme.brandSuccess),
                  ]),
                ],
              ),
            ),

            // Expanded evidence
            if (_expanded) ...[
              Divider(height: 1, color: Colors.white.withOpacity(0.06)),
              Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (d.matchedEvidence.isNotEmpty) ...[
                      const Text('Matched Evidence',
                        style: TextStyle(color: AviraTheme.textMuted, fontSize: 10,
                          fontWeight: FontWeight.w700, letterSpacing: 1)),
                      const SizedBox(height: 5),
                      ...d.matchedEvidence.take(4).map((e) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(children: [
                          const Text('✓ ',
                            style: TextStyle(color: AviraTheme.brandSuccess, fontSize: 12)),
                          Expanded(child: Text(e,
                            style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 12))),
                        ]),
                      )),
                    ],
                    if (d.missingEvidence.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      const Text('Not Confirmed',
                        style: TextStyle(color: AviraTheme.textMuted, fontSize: 10,
                          fontWeight: FontWeight.w700, letterSpacing: 1)),
                      const SizedBox(height: 5),
                      ...d.missingEvidence.take(3).map((e) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(children: [
                          const Text('○ ',
                            style: TextStyle(color: AviraTheme.textMuted, fontSize: 12)),
                          Expanded(child: Text(e,
                            style: const TextStyle(color: AviraTheme.textMuted, fontSize: 12))),
                        ]),
                      )),
                    ],
                    if (d.recommendations.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      const Text('Recommendations',
                        style: TextStyle(color: AviraTheme.textMuted, fontSize: 10,
                          fontWeight: FontWeight.w700, letterSpacing: 1)),
                      const SizedBox(height: 5),
                      ...d.recommendations.take(3).map((r) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Text('→ ',
                            style: TextStyle(color: AviraTheme.brandPrimary, fontSize: 12)),
                          Expanded(child: Text(r,
                            style: const TextStyle(color: AviraTheme.textSecondary, fontSize: 12))),
                        ]),
                      )),
                    ],
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(label,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }
}

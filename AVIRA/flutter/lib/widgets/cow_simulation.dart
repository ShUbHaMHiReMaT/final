/// AVIRA Digital Cow Simulation Widget
/// Renders an animated, CustomPainter-based side-view cow silhouette
/// with affected-region highlighting and disease pulse animation.
/// PRANIVA – Advanced Veterinary Intelligence Research & Analytics
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';

// ── Disease → body region mapping ────────────────────────────────────────────

/// Canonical body regions on the cow silhouette.
enum CowRegion {
  head,
  chest,
  abdomen,
  udder,
  legs,
  skin,
  heart,
}

extension CowRegionLabel on CowRegion {
  String get label {
    switch (this) {
      case CowRegion.head:
        return 'Head / Mouth';
      case CowRegion.chest:
        return 'Chest / Lungs';
      case CowRegion.abdomen:
        return 'Abdomen / Rumen';
      case CowRegion.udder:
        return 'Udder';
      case CowRegion.legs:
        return 'Legs / Hooves';
      case CowRegion.skin:
        return 'Skin (Whole Body)';
      case CowRegion.heart:
        return 'Heart Region';
    }
  }
}

/// Maps disease names (lowercase, partial match supported) to affected body region.
const Map<String, CowRegion> _diseaseRegionMap = {
  'fmd': CowRegion.head,
  'foot and mouth': CowRegion.head,
  'lsd': CowRegion.skin,
  'lumpy skin': CowRegion.skin,
  'theileriosis': CowRegion.heart,
  'pneumonia': CowRegion.chest,
  'babesiosis': CowRegion.heart,
  'bloat': CowRegion.abdomen,
  "johne's disease": CowRegion.abdomen,
  'johnes': CowRegion.abdomen,
  'worm infestation': CowRegion.abdomen,
  'worm': CowRegion.abdomen,
  'mastitis': CowRegion.udder,
  'tick fever': CowRegion.legs,
  'heat stress': CowRegion.skin,
};

/// Returns the body region most associated with [diseaseName].
CowRegion _regionForDisease(String diseaseName) {
  final lower = diseaseName.toLowerCase();
  for (final entry in _diseaseRegionMap.entries) {
    if (lower.contains(entry.key)) return entry.value;
  }
  return CowRegion.abdomen; // fallback
}

// ── Alert colour helpers ──────────────────────────────────────────────────────

Color _alertColour(String alertLevel) {
  switch (alertLevel.toUpperCase()) {
    case 'CRITICAL':
      return const Color(0xFFFF4757);
    case 'HIGH':
      return const Color(0xFFFF922B);
    case 'MODERATE':
      return const Color(0xFFFFD93D);
    default:
      return const Color(0xFF2ECC71);
  }
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  CowSimulationWidget                                                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝

/// Animated digital cow body diagram.
///
/// Shows a side-view silhouette with highlighted affected regions and
/// pulse animation based on the AI analysis result.
class CowSimulationWidget extends StatefulWidget {
  /// Full analysis result map from AppState (may be null before first analysis).
  final Map<String, dynamic>? analysisResult;

  /// Current alert level: 'NORMAL', 'MODERATE', 'HIGH', or 'CRITICAL'.
  final String alertLevel;

  /// Display name of the cow / animal ID.
  final String animalId;

  /// Breed label for the overlay.
  final String breed;

  const CowSimulationWidget({
    super.key,
    this.analysisResult,
    this.alertLevel = 'NORMAL',
    this.animalId = 'COW_001',
    this.breed = 'HF Cross',
  });

  @override
  State<CowSimulationWidget> createState() => _CowSimulationWidgetState();
}

class _CowSimulationWidgetState extends State<CowSimulationWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();

    _pulseAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  /// Extracts the top disease name from the analysis result map.
  String get _topDisease {
    final result = widget.analysisResult;
    if (result == null) return '';
    final topDiseases = result['top_diseases'] as List?;
    if (topDiseases == null || topDiseases.isEmpty) return '';
    final first = topDiseases.first;
    if (first is Map) return first['disease']?.toString() ?? '';
    return '';
  }

  CowRegion get _affectedRegion => _regionForDisease(_topDisease);

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulseAnimation,
      builder: (context, _) {
        return ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: CustomPaint(
            painter: CowBodyPainter(
              alertLevel: widget.alertLevel,
              topDisease: _topDisease,
              affectedRegion: _affectedRegion,
              pulseValue: _pulseAnimation.value,
              animalId: widget.animalId,
              breed: widget.breed,
            ),
            child: const SizedBox.expand(),
          ),
        );
      },
    );
  }
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  CowBodyPainter                                                          ║
// ╚══════════════════════════════════════════════════════════════════════════╝

/// Custom painter that draws the full cow silhouette with anatomical regions.
class CowBodyPainter extends CustomPainter {
  final String alertLevel;
  final String topDisease;
  final CowRegion affectedRegion;
  final double pulseValue; // 0.0 → 1.0, drives all animations
  final String animalId;
  final String breed;

  CowBodyPainter({
    required this.alertLevel,
    required this.topDisease,
    required this.affectedRegion,
    required this.pulseValue,
    required this.animalId,
    required this.breed,
  });

  // Palette
  static const _bodyFill = Color(0xFF1E3A5F);
  static const _bodyOutline = Color(0xFF2D5A8E);
  static const _skinHighlight = Color(0xFF3A6FA0);
  static const _bgStart = Color(0xFF0D1B2A);
  static const _bgEnd = Color(0xFF162236);
  static const _white = Colors.white;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // ── Background ────────────────────────────────────────────────────────
    _drawBackground(canvas, size);

    // ── Compute cow layout anchors (relative to canvas size) ─────────────
    // Body ellipse
    final bodyRect = Rect.fromLTWH(w * 0.22, h * 0.28, w * 0.56, h * 0.42);
    // Head circle
    final headCenter = Offset(w * 0.82, h * 0.30);
    const headRadius = 0.12; // fraction of w
    // Neck
    final neckRect = Rect.fromLTWH(w * 0.74, h * 0.26, w * 0.10, h * 0.22);
    // Legs
    final legW = w * 0.055;
    final legH = h * 0.30;
    final legTop = h * 0.64;
    final legPositions = [
      Offset(w * 0.28, legTop), // front-left
      Offset(w * 0.37, legTop), // front-right
      Offset(w * 0.58, legTop), // rear-left
      Offset(w * 0.67, legTop), // rear-right
    ];
    // Udder
    final udderRect = Rect.fromLTWH(w * 0.43, h * 0.65, w * 0.16, h * 0.13);
    // Tail
    final tailStart = Offset(w * 0.22, h * 0.40);
    final tailEnd = Offset(w * 0.08, h * 0.60);
    final tailControl = Offset(w * 0.10, h * 0.35);

    // ── Determine glow colour for affected region ─────────────────────────
    final glowColor = _alertColour(alertLevel);
    final bool hasAlert = alertLevel != 'NORMAL';

    // ── Draw parts in painter's-algorithm order ───────────────────────────

    // Tail
    _drawTail(canvas, tailStart, tailControl, tailEnd, w);

    // Legs (behind body)
    for (final pos in legPositions) {
      final isAffected = hasAlert && affectedRegion == CowRegion.legs;
      _drawLeg(canvas, pos, legW, legH, isAffected ? glowColor : null, w);
    }

    // Body with optional highlight overlays for skin/abdomen/chest/heart
    _drawBody(canvas, bodyRect, hasAlert, glowColor, w, h);

    // Udder
    _drawUdder(canvas, udderRect, hasAlert && affectedRegion == CowRegion.udder, glowColor);

    // Neck
    _drawNeck(canvas, neckRect);

    // Head (with mouth for FMD)
    _drawHead(canvas, headCenter, headRadius * w, hasAlert && affectedRegion == CowRegion.head, glowColor, w, h);

    // Horns
    _drawHorns(canvas, headCenter, headRadius * w, w);

    // Ear
    _drawEar(canvas, headCenter, headRadius * w, w);

    // Eye
    _drawEye(canvas, headCenter, headRadius * w);

    // Affected region pulse ring
    if (hasAlert && topDisease.isNotEmpty) {
      _drawPulseRing(canvas, size, glowColor, w, h);
    }

    // Disease label
    if (hasAlert && topDisease.isNotEmpty) {
      _drawDiseaseLabel(canvas, size, glowColor, w, h);
    }

    // Animal ID / breed overlay at top
    _drawTopOverlay(canvas, size, w);
  }

  // ── Background ────────────────────────────────────────────────────────────
  void _drawBackground(Canvas canvas, Size size) {
    final paint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [_bgStart, _bgEnd],
      ).createShader(Offset.zero & size);

    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(16)),
      paint,
    );

    // subtle grid dots
    final dotPaint = Paint()
      ..color = const Color(0xFF1A2F45)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.fill;
    const step = 20.0;
    for (double x = step; x < size.width; x += step) {
      for (double y = step; y < size.height; y += step) {
        canvas.drawCircle(Offset(x, y), 1, dotPaint);
      }
    }
  }

  // ── Body ──────────────────────────────────────────────────────────────────
  void _drawBody(Canvas canvas, Rect rect, bool hasAlert, Color glowColor, double w, double h) {
    // Base shadow
    final shadowPaint = Paint()
      ..color = Colors.black26
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10);
    canvas.drawOval(rect.inflate(6), shadowPaint);

    // Body fill – gradient
    final bodyPaint = Paint()
      ..shader = RadialGradient(
        center: Alignment.center,
        radius: 0.8,
        colors: [_skinHighlight, _bodyFill],
      ).createShader(rect);
    canvas.drawOval(rect, bodyPaint);

    // Body outline
    final outlinePaint = Paint()
      ..color = _bodyOutline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawOval(rect, outlinePaint);

    // Chest / lung overlay
    if (hasAlert && affectedRegion == CowRegion.chest) {
      final chestRect = Rect.fromLTWH(rect.left + rect.width * 0.50, rect.top + rect.height * 0.10,
          rect.width * 0.30, rect.height * 0.55);
      _drawRegionGlow(canvas, chestRect, glowColor, oval: true);
    }

    // Abdomen / rumen overlay
    if (hasAlert && affectedRegion == CowRegion.abdomen) {
      final abdRect = Rect.fromLTWH(rect.left + rect.width * 0.20, rect.top + rect.height * 0.25,
          rect.width * 0.40, rect.height * 0.60);
      _drawRegionGlow(canvas, abdRect, glowColor, oval: true);
    }

    // Heart region overlay (slightly left-chest)
    if (hasAlert && affectedRegion == CowRegion.heart) {
      final heartRect = Rect.fromLTWH(rect.left + rect.width * 0.52, rect.top + rect.height * 0.05,
          rect.width * 0.22, rect.height * 0.40);
      _drawRegionGlow(canvas, heartRect, glowColor, oval: true);
    }

    // Skin (whole body)
    if (hasAlert && affectedRegion == CowRegion.skin) {
      final skinPaint = Paint()
        ..color = glowColor.withOpacity(0.20 + 0.10 * math.sin(pulseValue * math.pi * 2))
        ..style = PaintingStyle.fill;
      canvas.drawOval(rect.inflate(3), skinPaint);

      final skinBorderPaint = Paint()
        ..color = glowColor.withOpacity(0.60)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.0;
      canvas.drawOval(rect.inflate(3), skinBorderPaint);
    }
  }

  // ── Neck ──────────────────────────────────────────────────────────────────
  void _drawNeck(Canvas canvas, Rect rect) {
    final paint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [_bodyFill, _skinHighlight],
      ).createShader(rect);
    canvas.drawOval(rect, paint);

    final outline = Paint()
      ..color = _bodyOutline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawOval(rect, outline);
  }

  // ── Head ──────────────────────────────────────────────────────────────────
  void _drawHead(Canvas canvas, Offset center, double radius, bool affected, Color glowColor,
      double w, double h) {
    if (affected) {
      // Glow ring
      final glowPaint = Paint()
        ..color = glowColor.withOpacity(0.35 + 0.25 * math.sin(pulseValue * math.pi * 2))
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12);
      canvas.drawCircle(center, radius * 1.35, glowPaint);
    }

    // Head fill
    final fillPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.3, -0.3),
        radius: 0.9,
        colors: [_skinHighlight, _bodyFill],
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawCircle(center, radius, fillPaint);

    if (affected) {
      final overlayPaint = Paint()
        ..color = glowColor.withOpacity(0.30)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(center, radius, overlayPaint);
    }

    // Head outline
    final outlinePaint = Paint()
      ..color = affected ? glowColor : _bodyOutline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawCircle(center, radius, outlinePaint);

    // Muzzle / snout ellipse
    final muzzleRect = Rect.fromCenter(
      center: Offset(center.dx + radius * 0.60, center.dy + radius * 0.15),
      width: radius * 0.70,
      height: radius * 0.45,
    );
    final muzzlePaint = Paint()..color = const Color(0xFF254A6A);
    canvas.drawOval(muzzleRect, muzzlePaint);

    // Nostril dots
    final nostrilPaint = Paint()..color = const Color(0xFF1A3550);
    canvas.drawCircle(Offset(center.dx + radius * 0.50, center.dy + radius * 0.18), radius * 0.07,
        nostrilPaint);
    canvas.drawCircle(Offset(center.dx + radius * 0.65, center.dy + radius * 0.18), radius * 0.07,
        nostrilPaint);
  }

  // ── Horns ─────────────────────────────────────────────────────────────────
  void _drawHorns(Canvas canvas, Offset headCenter, double radius, double w) {
    final hornPaint = Paint()
      ..color = const Color(0xFFE8D5A3)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 4.0;

    // Left horn
    final hornPath1 = Path()
      ..moveTo(headCenter.dx - radius * 0.30, headCenter.dy - radius * 0.75)
      ..quadraticBezierTo(headCenter.dx - radius * 0.70, headCenter.dy - radius * 1.4,
          headCenter.dx - radius * 0.20, headCenter.dy - radius * 1.45);
    canvas.drawPath(hornPath1, hornPaint);

    // Right horn (angled differently)
    final hornPath2 = Path()
      ..moveTo(headCenter.dx + radius * 0.05, headCenter.dy - radius * 0.75)
      ..quadraticBezierTo(headCenter.dx + radius * 0.45, headCenter.dy - radius * 1.4,
          headCenter.dx + radius * 0.15, headCenter.dy - radius * 1.45);
    canvas.drawPath(hornPath2, hornPaint);
  }

  // ── Ear ───────────────────────────────────────────────────────────────────
  void _drawEar(Canvas canvas, Offset headCenter, double radius, double w) {
    final earPath = Path()
      ..moveTo(headCenter.dx - radius * 0.30, headCenter.dy - radius * 0.50)
      ..lineTo(headCenter.dx - radius * 0.70, headCenter.dy - radius * 0.80)
      ..lineTo(headCenter.dx - radius * 0.10, headCenter.dy - radius * 0.60)
      ..close();

    canvas.drawPath(earPath, Paint()..color = _skinHighlight);
    canvas.drawPath(
        earPath,
        Paint()
          ..color = _bodyOutline
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);

    // Inner ear
    final innerEarPath = Path()
      ..moveTo(headCenter.dx - radius * 0.30, headCenter.dy - radius * 0.53)
      ..lineTo(headCenter.dx - radius * 0.58, headCenter.dy - radius * 0.74)
      ..lineTo(headCenter.dx - radius * 0.18, headCenter.dy - radius * 0.60)
      ..close();
    canvas.drawPath(innerEarPath, Paint()..color = const Color(0xFF3A6FA0).withOpacity(0.6));
  }

  // ── Eye ───────────────────────────────────────────────────────────────────
  void _drawEye(Canvas canvas, Offset headCenter, double radius) {
    final eyeCenter = Offset(headCenter.dx + radius * 0.15, headCenter.dy - radius * 0.20);

    // White sclera
    canvas.drawCircle(eyeCenter, radius * 0.16, Paint()..color = _white);
    // Pupil
    canvas.drawCircle(eyeCenter, radius * 0.09, Paint()..color = Colors.black87);
    // Catchlight
    canvas.drawCircle(
        Offset(eyeCenter.dx + radius * 0.04, eyeCenter.dy - radius * 0.04),
        radius * 0.04,
        Paint()..color = _white);
  }

  // ── Legs ──────────────────────────────────────────────────────────────────
  void _drawLeg(Canvas canvas, Offset topLeft, double legW, double legH, Color? highlight,
      double w) {
    final rect = Rect.fromLTWH(topLeft.dx - legW / 2, topLeft.dy, legW, legH);

    // Shadow
    final shadowPaint = Paint()
      ..color = Colors.black26
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
    canvas.drawRRect(RRect.fromRectAndRadius(rect.inflate(2), const Radius.circular(6)),
        shadowPaint);

    // Leg body
    final legPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [_skinHighlight, _bodyFill],
      ).createShader(rect);
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)), legPaint);

    if (highlight != null) {
      final glowPaint = Paint()
        ..color = highlight.withOpacity(0.45 + 0.20 * math.sin(pulseValue * math.pi * 2))
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
      canvas.drawRRect(RRect.fromRectAndRadius(rect.inflate(2), const Radius.circular(6)),
          glowPaint);
    }

    // Hoof (darker bottom)
    final hoofRect = Rect.fromLTWH(rect.left, rect.bottom - legH * 0.15, legW, legH * 0.15);
    canvas.drawRRect(
        RRect.fromRectAndRadius(hoofRect, const Radius.circular(4)),
        Paint()..color = const Color(0xFF0D1F33));

    // Outline
    canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(6)),
        Paint()
          ..color = _bodyOutline
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
  }

  // ── Udder ─────────────────────────────────────────────────────────────────
  void _drawUdder(Canvas canvas, Rect rect, bool affected, Color glowColor) {
    if (affected) {
      final glowPaint = Paint()
        ..color = glowColor.withOpacity(0.40 + 0.20 * math.sin(pulseValue * math.pi * 2))
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10);
      canvas.drawOval(rect.inflate(5), glowPaint);
    }

    final udderPaint = Paint()
      ..color = affected
          ? Color.lerp(const Color(0xFFF4A0A0), glowColor, 0.50)!
          : const Color(0xFFF4C0C0);
    canvas.drawOval(rect, udderPaint);

    // Teats
    final teatPaint = Paint()..color = const Color(0xFFD88080);
    final teatW = rect.width * 0.11;
    final teatH = rect.height * 0.45;
    for (int i = 0; i < 4; i++) {
      final tx = rect.left + rect.width * (0.12 + i * 0.25);
      canvas.drawRRect(
          RRect.fromRectAndRadius(
              Rect.fromLTWH(tx, rect.bottom - 2, teatW, teatH), const Radius.circular(3)),
          teatPaint);
    }

    canvas.drawOval(
        rect,
        Paint()
          ..color = affected ? glowColor.withOpacity(0.50) : Colors.transparent
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.0);
  }

  // ── Tail ──────────────────────────────────────────────────────────────────
  void _drawTail(Canvas canvas, Offset start, Offset control, Offset end, double w) {
    final tailPath = Path()
      ..moveTo(start.dx, start.dy)
      ..quadraticBezierTo(control.dx, control.dy, end.dx, end.dy);

    canvas.drawPath(
        tailPath,
        Paint()
          ..color = _bodyOutline
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeWidth = 5.0);

    // Tail tuft (small oval at end)
    final tuftPaint = Paint()..color = const Color(0xFF2D5A8E);
    canvas.drawOval(Rect.fromCenter(center: end, width: w * 0.04, height: w * 0.06), tuftPaint);
  }

  // ── Region glow helper ────────────────────────────────────────────────────
  void _drawRegionGlow(Canvas canvas, Rect rect, Color color, {bool oval = false}) {
    final glowPaint = Paint()
      ..color = color.withOpacity(0.35 + 0.20 * math.sin(pulseValue * math.pi * 2))
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14);

    final borderPaint = Paint()
      ..color = color.withOpacity(0.75)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;

    if (oval) {
      canvas.drawOval(rect, glowPaint);
      canvas.drawOval(rect, borderPaint);
    } else {
      final rRect = RRect.fromRectAndRadius(rect, const Radius.circular(8));
      canvas.drawRRect(rRect, glowPaint);
      canvas.drawRRect(rRect, borderPaint);
    }
  }

  // ── Pulse ring ────────────────────────────────────────────────────────────
  void _drawPulseRing(Canvas canvas, Size size, Color color, double w, double h) {
    final Offset center = _affectedRegionCenter(w, h);
    final double maxRadius = w * 0.14;
    final double radius = maxRadius * pulseValue;
    final double opacity = (1.0 - pulseValue).clamp(0.0, 1.0);

    final paint = Paint()
      ..color = color.withOpacity(opacity * 0.85)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0;

    canvas.drawCircle(center, radius, paint);

    // Secondary inner pulse ring (offset phase)
    final innerPhase = (pulseValue + 0.4) % 1.0;
    final innerRadius = maxRadius * innerPhase;
    final innerOpacity = (1.0 - innerPhase).clamp(0.0, 1.0);
    final innerPaint = Paint()
      ..color = color.withOpacity(innerOpacity * 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawCircle(center, innerRadius, innerPaint);
  }

  /// Returns the canvas centre point for the affected region.
  Offset _affectedRegionCenter(double w, double h) {
    switch (affectedRegion) {
      case CowRegion.head:
        return Offset(w * 0.82, h * 0.30);
      case CowRegion.chest:
        return Offset(w * 0.68, h * 0.44);
      case CowRegion.abdomen:
        return Offset(w * 0.46, h * 0.50);
      case CowRegion.udder:
        return Offset(w * 0.51, h * 0.70);
      case CowRegion.legs:
        return Offset(w * 0.48, h * 0.80);
      case CowRegion.skin:
        return Offset(w * 0.50, h * 0.50);
      case CowRegion.heart:
        return Offset(w * 0.64, h * 0.38);
    }
  }

  // ── Disease label ─────────────────────────────────────────────────────────
  void _drawDiseaseLabel(Canvas canvas, Size size, Color color, double w, double h) {
    final Offset regionCenter = _affectedRegionCenter(w, h);
    final labelText = topDisease.isNotEmpty ? topDisease : '';
    if (labelText.isEmpty) return;

    final textStyle = TextStyle(
      color: color,
      fontSize: w * 0.030,
      fontWeight: FontWeight.bold,
      shadows: const [Shadow(color: Colors.black, blurRadius: 4)],
    );
    final textPainter = TextPainter(
      text: TextSpan(text: '▶ $labelText', style: textStyle),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout(maxWidth: w * 0.45);

    // Position label to the left of the region if near right edge
    double labelX = regionCenter.dx + w * 0.05;
    if (labelX + textPainter.width > w * 0.95) {
      labelX = regionCenter.dx - textPainter.width - w * 0.05;
    }
    final labelY = (regionCenter.dy - textPainter.height / 2).clamp(h * 0.05, h * 0.88);

    // Background pill
    final bgRect = Rect.fromLTWH(
        labelX - 6, labelY - 4, textPainter.width + 12, textPainter.height + 8);
    canvas.drawRRect(
        RRect.fromRectAndRadius(bgRect, const Radius.circular(6)),
        Paint()..color = Colors.black.withOpacity(0.60));

    textPainter.paint(canvas, Offset(labelX, labelY));
  }

  // ── Animal ID top overlay ─────────────────────────────────────────────────
  void _drawTopOverlay(Canvas canvas, Size size, double w) {
    const fontSize = 11.0;
    final idStyle = const TextStyle(
      color: Color(0xFF7DB5E0),
      fontSize: fontSize,
      fontWeight: FontWeight.w600,
      letterSpacing: 0.5,
    );
    final breedStyle = const TextStyle(
      color: Color(0xFF4A7FA0),
      fontSize: fontSize - 1,
    );

    final idPainter = TextPainter(
      text: TextSpan(text: '🐄  $animalId', style: idStyle),
      textDirection: TextDirection.ltr,
    );
    idPainter.layout();

    final breedPainter = TextPainter(
      text: TextSpan(text: breed, style: breedStyle),
      textDirection: TextDirection.ltr,
    );
    breedPainter.layout();

    // Background pill
    final bgW = idPainter.width + breedPainter.width + 24;
    canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(w * 0.03, size.height * 0.04, bgW, 24), const Radius.circular(12)),
        Paint()..color = Colors.black.withOpacity(0.50));

    idPainter.paint(canvas, Offset(w * 0.05, size.height * 0.052));
    breedPainter.paint(
        canvas, Offset(w * 0.05 + idPainter.width + 8, size.height * 0.052 + 1));
  }

  @override
  bool shouldRepaint(CowBodyPainter oldDelegate) =>
      oldDelegate.pulseValue != pulseValue ||
      oldDelegate.alertLevel != alertLevel ||
      oldDelegate.topDisease != topDisease ||
      oldDelegate.affectedRegion != affectedRegion;
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  HealthStatusOverlay                                                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝

/// Overlay widget displayed over / below the cow simulation showing
/// alert badge, health score bar, and top disease name.
class HealthStatusOverlay extends StatelessWidget {
  final String alertLevel;
  final double healthScore; // 0.0 – 1.0
  final String topDiseaseName;
  final bool vetRequired;

  const HealthStatusOverlay({
    super.key,
    required this.alertLevel,
    required this.healthScore,
    required this.topDiseaseName,
    required this.vetRequired,
  });

  Color get _levelColor => _alertColour(alertLevel);

  String get _levelLabel {
    switch (alertLevel.toUpperCase()) {
      case 'CRITICAL':
        return '🔴  CRITICAL';
      case 'HIGH':
        return '🟠  HIGH ALERT';
      case 'MODERATE':
        return '🟡  MODERATE';
      default:
        return '🟢  NORMAL';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1B2A).withOpacity(0.92),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _levelColor.withOpacity(0.50), width: 1.2),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Alert badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: _levelColor.withOpacity(0.18),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _levelColor, width: 1.0),
            ),
            child: Text(
              _levelLabel,
              style: TextStyle(
                color: _levelColor,
                fontWeight: FontWeight.bold,
                fontSize: 13,
                letterSpacing: 0.5,
              ),
            ),
          ),
          const SizedBox(height: 8),

          // Health score bar
          Row(
            children: [
              const Text(
                'Health',
                style: TextStyle(color: Color(0xFF7DB5E0), fontSize: 12),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: healthScore.clamp(0.0, 1.0),
                    backgroundColor: const Color(0xFF1E3A5F),
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Color.lerp(Colors.red, Colors.green, healthScore) ??
                          Colors.green,
                    ),
                    minHeight: 8,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${(healthScore * 100).toInt()}%',
                style: TextStyle(
                  color: Color.lerp(Colors.red, Colors.green, healthScore) ??
                      Colors.green,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),

          // Top disease
          if (topDiseaseName.isNotEmpty)
            Row(
              children: [
                const Icon(Icons.biotech, color: Color(0xFF7DB5E0), size: 14),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    topDiseaseName,
                    style: const TextStyle(
                      color: Color(0xFFCCE4FF),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),

          // Vet required badge
          if (vetRequired) ...[
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.red.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.red.shade400, width: 0.8),
              ),
              child: const Text(
                '🩺  Veterinarian Required',
                style: TextStyle(color: Colors.redAccent, fontSize: 11),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  Body region legend                                                      ║
// ╚══════════════════════════════════════════════════════════════════════════╝

/// Static map of body region → list of associated diseases (for legend display).
const Map<CowRegion, List<String>> cowRegionDiseaseIndex = {
  CowRegion.head: ['FMD', 'LSD', 'Theileriosis'],
  CowRegion.chest: ['Pneumonia', 'Babesiosis'],
  CowRegion.abdomen: ["Bloat", "Johne's Disease", 'Worm Infestation'],
  CowRegion.udder: ['Mastitis'],
  CowRegion.legs: ['FMD', 'Tick Fever', 'Worm Infestation'],
  CowRegion.skin: ['LSD', 'Heat Stress', 'Theileriosis'],
  CowRegion.heart: ['Theileriosis', 'Babesiosis'],
};

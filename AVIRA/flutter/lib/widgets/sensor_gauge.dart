/// AVIRA – Sensor Gauge Widget
/// Circular arc gauge for displaying a single sensor value.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../utils/theme.dart';

class SensorGauge extends StatefulWidget {
  final double? value;
  final String label;
  final String unit;
  final double minVal;
  final double maxVal;
  final Color color;
  final double size;
  final bool isValid;

  const SensorGauge({
    super.key,
    required this.value,
    required this.label,
    required this.unit,
    required this.minVal,
    required this.maxVal,
    required this.color,
    this.size = 110,
    this.isValid = true,
  });

  @override
  State<SensorGauge> createState() => _SensorGaugeState();
}

class _SensorGaugeState extends State<SensorGauge>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _animation;
  double _prevValue = 0;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _animation = Tween<double>(begin: 0, end: _normalised).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeOut),
    );
    _ctrl.forward();
  }

  @override
  void didUpdateWidget(SensorGauge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value) {
      _animation = Tween<double>(
        begin: _prevValue,
        end: _normalised,
      ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
      _ctrl.forward(from: 0);
      _prevValue = _normalised;
    }
  }

  double get _normalised {
    if (widget.value == null || !widget.isValid) return 0;
    return ((widget.value! - widget.minVal) / (widget.maxVal - widget.minVal))
        .clamp(0.0, 1.0);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _animation,
            builder: (_, __) => SizedBox(
              width: widget.size,
              height: widget.size,
              child: CustomPaint(
                painter: _GaugePainter(
                  progress: _animation.value,
                  color: widget.color,
                  isValid: widget.isValid,
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        widget.value != null && widget.isValid
                            ? _formatValue(widget.value!)
                            : '--',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: widget.size * 0.20,
                          fontWeight: FontWeight.w800,
                          color: widget.isValid ? widget.color : AviraTheme.textMuted,
                        ),
                      ),
                      Text(
                        widget.unit,
                        style: TextStyle(
                          fontSize: widget.size * 0.085,
                          color: AviraTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            widget.label,
            style: const TextStyle(
              fontSize: 11,
              color: AviraTheme.textSecondary,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  String _formatValue(double v) {
    if (v >= 100) return v.toStringAsFixed(0);
    if (v >= 10)  return v.toStringAsFixed(1);
    return v.toStringAsFixed(2);
  }
}

class _GaugePainter extends CustomPainter {
  final double progress;
  final Color color;
  final bool isValid;
  static const double _startAngle = math.pi * 0.75;
  static const double _sweepAngle = math.pi * 1.5;

  const _GaugePainter({
    required this.progress,
    required this.color,
    required this.isValid,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width  / 2;
    final cy = size.height / 2;
    final radius = (size.shortestSide / 2) - 8;
    final strokeW = 7.0;
    final rect = Rect.fromCircle(center: Offset(cx, cy), radius: radius);

    // Background arc
    final bgPaint = Paint()
      ..color = Colors.white.withOpacity(0.06)
      ..strokeWidth = strokeW
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, _startAngle, _sweepAngle, false, bgPaint);

    // Progress arc
    if (progress > 0 && isValid) {
      final fgPaint = Paint()
        ..color = color
        ..strokeWidth = strokeW
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round;

      // Glow
      final glowPaint = Paint()
        ..color = color.withOpacity(0.25)
        ..strokeWidth = strokeW + 6
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
      canvas.drawArc(rect, _startAngle, _sweepAngle * progress, false, glowPaint);
      canvas.drawArc(rect, _startAngle, _sweepAngle * progress, false, fgPaint);
    }
  }

  @override
  bool shouldRepaint(_GaugePainter old) =>
      old.progress != progress || old.color != color;
}

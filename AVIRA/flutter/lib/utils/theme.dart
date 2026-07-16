/// AVIRA App Theme
/// Dark premium theme matching the web dashboard aesthetic.
library;

import 'package:flutter/material.dart';

abstract final class AviraTheme {
  // ── Brand Colours ────────────────────────────────────────────────────
  static const Color brandPrimary   = Color(0xFF00D4AA);
  static const Color brandSecondary = Color(0xFF0891B2);
  static const Color brandAccent    = Color(0xFF7C3AED);
  static const Color brandDanger    = Color(0xFFEF4444);
  static const Color brandWarning   = Color(0xFFF59E0B);
  static const Color brandSuccess   = Color(0xFF10B981);
  static const Color brandInfo      = Color(0xFF3B82F6);

  // ── Card / Border shorthands ─────────────────────────────────────────
  static const Color cardBg       = Color(0xFF1E293B);   // bgMedium alias
  static const Color borderGlass  = Color(0x14FFFFFF);   // white @ 8% opacity

  // ── Alert shorthands (for widgets) ──────────────────────────────────
  static const Color alertCritical = Color(0xFFEF4444);  // same as brandDanger
  static const Color alertHigh     = Color(0xFFF59E0B);  // same as brandWarning
  static const Color alertModerate = Color(0xFF3B82F6);  // same as brandInfo
  static const Color alertLow      = Color(0xFF10B981);  // same as brandSuccess

  // ── Background ───────────────────────────────────────────────────────
  static const Color bgVoid   = Color(0xFF030712);
  static const Color bgDeep   = Color(0xFF0A0F1E);
  static const Color bgDark   = Color(0xFF0F172A);
  static const Color bgMedium = Color(0xFF1E293B);
  static const Color bgLight  = Color(0xFF334155);

  // ── Text ─────────────────────────────────────────────────────────────
  static const Color textPrimary   = Color(0xFFF1F5F9);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted     = Color(0xFF475569);

  // ── Alert Level Colours ──────────────────────────────────────────────
  static Color alertColor(String level) {
    switch (level.toUpperCase()) {
      case 'CRITICAL': return brandDanger;
      case 'HIGH':     return brandWarning;
      case 'MODERATE': return brandInfo;
      case 'LOW':      return brandSuccess;
      default:         return textSecondary;
    }
  }

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary:    brandPrimary,
        secondary:  brandSecondary,
        tertiary:   brandAccent,
        error:      brandDanger,
        surface:    bgDark,
        onPrimary:  bgDark,
        onSurface:  textPrimary,
      ),
      scaffoldBackgroundColor: bgVoid,
      cardTheme: CardThemeData(
        color: bgMedium.withOpacity(0.6),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.white.withOpacity(0.08)),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: bgDeep,
        foregroundColor: textPrimary,
        elevation: 0,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: brandPrimary,
          foregroundColor: bgDark,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: brandPrimary,
          side: const BorderSide(color: brandPrimary),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: bgMedium.withOpacity(0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: brandPrimary, width: 1.5),
        ),
        labelStyle: const TextStyle(color: textSecondary),
        hintStyle: const TextStyle(color: textMuted),
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(color: textPrimary, fontWeight: FontWeight.w800),
        headlineMedium: TextStyle(color: textPrimary, fontWeight: FontWeight.w700),
        titleLarge: TextStyle(color: textPrimary, fontWeight: FontWeight.w700),
        titleMedium: TextStyle(color: textPrimary, fontWeight: FontWeight.w600),
        bodyLarge: TextStyle(color: textSecondary, height: 1.6),
        bodyMedium: TextStyle(color: textSecondary, height: 1.6),
        bodySmall: TextStyle(color: textMuted),
        labelLarge: TextStyle(color: textPrimary, fontWeight: FontWeight.w600),
      ),
      dividerTheme: DividerThemeData(
        color: Colors.white.withOpacity(0.08),
        thickness: 1,
      ),
      iconTheme: const IconThemeData(color: textSecondary),
    );
  }
}

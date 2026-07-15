/// AVIRA Text-to-Speech Service
/// Wraps flutter_tts to provide multilingual voice alerts for livestock health.
/// PRANIVA – Advanced Veterinary Intelligence Research & Analytics
library;

import 'package:flutter_tts/flutter_tts.dart';
import 'i18n.dart';

/// Singleton TTS service that drives voice health alerts in regional languages.
class TtsService {
  TtsService._internal();

  static final TtsService _instance = TtsService._internal();

  /// Access the shared singleton.
  static TtsService get instance => _instance;

  // ── Fields ───────────────────────────────────────────────────────────────
  final FlutterTts _tts = FlutterTts();
  bool _isInitialized = false;
  String _currentLanguage = 'en-IN';
  bool _speaking = false;

  // ── Language code map ─────────────────────────────────────────────────────
  static const Map<String, String> _langCodeMap = {
    'en': 'en-IN',
    'hi': 'hi-IN',
    'kn': 'kn-IN',
    'ta': 'ta-IN',
    'te': 'te-IN',
    'mr': 'mr-IN',
    'gu': 'gu-IN',
    'bn': 'bn-IN',
  };

  // ── Getters ───────────────────────────────────────────────────────────────
  bool get isSpeaking => _speaking;
  bool get isInitialized => _isInitialized;
  String get currentLanguage => _currentLanguage;

  // ── Initialisation ────────────────────────────────────────────────────────

  /// Call once (e.g. in main() or first use) to configure flutter_tts.
  Future<void> init() async {
    if (_isInitialized) return;
    try {
      await _tts.setLanguage(_currentLanguage);
      await _tts.setSpeechRate(0.5);
      await _tts.setPitch(1.0);
      await _tts.setVolume(1.0);

      // Listen to completion and error events
      _tts.setCompletionHandler(() {
        _speaking = false;
      });
      _tts.setErrorHandler((message) {
        _speaking = false;
      });
      _tts.setStartHandler(() {
        _speaking = true;
      });
      _tts.setCancelHandler(() {
        _speaking = false;
      });

      _isInitialized = true;
    } catch (e) {
      // Graceful degradation – TTS may not be available on all devices.
      _isInitialized = false;
    }
  }

  // ── Language switching ────────────────────────────────────────────────────

  /// Changes the TTS locale to match the UI language [langCode] (e.g. 'hi', 'kn').
  Future<void> setLanguage(String langCode) async {
    try {
      if (!_isInitialized) await init();
      final ttsCode = _langCodeMap[langCode] ?? 'en-IN';
      _currentLanguage = ttsCode;
      await _tts.setLanguage(ttsCode);
    } catch (e) {
      // If TTS locale is unsupported on this device, fall back silently.
      try {
        _currentLanguage = 'en-IN';
        await _tts.setLanguage('en-IN');
      } catch (_) {}
    }
  }

  // ── Core speak ────────────────────────────────────────────────────────────

  /// Speaks [text] using the currently configured TTS locale.
  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    try {
      if (!_isInitialized) await init();
      // Stop any ongoing speech before starting
      if (_speaking) await stop();
      await _tts.speak(text);
    } catch (e) {
      _speaking = false;
    }
  }

  // ── Health alert speech ───────────────────────────────────────────────────

  /// Speaks a contextual health alert derived from [alertLevel] and [topDisease].
  ///
  /// [alertLevel] should be one of: 'CRITICAL', 'HIGH', 'MODERATE', 'NORMAL'.
  /// [topDisease] is the name of the top-ranked disease candidate (may be empty).
  Future<void> speakAlert(String alertLevel, String topDisease) async {
    try {
      if (!_isInitialized) await init();

      final String message = _buildAlertMessage(alertLevel, topDisease);
      await speak(message);
    } catch (e) {
      _speaking = false;
    }
  }

  /// Builds the spoken alert message for the current UI language.
  String _buildAlertMessage(String alertLevel, String topDisease) {
    final lang = AviraI18n.currentLang;
    final String level = alertLevel.toUpperCase();
    final String disease = topDisease.trim().isNotEmpty ? topDisease : 'unknown disease';

    switch (level) {
      case 'CRITICAL':
        return _criticalMessage(lang, disease);
      case 'HIGH':
        return _highMessage(lang, disease);
      case 'MODERATE':
        return _moderateMessage(lang, disease);
      case 'NORMAL':
      default:
        return _normalMessage(lang);
    }
  }

  String _criticalMessage(String lang, String disease) {
    switch (lang) {
      case 'hi':
        return 'गंभीर स्वास्थ्य चेतावनी! $disease। पशु चिकित्सक को तुरंत बुलाएं!';
      case 'kn':
        return 'ತೀವ್ರ ಆರೋಗ್ಯ ಎಚ್ಚರಿಕೆ! $disease. ತಕ್ಷಣ ಪಶು ವೈದ್ಯರನ್ನು ಕರೆಯಿರಿ!';
      case 'ta':
        return 'தீவிர உடல்நல எச்சரிக்கை! $disease. உடனடியாக கால்நடை மருத்துவரை அழைக்கவும்!';
      case 'te':
        return 'క్రిటికల్ ఆరోగ్య హెచ్చరిక! $disease. వెంటనే పశువైద్యుడిని పిలవండి!';
      case 'mr':
        return 'गंभीर आरोग्य इशारा! $disease. ताबडतोब पशुवैद्यास बोलवा!';
      case 'gu':
        return 'ગંભીર આરોગ્ય ચેતવણી! $disease. તાત્કાલિક પશુ ચિકિત્સક ને બોલાવો!';
      case 'bn':
        return 'জরুরি স্বাস্থ্য সতর্কতা! $disease. এখনই পশু চিকিৎসক ডাকুন!';
      default:
        return 'Critical health alert! $disease. Call veterinarian immediately!';
    }
  }

  String _highMessage(String lang, String disease) {
    switch (lang) {
      case 'hi':
        return 'उच्च चेतावनी! $disease पाया गया। कृपया आज पशु चिकित्सक से संपर्क करें।';
      case 'kn':
        return 'ಉನ್ನತ ಎಚ್ಚರಿಕೆ! $disease ಪತ್ತೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಇಂದು ಪಶು ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.';
      case 'ta':
        return 'உயர் எச்சரிக்கை! $disease கண்டறியப்பட்டது. இன்று கால்நடை மருத்துவரை தொடர்பு கொள்ளவும்.';
      case 'te':
        return 'అధిక హెచ్చరిక! $disease గుర్తించబడింది. దయచేసి నేడు పశువైద్యుడిని సంప్రదించండి.';
      case 'mr':
        return 'उच्च इशारा! $disease आढळले. कृपया आज पशुवैद्यांशी संपर्क साधा.';
      case 'gu':
        return 'ઉચ્ચ ચેતવણી! $disease મળ્યો. કૃપા કરીને આજે પશુ ચિકિત્સક ને સંપર્ક કરો.';
      case 'bn':
        return 'উচ্চ সতর্কতা! $disease শনাক্ত হয়েছে। আজই পশু চিকিৎসকের সাথে যোগাযোগ করুন।';
      default:
        return 'High alert! $disease detected. Please contact veterinarian today.';
    }
  }

  String _moderateMessage(String lang, String disease) {
    switch (lang) {
      case 'hi':
        return 'मध्यम स्तर की चेतावनी। $disease की संभावना है। पशु पर ध्यान दें।';
      case 'kn':
        return 'ಮಧ್ಯಮ ಎಚ್ಚರಿಕೆ. $disease ಸಾಧ್ಯತೆ ಇದೆ. ಪ್ರಾಣಿಯನ್ನು ಗಮನಿಸಿ.';
      case 'ta':
        return 'மிதமான எச்சரிக்கை. $disease சாத்தியம். விலங்கை கவனிக்கவும்.';
      case 'te':
        return 'మధ్యస్థ హెచ్చరిక. $disease సంభావ్యత ఉంది. జంతువుపై శ్రద్ధ వహించండి.';
      case 'mr':
        return 'मध्यम इशारा. $disease ची शक्यता आहे. प्राण्याकडे लक्ष द्या.';
      case 'gu':
        return 'મધ્યમ ચેતવણી. $disease ની સંભાવના છે. પ્રાણી પર ધ્યાન આપો.';
      case 'bn':
        return 'মাঝারি সতর্কতা। $disease সম্ভাবনা আছে। পশুর দিকে মনোযোগ দিন।';
      default:
        return 'Moderate alert. Possible $disease detected. Monitor the animal closely.';
    }
  }

  String _normalMessage(String lang) {
    switch (lang) {
      case 'hi':
        return 'पशु का स्वास्थ्य सामान्य है।';
      case 'kn':
        return 'ಪ್ರಾಣಿಯ ಆರೋಗ್ಯ ಸಾಮಾನ್ಯವಾಗಿದೆ.';
      case 'ta':
        return 'விலங்கின் ஆரோக்கியம் சாதாரணமாக உள்ளது.';
      case 'te':
        return 'జంతువు ఆరోగ్యం సాధారణంగా ఉంది.';
      case 'mr':
        return 'प्राण्याचे आरोग्य सामान्य आहे.';
      case 'gu':
        return 'પ્રાણીનું સ્વાસ્થ્ય સામાન્ય છે.';
      case 'bn':
        return 'পশুর স্বাস্থ্য স্বাভাবিক।';
      default:
        return 'Animal health is normal.';
    }
  }

  // ── Stop ──────────────────────────────────────────────────────────────────

  /// Stops any in-progress TTS playback immediately.
  Future<void> stop() async {
    try {
      await _tts.stop();
      _speaking = false;
    } catch (e) {
      _speaking = false;
    }
  }

  // ── Dispose ───────────────────────────────────────────────────────────────

  /// Releases TTS engine resources (call when app is shutting down).
  Future<void> dispose() async {
    try {
      await stop();
    } catch (_) {}
  }
}

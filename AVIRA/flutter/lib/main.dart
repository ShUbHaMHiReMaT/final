/// AVIRA App Entry Point
/// PRANIVA – Advanced Veterinary Intelligence Research & Analytics
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'models/app_state.dart';
import 'screens/splash_screen.dart';
import 'utils/theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait for consistent sensor display
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Status bar style
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AppState()),
      ],
      child: const AvirApp(),
    ),
  );
}

/// Root application widget
class AvirApp extends StatelessWidget {
  const AvirApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AVIRA – Livestock Health Monitor',
      debugShowCheckedModeBanner: false,
      theme: AviraTheme.darkTheme,
      home: const SplashScreen(),
    );
  }
}

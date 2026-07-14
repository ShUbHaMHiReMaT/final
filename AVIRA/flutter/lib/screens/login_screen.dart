/// AVIRA – Login Screen
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/app_state.dart';
import '../services/api_service.dart';
import '../utils/theme.dart';
import 'dashboard_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _farmIdCtrl     = TextEditingController(text: 'PRANIVA_FARM_01');
  final _cowIdCtrl      = TextEditingController(text: 'COW_001');
  final _serverUrlCtrl  = TextEditingController(text: 'http://10.0.2.2:5000/api/v1');

  bool _isConnecting = false;
  String? _connectionError;

  @override
  void dispose() {
    _farmIdCtrl.dispose();
    _cowIdCtrl.dispose();
    _serverUrlCtrl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isConnecting = true;
      _connectionError = null;
    });

    final appState = context.read<AppState>();
    await appState.setServerUrl(_serverUrlCtrl.text.trim());
    await appState.setCowId(_cowIdCtrl.text.trim());

    final api = ApiService(baseUrl: _serverUrlCtrl.text.trim());
    final isOnline = await api.ping();

    if (!mounted) return;

    if (isOnline) {
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => const DashboardScreen(),
          transitionDuration: const Duration(milliseconds: 500),
          transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
        ),
      );
    } else {
      setState(() {
        _connectionError =
            'Cannot reach AVIRA backend at ${_serverUrlCtrl.text}.\n'
            'Ensure the server is running and the URL is correct.';
        _isConnecting = false;
      });
    }
  }

  void _skipToDemo() {
    final appState = context.read<AppState>();
    appState.setServerUrl(_serverUrlCtrl.text.trim());
    appState.setCowId(_cowIdCtrl.text.trim());
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const DashboardScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AviraTheme.bgVoid, AviraTheme.bgDeep],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Logo
                      const Center(
                        child: Column(children: [
                          Text('🐄', style: TextStyle(fontSize: 52)),
                          SizedBox(height: 12),
                          Text('AVIRA',
                            style: TextStyle(
                              fontSize: 32, fontWeight: FontWeight.w900,
                              color: AviraTheme.brandPrimary, letterSpacing: 6,
                            ),
                          ),
                          Text('PRANIVA Livestock Intelligence',
                            style: TextStyle(
                              color: AviraTheme.textMuted, fontSize: 12, letterSpacing: 1,
                            ),
                          ),
                        ]),
                      ),
                      const SizedBox(height: 40),

                      // Farm ID
                      _buildField(
                        controller: _farmIdCtrl,
                        label: 'Farm ID',
                        icon: Icons.agriculture,
                        hint: 'PRANIVA_FARM_01',
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Farm ID required' : null,
                      ),
                      const SizedBox(height: 16),

                      // Cow ID
                      _buildField(
                        controller: _cowIdCtrl,
                        label: 'Default Animal ID',
                        icon: Icons.pets,
                        hint: 'COW_001',
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Animal ID required' : null,
                      ),
                      const SizedBox(height: 16),

                      // Server URL
                      _buildField(
                        controller: _serverUrlCtrl,
                        label: 'Backend Server URL',
                        icon: Icons.cloud,
                        hint: 'http://10.0.2.2:5000/api/v1',
                        keyboardType: TextInputType.url,
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return 'Server URL required';
                          if (!v.startsWith('http')) return 'Must start with http:// or https://';
                          return null;
                        },
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Android emulator: use 10.0.2.2\nPhysical device: use your computer\'s local IP',
                        style: TextStyle(color: AviraTheme.textMuted, fontSize: 11),
                      ),
                      const SizedBox(height: 24),

                      // Error message
                      if (_connectionError != null) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AviraTheme.brandDanger.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AviraTheme.brandDanger.withOpacity(0.4)),
                          ),
                          child: Text(
                            _connectionError!,
                            style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 13),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Connect button
                      ElevatedButton(
                        onPressed: _isConnecting ? null : _connect,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          backgroundColor: AviraTheme.brandPrimary,
                          foregroundColor: AviraTheme.bgDark,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        child: _isConnecting
                            ? const SizedBox(
                                height: 20, width: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(AviraTheme.bgDark),
                                ),
                              )
                            : const Text('🔗  Connect to AVIRA',
                                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                      ),
                      const SizedBox(height: 12),

                      // Skip button
                      TextButton(
                        onPressed: _isConnecting ? null : _skipToDemo,
                        child: Text(
                          'Continue offline (limited functionality)',
                          style: TextStyle(color: AviraTheme.textMuted, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    String? hint,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: AviraTheme.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, color: AviraTheme.brandPrimary, size: 20),
      ),
      validator: validator,
    );
  }
}

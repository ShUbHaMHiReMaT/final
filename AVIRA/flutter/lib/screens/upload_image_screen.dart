/// AVIRA – Upload Image / Vision Analysis Screen
library;

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../models/app_state.dart';
import '../models/analysis_result.dart';
import '../services/api_service.dart';
import '../utils/theme.dart';

class UploadImageScreen extends StatefulWidget {
  const UploadImageScreen({super.key});

  @override
  State<UploadImageScreen> createState() => _UploadImageScreenState();
}

class _UploadImageScreenState extends State<UploadImageScreen> {
  File? _selectedImage;
  bool _isUploading = false;
  AnalysisResult? _result;
  String? _errorMessage;
  final ImagePicker _picker = ImagePicker();

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? picked = await _picker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );
      if (picked != null) {
        setState(() {
          _selectedImage = File(picked.path);
          _result = null;
          _errorMessage = null;
        });
      }
    } catch (e) {
      setState(() => _errorMessage = 'Could not pick image: $e');
    }
  }

  Future<void> _uploadAndAnalyse() async {
    if (_selectedImage == null) return;
    final appState = context.read<AppState>();
    setState(() { _isUploading = true; _errorMessage = null; });

    try {
      final api = ApiService(baseUrl: appState.serverUrl);

      // Upload image
      final uploadResp = await api.uploadImage(
        cowId: appState.cowId,
        sessionId: appState.sessionId,
        imageFile: _selectedImage!,
      );
      final sessionId = uploadResp['session_id']?.toString() ?? appState.sessionId;

      // Run analysis
      final analysisResp = await api.runAnalysis(appState.cowId, sessionId);
      final result = AnalysisResult.fromJson(analysisResp);
      appState.setAnalysisResult(result);

      setState(() { _result = result; _isUploading = false; });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Vision analysis complete!'),
            backgroundColor: AviraTheme.brandSuccess,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isUploading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: AviraTheme.brandDanger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('🔬 Vision Analysis')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Source selector
            Row(children: [
              Expanded(child: _sourceBtn(
                icon: Icons.camera_alt,
                label: 'Camera',
                onTap: () => _pickImage(ImageSource.camera),
              )),
              const SizedBox(width: 12),
              Expanded(child: _sourceBtn(
                icon: Icons.photo_library,
                label: 'Gallery',
                onTap: () => _pickImage(ImageSource.gallery),
              )),
            ]),
            const SizedBox(height: 16),

            // Image preview
            if (_selectedImage != null) ...[
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(
                  _selectedImage!,
                  height: 250,
                  width: double.infinity,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _isUploading ? null : _uploadAndAnalyse,
                icon: _isUploading
                    ? const SizedBox(width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AviraTheme.bgDark))
                    : const Text('🧠'),
                label: Text(_isUploading ? 'Analysing…' : 'Analyse Image'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ] else
              Container(
                height: 200,
                decoration: BoxDecoration(
                  color: AviraTheme.bgMedium.withOpacity(0.4),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.1),
                    width: 2,
                    style: BorderStyle.solid,
                  ),
                ),
                child: const Center(
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.add_photo_alternate, size: 48, color: AviraTheme.textMuted),
                    SizedBox(height: 8),
                    Text('Select a cattle image to begin\nvision health analysis',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AviraTheme.textMuted)),
                  ]),
                ),
              ),

            // Error
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AviraTheme.brandDanger.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AviraTheme.brandDanger.withOpacity(0.4)),
                ),
                child: Text(_errorMessage!,
                  style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 13)),
              ),
            ],

            // Results
            if (_result != null) ...[
              const SizedBox(height: 20),
              _ResultsPanel(result: _result!),
            ],
          ],
        ),
      ),
    );
  }

  Widget _sourceBtn({required IconData icon, required String label, required VoidCallback onTap}) {
    return OutlinedButton.icon(
      onPressed: _isUploading ? null : onTap,
      icon: Icon(icon, size: 18),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 12),
      ),
    );
  }
}

class _ResultsPanel extends StatelessWidget {
  final AnalysisResult result;
  const _ResultsPanel({required this.result});

  @override
  Widget build(BuildContext context) {
    final alertColor = AviraTheme.alertColor(result.alertLevel);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('Analysis Results',
          style: TextStyle(color: AviraTheme.textSecondary, fontWeight: FontWeight.w700,
            fontSize: 13, letterSpacing: 1)),
        const SizedBox(height: 8),

        // Alert level
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: alertColor.withOpacity(0.12),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: alertColor.withOpacity(0.4)),
          ),
          child: Row(children: [
            Text(_alertIcon(result.alertLevel), style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 10),
            Text('Alert: ${result.alertLevel}',
              style: TextStyle(color: alertColor, fontWeight: FontWeight.w800, fontSize: 15)),
            const Spacer(),
            if (result.vetRequired)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AviraTheme.brandDanger.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text('🏥 VET',
                  style: TextStyle(color: Color(0xFFFCA5A5), fontSize: 11, fontWeight: FontWeight.w700)),
              ),
          ]),
        ),
        const SizedBox(height: 10),

        // Top diseases
        ...result.diseaseCandidates.take(3).map((d) {
          final color = d.probability >= 0.6 ? AviraTheme.brandDanger
              : d.probability >= 0.35 ? AviraTheme.brandWarning
              : AviraTheme.brandPrimary;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AviraTheme.bgMedium.withOpacity(0.4),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: color.withOpacity(0.2)),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(d.disease,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13))),
                  Text('${(d.probability * 100).toInt()}%',
                    style: TextStyle(color: color, fontWeight: FontWeight.w800)),
                ]),
                const SizedBox(height: 6),
                LinearProgressIndicator(
                  value: d.probability,
                  backgroundColor: Colors.white.withOpacity(0.08),
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                  borderRadius: BorderRadius.circular(3),
                ),
              ]),
            ),
          );
        }),
      ],
    );
  }

  String _alertIcon(String level) {
    switch (level) {
      case 'CRITICAL': return '🔴';
      case 'HIGH':     return '🟠';
      case 'MODERATE': return '🟡';
      default:         return '🟢';
    }
  }
}

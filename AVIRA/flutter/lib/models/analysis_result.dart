/// AVIRA Analysis Result Model
/// Represents the complete AI pipeline output returned from the backend.
library;

/// Top-level analysis result from the AI pipeline.
class AnalysisResult {
  final String cowId;
  final String sessionId;
  final String alertLevel;
  final double stressIndex;
  final String urgencyLevel;
  final bool vetRequired;
  final double pipelineConfidence;
  final List<DiseaseCandidate> diseaseCandidates;
  final List<Recommendation> recommendations;
  final List<ReasoningStep> reasoningChain;
  final VisionResult? visionResult;
  final DateTime generatedAt;

  const AnalysisResult({
    required this.cowId,
    required this.sessionId,
    required this.alertLevel,
    required this.stressIndex,
    required this.urgencyLevel,
    required this.vetRequired,
    required this.pipelineConfidence,
    required this.diseaseCandidates,
    required this.recommendations,
    required this.reasoningChain,
    this.visionResult,
    required this.generatedAt,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    final report = json['analysis'] as Map<String, dynamic>? ?? {};
    final healthSummary = report['health_summary'] as Map<String, dynamic>? ?? {};
    final recs = (json['recommendations'] as List? ?? []).map((r) {
      if (r is Map<String, dynamic>) return Recommendation.fromJson(r);
      return Recommendation(action: r.toString(), category: 'INFO', priority: 9);
    }).toList();

    return AnalysisResult(
      cowId: json['cow_id']?.toString() ?? '',
      sessionId: json['session_id']?.toString() ?? '',
      alertLevel: healthSummary['alert_level']?.toString() ?? 'UNKNOWN',
      stressIndex: (healthSummary['overall_stress_index'] as num?)?.toDouble() ?? 0.0,
      urgencyLevel: healthSummary['urgency']?.toString() ?? 'LOW',
      vetRequired: healthSummary['vet_required'] as bool? ?? false,
      pipelineConfidence: (report['pipeline_confidence'] as num?)?.toDouble() ?? 0.0,
      diseaseCandidates: (json['top_diseases'] as List? ?? [])
          .map((d) => DiseaseCandidate.fromJson(d as Map<String, dynamic>))
          .toList(),
      recommendations: recs,
      reasoningChain: (json['reasoning_chain'] as List? ?? [])
          .map((s) => ReasoningStep.fromJson(s as Map<String, dynamic>))
          .toList(),
      generatedAt: DateTime.tryParse(report['generated_at']?.toString() ?? '') ?? DateTime.now(),
    );
  }
}

/// A disease probability candidate from the AI reasoning engine.
class DiseaseCandidate {
  final String diseaseId;
  final String disease;
  final double probability;
  final String confidence;
  final String urgency;
  final bool vetRequired;
  final List<String> matchedEvidence;
  final List<String> missingEvidence;
  final List<String> recommendations;

  const DiseaseCandidate({
    required this.diseaseId,
    required this.disease,
    required this.probability,
    required this.confidence,
    required this.urgency,
    required this.vetRequired,
    required this.matchedEvidence,
    required this.missingEvidence,
    required this.recommendations,
  });

  factory DiseaseCandidate.fromJson(Map<String, dynamic> json) {
    return DiseaseCandidate(
      diseaseId: json['disease_id']?.toString() ?? '',
      disease: json['disease']?.toString() ?? '',
      probability: (json['probability'] as num?)?.toDouble() ?? 0.0,
      confidence: json['confidence']?.toString() ?? 'UNKNOWN',
      urgency: json['urgency']?.toString() ?? 'UNKNOWN',
      vetRequired: json['vet_required'] as bool? ?? false,
      matchedEvidence: List<String>.from(json['matched_evidence'] ?? []),
      missingEvidence: List<String>.from(json['missing_evidence'] ?? []),
      recommendations: List<String>.from(json['recommendations'] ?? []),
    );
  }
}

/// A single recommendation action item.
class Recommendation {
  final String action;
  final String category;
  final int priority;
  final String? rationale;

  const Recommendation({
    required this.action,
    required this.category,
    required this.priority,
    this.rationale,
  });

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    return Recommendation(
      action: json['action']?.toString() ?? '',
      category: json['category']?.toString() ?? 'INFO',
      priority: (json['priority'] as num?)?.toInt() ?? 9,
      rationale: json['rationale']?.toString(),
    );
  }
}

/// A step in the AI reasoning chain.
class ReasoningStep {
  final String step;
  final String agent;
  final String finding;
  final double confidence;
  final List<String> evidence;

  const ReasoningStep({
    required this.step,
    required this.agent,
    required this.finding,
    required this.confidence,
    required this.evidence,
  });

  factory ReasoningStep.fromJson(Map<String, dynamic> json) {
    return ReasoningStep(
      step: json['step']?.toString() ?? '',
      agent: json['agent']?.toString() ?? '',
      finding: json['finding']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      evidence: List<String>.from(json['evidence'] ?? []),
    );
  }
}

/// Vision analysis result.
class VisionResult {
  final bool hasDetections;
  final String summary;
  final List<DetectedCondition> detectedConditions;

  const VisionResult({
    required this.hasDetections,
    required this.summary,
    required this.detectedConditions,
  });

  factory VisionResult.fromJson(Map<String, dynamic> json) {
    return VisionResult(
      hasDetections: json['has_detections'] as bool? ?? false,
      summary: json['summary']?.toString() ?? '',
      detectedConditions: (json['detected_conditions'] as List? ?? [])
          .map((d) => DetectedCondition.fromJson(d as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// A single visual condition detected by the vision agent.
class DetectedCondition {
  final String condition;
  final String displayName;
  final double confidence;

  const DetectedCondition({
    required this.condition,
    required this.displayName,
    required this.confidence,
  });

  factory DetectedCondition.fromJson(Map<String, dynamic> json) {
    return DetectedCondition(
      condition: json['condition']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

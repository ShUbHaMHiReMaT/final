"""
AVIRA – Agent 2: Disease Reasoning Engine (16-Disease Edition)
===============================================================
Computes posterior probability scores for 16 bovine diseases using
Bayesian-style evidence weighting against the knowledge base.

Disease roster (from veterinary reference chart):
  1.  Mastitis
  2.  Foot & Mouth Disease (FMD)
  3.  Lumpy Skin Disease (LSD)
  4.  Haemorrhagic Septicaemia (HS)
  5.  Black Quarter (BQ)
  6.  Theileriosis
  7.  Babesiosis
  8.  Brucellosis
  9.  Johne's Disease (Paratuberculosis)
  10. Milk Fever (Hypocalcaemia)
  11. Ketosis
  12. Bloat (Ruminal Tympany)
  13. Pneumonia (BRD)
  14. Tick Fever (Anaplasmosis / general)
  15. Worm Infestation (Helminthiasis)
  16. Heat Stress (Hyperthermia)

Inputs:
    vital_analysis    – output of Agent 1
    manual_data       – farmer manual input dict
    vision_data       – output of Agent 3 (optional)

Outputs:
    {
        "disease_candidates": [ { disease, probability, confidence,
                                   urgency, vet_required, evidence_matched,
                                   evidence_missing, reasoning_chain,
                                   treatment_info, recommendations } ],
        "reasoning_chain": [str],
        "top_alert": str,
        "agent_confidence": float,
    }
"""

import logging
from typing import Optional

from services.knowledge_service import knowledge_base

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Vital thresholds used in scoring
# ─────────────────────────────────────────────

def _hr_status(vitals: dict) -> str:
    return vitals.get("heart_rate", {}).get("status", "UNKNOWN")

def _hr_val(vitals: dict) -> Optional[float]:
    return vitals.get("heart_rate", {}).get("value")

def _temp_val(vitals: dict) -> Optional[float]:
    return vitals.get("temperature", {}).get("value")

def _temp_status(vitals: dict) -> str:
    return vitals.get("temperature", {}).get("status", "UNKNOWN")

def _spo2_val(vitals: dict) -> Optional[float]:
    return vitals.get("spo2", {}).get("value")

def _motion_status(vitals: dict) -> str:
    return vitals.get("motion", {}).get("status", "UNKNOWN")

def _motion_val(vitals: dict) -> Optional[float]:
    return vitals.get("motion", {}).get("value")


# ─────────────────────────────────────────────
#  Disease Scorers
# ─────────────────────────────────────────────

def _score_mastitis(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Mastitis: Temp 39.5-41°C, HR 80-120, udder swelling/pain, milk change."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 39.5 <= temp <= 41.0:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (mastitis range 39.5–41°C)")
        elif temp > 38.5:
            score += 0.08; evidence_matched.append(f"Mild temperature elevation {temp:.1f}°C")
        else:
            evidence_missing.append("Fever not present")
    else:
        evidence_missing.append("Temperature not recorded")

    hr = _hr_val(vitals)
    if hr is not None:
        if 80 <= hr <= 120:
            score += 0.20; evidence_matched.append(f"Elevated HR {int(hr)} BPM (mastitis range 80–120)")
        elif hr > 72:
            score += 0.08; evidence_matched.append(f"Slightly elevated HR {int(hr)} BPM")
        else:
            evidence_missing.append("HR within normal range")
    else:
        evidence_missing.append("Heart rate not recorded")

    # Manual inputs
    obs = str(manual.get("observations", "")).lower()
    milk = manual.get("milk_production")

    if any(k in obs for k in ["udder", "mastitis", "swelling", "teat", "clot", "milk abnormal", "hard quarter"]):
        score += 0.35; evidence_matched.append("Udder/teat abnormality reported in observations")
    else:
        evidence_missing.append("No udder abnormality reported")

    if milk is not None:
        try:
            milk = float(milk)
            if milk < 5:
                score += 0.15; evidence_matched.append(f"Very low milk production: {milk:.1f} L")
            elif milk < 12:
                score += 0.08; evidence_matched.append(f"Reduced milk production: {milk:.1f} L")
        except (ValueError, TypeError):
            pass
    else:
        evidence_missing.append("Milk production not recorded")

    # Vision
    if vision.get("udder_abnormality", {}).get("detected"):
        score += 0.20; evidence_matched.append("Vision: udder abnormality detected")

    chain.append(f"Mastitis scoring: temp={temp}, HR={hr}, obs_keywords matched={bool(evidence_matched)}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_fmd(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Foot & Mouth Disease: Temp 40-41°C, HR 80-120, lesions on mouth/feet."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 41.0:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (FMD range 40–41°C)")
        elif temp > 39.3:
            score += 0.10; evidence_matched.append(f"Elevated temperature {temp:.1f}°C")
        else:
            evidence_missing.append("Fever not present")

    hr = _hr_val(vitals)
    if hr is not None and 80 <= hr <= 120:
        score += 0.15; evidence_matched.append(f"HR {int(hr)} BPM – elevated (FMD range 80–120)")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["blister", "lesion", "sore", "mouth", "tongue", "drool", "saliva", "lameness", "foot", "fmd"]):
        score += 0.40; evidence_matched.append("FMD-specific lesion/lameness reported")
    else:
        evidence_missing.append("No blisters, mouth lesions, or lameness reported")

    appetite = manual.get("appetite")
    if appetite is not None:
        try:
            if float(appetite) <= 3:
                score += 0.10; evidence_matched.append(f"Very low appetite score {appetite} (mouth pain)")
        except (ValueError, TypeError):
            pass

    # Vision
    if vision.get("skin_lesions", {}).get("detected"):
        score += 0.10; evidence_matched.append("Vision: skin lesions detected")

    chain.append(f"FMD scoring: temp={temp}, lesion_obs={any(k in obs for k in ['blister','lesion','mouth'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_lsd(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Lumpy Skin Disease: Temp 40-41.5°C, HR 90-120, skin nodules."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 41.5:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (LSD range 40–41.5°C)")
        elif temp > 39.5:
            score += 0.10; evidence_matched.append(f"Elevated temperature {temp:.1f}°C")
        else:
            evidence_missing.append("Fever not present")

    hr = _hr_val(vitals)
    if hr is not None and 90 <= hr <= 120:
        score += 0.15; evidence_matched.append(f"HR {int(hr)} BPM (LSD range 90–120)")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["lump", "nodule", "skin", "bumps", "lesion", "lsd", "lumpy"]):
        score += 0.45; evidence_matched.append("Skin nodules/lumps reported – highly specific for LSD")
    else:
        evidence_missing.append("No skin nodules or lumps reported (key LSD indicator)")

    if vision.get("skin_lesions", {}).get("detected"):
        score += 0.10; evidence_matched.append("Vision: skin lesions detected")

    chain.append(f"LSD scoring: temp={temp}, nodule_reported={any(k in obs for k in ['lump','nodule'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_hs(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Haemorrhagic Septicaemia: Temp 41-42°C, HR 100-140, sudden onset."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if temp >= 41.0:
            score += 0.35; evidence_matched.append(f"High fever {temp:.1f}°C (HS range 41–42°C)")
        elif temp >= 40.0:
            score += 0.15; evidence_matched.append(f"Elevated temperature {temp:.1f}°C")
        else:
            evidence_missing.append("Fever not at HS threshold (≥41°C)")

    hr = _hr_val(vitals)
    if hr is not None:
        if hr >= 100:
            score += 0.30; evidence_matched.append(f"Very elevated HR {int(hr)} BPM (HS range 100–140)")
        elif hr > 84:
            score += 0.10; evidence_matched.append(f"Elevated HR {int(hr)} BPM")
        else:
            evidence_missing.append("HR not elevated to HS level")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["swelling", "throat", "neck", "breathing", "haemorrhagic", "hs", "sudden", "pneumonia septicaemia"]):
        score += 0.25; evidence_matched.append("Throat/neck swelling or sudden onset reported")
    else:
        evidence_missing.append("No throat swelling or sudden onset reported")

    appetite = manual.get("appetite")
    if appetite is not None:
        try:
            if float(appetite) <= 2:
                score += 0.05; evidence_matched.append("Complete appetite loss")
        except (ValueError, TypeError):
            pass

    chain.append(f"HS scoring: temp={temp}, HR={hr}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_bq(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Black Quarter: Temp 40.5-42°C, HR 100-140, muscle swelling/crepitation."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.5 <= temp <= 42.0:
            score += 0.30; evidence_matched.append(f"High fever {temp:.1f}°C (BQ range 40.5–42°C)")
        elif temp >= 40.0:
            score += 0.12; evidence_matched.append(f"Elevated temperature {temp:.1f}°C")
        else:
            evidence_missing.append("Fever not at BQ threshold")

    hr = _hr_val(vitals)
    if hr is not None and hr >= 100:
        score += 0.25; evidence_matched.append(f"Very elevated HR {int(hr)} BPM (BQ range 100–140)")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["swelling", "muscle", "hindquarter", "hind leg", "crepitus", "blackleg", "bq", "black quarter", "gas gangrene"]):
        score += 0.40; evidence_matched.append("Muscle swelling / blackleg symptoms reported – key BQ indicator")
    else:
        evidence_missing.append("No muscle swelling/crepitation reported (critical BQ indicator)")

    motion = _motion_status(vitals)
    if motion in ("VERY_LOW", "LOW"):
        score += 0.05; evidence_matched.append("Very low motion – lameness suspected")

    chain.append(f"BQ scoring: temp={temp}, HR={hr}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_theileriosis(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Theileriosis: Temp 40-42°C, HR 90-130, lymph nodes, anaemia, ticks."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 42.0:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (Theileriosis range 40–42°C)")
        else:
            evidence_missing.append("Fever not in Theileriosis range")

    hr = _hr_val(vitals)
    if hr is not None and 90 <= hr <= 130:
        score += 0.15; evidence_matched.append(f"Elevated HR {int(hr)} BPM")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["tick", "theileria", "lymph", "anaemia", "pale", "swollen gland"]):
        score += 0.45; evidence_matched.append("Tick exposure / lymph node swelling / anaemia reported")
    else:
        evidence_missing.append("No tick exposure or lymph node swelling mentioned")

    chain.append(f"Theileriosis scoring: temp={temp}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_babesiosis(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Babesiosis: Temp 40-41.5°C, HR 90-130, red urine, anaemia, ticks."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 41.5:
            score += 0.20; evidence_matched.append(f"Fever {temp:.1f}°C (Babesiosis range 40–41.5°C)")
        else:
            evidence_missing.append("Temperature not in Babesiosis range")

    hr = _hr_val(vitals)
    if hr is not None and hr >= 90:
        score += 0.15; evidence_matched.append(f"Elevated HR {int(hr)} BPM")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["red urine", "redwater", "babesia", "tick", "haemoglobin", "haemolysis", "blood urine"]):
        score += 0.50; evidence_matched.append("Red urine / tick exposure / haemolysis reported – key Babesiosis signs")
    else:
        evidence_missing.append("No red urine or tick infestation mentioned (key Babesiosis signs)")

    chain.append(f"Babesiosis scoring: temp={temp}, red_urine_obs={any(k in obs for k in ['red urine','redwater'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_brucellosis(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Brucellosis: Usually normal vitals, key indicator = late-term abortion."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["abortion", "aborted", "stillborn", "placenta", "brucella", "brucellosis", "repeat breeding", "infertility"]):
        score += 0.65; evidence_matched.append("Abortion / retained placenta / infertility reported – primary Brucellosis indicator")
    else:
        evidence_missing.append("No abortion or reproductive failure reported (primary Brucellosis indicator)")

    # Normal vitals slightly support Brucellosis (not FMD/HS)
    temp = _temp_val(vitals)
    if temp is not None and 37.8 <= temp <= 39.3:
        score += 0.05; evidence_matched.append("Normal temperature consistent with Brucellosis")

    chain.append(f"Brucellosis scoring: abortion_obs={any(k in obs for k in ['abortion','aborted'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_johnes(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Johne's Disease: Normal vitals, chronic diarrhoea, weight loss, bottle jaw."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["diarrhoea", "diarrhea", "watery stool", "weight loss", "thin", "wasting", "bottle jaw", "johne", "paratuberculosis"]):
        score += 0.60; evidence_matched.append("Chronic diarrhoea / progressive weight loss / bottle jaw reported")
    else:
        evidence_missing.append("No chronic diarrhoea or weight loss reported")

    milk = manual.get("milk_production")
    if milk is not None:
        try:
            if float(milk) < 8:
                score += 0.10; evidence_matched.append(f"Reduced milk production {milk} L")
        except (ValueError, TypeError):
            pass

    temp = _temp_val(vitals)
    if temp is not None and 37.8 <= temp <= 39.3:
        score += 0.05; evidence_matched.append("Normal temperature (Johne's typically normal vitals)")

    chain.append(f"Johne's scoring: diarrhoea_obs={any(k in obs for k in ['diarrhoea','wasting'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_milk_fever(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Milk Fever: Low/normal temp, rapid weak HR 90-120, recumbency, post-calving."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if temp < 38.0:
            score += 0.25; evidence_matched.append(f"Low temperature {temp:.1f}°C – hypocalcaemia typical")
        elif temp <= 39.0:
            score += 0.10; evidence_matched.append(f"Normal-low temperature {temp:.1f}°C")

    hr = _hr_val(vitals)
    if hr is not None and 90 <= hr <= 120:
        score += 0.20; evidence_matched.append(f"Rapid weak HR {int(hr)} BPM (Milk Fever range 90–120)")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["calving", "calved", "milk fever", "cannot stand", "recumbent", "hypocalcaemia", "cold legs", "muscle tremor", "down cow"]):
        score += 0.50; evidence_matched.append("Post-calving / recumbency / milk fever reported – primary indicator")
    else:
        evidence_missing.append("No calving event or recumbency reported (key Milk Fever context)")

    motion = _motion_status(vitals)
    if motion == "VERY_LOW":
        score += 0.05; evidence_matched.append("Very low motion – possible recumbency")

    chain.append(f"Milk Fever scoring: temp={temp}, post_calving_obs={any(k in obs for k in ['calving','calved','cannot stand'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_ketosis(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Ketosis: Normal temp, normal-high HR, low milk, low appetite, early lactation."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["ketosis", "acetonaemia", "sweet smell", "acetone", "ketone", "early lactation", "negative energy"]):
        score += 0.45; evidence_matched.append("Ketosis-specific signs reported (sweet smell / acetonaemia)")
    else:
        evidence_missing.append("No ketosis-specific observations")

    milk = manual.get("milk_production")
    if milk is not None:
        try:
            if float(milk) < 10:
                score += 0.20; evidence_matched.append(f"Significant milk drop {milk} L – post-peak lactation risk")
        except (ValueError, TypeError):
            pass

    appetite = manual.get("appetite")
    if appetite is not None:
        try:
            if float(appetite) <= 4:
                score += 0.20; evidence_matched.append(f"Reduced appetite score {appetite}/10")
        except (ValueError, TypeError):
            pass

    rumination = manual.get("rumination")
    if rumination is not None:
        try:
            if float(rumination) <= 4:
                score += 0.10; evidence_matched.append(f"Reduced rumination {rumination}/10")
        except (ValueError, TypeError):
            pass

    temp = _temp_val(vitals)
    if temp is not None and 37.8 <= temp <= 39.5:
        score += 0.05; evidence_matched.append("Normal temperature – consistent with Ketosis")

    chain.append("Ketosis scoring based on metabolic indicators")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_bloat(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Bloat: Normal temp, HR 80-120, sudden cessation of rumination, abdominal distension."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["bloat", "bloated", "swollen belly", "distended", "tympany", "rumen", "kicking", "abdomen", "gassy"]):
        score += 0.55; evidence_matched.append("Bloat / abdominal distension reported – primary indicator")
    else:
        evidence_missing.append("No abdominal distension or bloat reported (key Bloat indicator)")

    rumination = manual.get("rumination")
    if rumination is not None:
        try:
            if float(rumination) == 0:
                score += 0.25; evidence_matched.append("Complete cessation of rumination")
            elif float(rumination) <= 2:
                score += 0.15; evidence_matched.append(f"Very low rumination {rumination}/10")
        except (ValueError, TypeError):
            pass
    else:
        evidence_missing.append("Rumination score not recorded")

    hr = _hr_val(vitals)
    if hr is not None and 80 <= hr <= 120:
        score += 0.10; evidence_matched.append(f"Elevated HR {int(hr)} BPM consistent with abdominal discomfort")

    motion = _motion_status(vitals)
    if motion in ("HIGH", "VERY_HIGH"):
        score += 0.10; evidence_matched.append("High motion – restlessness / kicking belly")

    chain.append(f"Bloat scoring: distension_obs={any(k in obs for k in ['bloat','distended'])}, rumination={rumination}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_pneumonia(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Pneumonia: Temp 40-41°C, HR 90-130, cough, nasal discharge, laboured breathing."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 41.0:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (Pneumonia range 40–41°C)")
        elif temp > 39.3:
            score += 0.10; evidence_matched.append(f"Elevated temperature {temp:.1f}°C")

    hr = _hr_val(vitals)
    if hr is not None and 90 <= hr <= 130:
        score += 0.15; evidence_matched.append(f"Elevated HR {int(hr)} BPM (Pneumonia range 90–130)")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["cough", "nasal", "breathing", "respiratory", "pneumonia", "wheeze", "discharge", "laboured"]):
        score += 0.45; evidence_matched.append("Cough / nasal discharge / laboured breathing reported")
    else:
        evidence_missing.append("No respiratory signs reported (key Pneumonia indicator)")

    appetite = manual.get("appetite")
    if appetite is not None:
        try:
            if float(appetite) <= 4:
                score += 0.10; evidence_matched.append(f"Reduced appetite {appetite}/10")
        except (ValueError, TypeError):
            pass

    chain.append(f"Pneumonia scoring: temp={temp}, respiratory_obs={any(k in obs for k in ['cough','nasal','breathing'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_tick_fever(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Tick Fever (general): Temp 40-42°C, HR 90-130, visible tick infestation."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 40.0 <= temp <= 42.0:
            score += 0.25; evidence_matched.append(f"Fever {temp:.1f}°C (Tick Fever range 40–42°C)")
        else:
            evidence_missing.append("Temperature not in tick fever range")

    hr = _hr_val(vitals)
    if hr is not None and hr >= 90:
        score += 0.15; evidence_matched.append(f"Elevated HR {int(hr)} BPM")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["tick", "tick fever", "anaplasmosis", "anaemia", "pale gum", "weakness"]):
        score += 0.45; evidence_matched.append("Tick infestation / anaemia / tick fever reported")
    else:
        evidence_missing.append("No tick exposure or anaemia reported")

    chain.append(f"Tick Fever scoring: temp={temp}, tick_obs={any(k in obs for k in ['tick','anaplasmosis'])}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_worm_infestation(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Worm Infestation: Usually normal vitals, weight loss, diarrhoea, bottle jaw."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["worm", "parasite", "helminth", "diarrhoea", "weight loss", "bottle jaw", "thin", "rough coat", "pale gum"]):
        score += 0.50; evidence_matched.append("Worm / parasite indicators in observations")
    else:
        evidence_missing.append("No worm or parasite signs reported")

    milk = manual.get("milk_production")
    if milk is not None:
        try:
            if float(milk) < 10:
                score += 0.15; evidence_matched.append(f"Reduced milk production {milk} L")
        except (ValueError, TypeError):
            pass

    appetite = manual.get("appetite")
    if appetite is not None:
        try:
            if float(appetite) <= 5:
                score += 0.10; evidence_matched.append(f"Reduced appetite {appetite}/10")
        except (ValueError, TypeError):
            pass

    # Normal vitals slightly support worm (not fever diseases)
    temp = _temp_val(vitals)
    if temp is not None and 37.8 <= temp <= 39.3:
        score += 0.05; evidence_matched.append("Normal temperature consistent with chronic parasitism")

    chain.append("Worm Infestation scoring based on chronic production indicators")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


def _score_heat_stress(vitals: dict, manual: dict, vision: dict) -> tuple[float, list, list, list]:
    """Heat Stress: Temp 39.5-41°C, HR 80-110, high water intake, low rumination."""
    evidence_matched, evidence_missing, chain = [], [], []
    score = 0.0

    temp = _temp_val(vitals)
    if temp is not None:
        if 39.5 <= temp <= 41.0:
            score += 0.25; evidence_matched.append(f"Elevated temperature {temp:.1f}°C (Heat Stress range 39.5–41°C)")
        elif temp > 39.3:
            score += 0.10; evidence_matched.append(f"Mildly elevated temperature {temp:.1f}°C")
        else:
            evidence_missing.append("Temperature not elevated")

    hr = _hr_val(vitals)
    if hr is not None and 80 <= hr <= 110:
        score += 0.15; evidence_matched.append(f"Elevated HR {int(hr)} BPM (Heat Stress range 80–110)")

    water = manual.get("water_intake")
    if water is not None:
        try:
            if float(water) > 70:
                score += 0.25; evidence_matched.append(f"High water intake {water} L – heat stress indicator")
        except (ValueError, TypeError):
            pass

    rumination = manual.get("rumination")
    if rumination is not None:
        try:
            if float(rumination) <= 4:
                score += 0.15; evidence_matched.append(f"Reduced rumination {rumination}/10 – heat-induced anorexia")
        except (ValueError, TypeError):
            pass

    motion = _motion_status(vitals)
    if motion in ("VERY_LOW", "LOW"):
        score += 0.10; evidence_matched.append("Low motion – heat stress lethargy")

    obs = str(manual.get("observations", "")).lower()
    if any(k in obs for k in ["heat", "panting", "drool", "shade", "hot", "sweating"]):
        score += 0.10; evidence_matched.append("Heat stress symptoms mentioned in observations")

    chain.append(f"Heat Stress scoring: temp={temp}, water={water}, rumination={rumination}")
    return min(score, 0.98), evidence_matched, evidence_missing, chain


# ─────────────────────────────────────────────
#  Disease Catalogue
# ─────────────────────────────────────────────
# Maps disease_id → (scorer_fn, display_name)

DISEASE_SCORERS = {
    "MASTITIS":         (_score_mastitis,        "Mastitis"),
    "FMD":              (_score_fmd,             "Foot & Mouth Disease"),
    "LSD":              (_score_lsd,             "Lumpy Skin Disease"),
    "HS":               (_score_hs,              "Haemorrhagic Septicaemia"),
    "BLACK_QUARTER":    (_score_bq,              "Black Quarter"),
    "THEILERIOSIS":     (_score_theileriosis,    "Theileriosis"),
    "BABESIOSIS":       (_score_babesiosis,       "Babesiosis"),
    "BRUCELLOSIS":      (_score_brucellosis,      "Brucellosis"),
    "JOHNES":           (_score_johnes,           "Johne's Disease"),
    "MILK_FEVER":       (_score_milk_fever,       "Milk Fever"),
    "KETOSIS":          (_score_ketosis,          "Ketosis"),
    "BLOAT":            (_score_bloat,            "Bloat"),
    "PNEUMONIA":        (_score_pneumonia,        "Pneumonia"),
    "TICK_FEVER":       (_score_tick_fever,       "Tick Fever"),
    "WORM_INFESTATION": (_score_worm_infestation, "Worm Infestation"),
    "HEAT_STRESS":      (_score_heat_stress,      "Heat Stress"),
}


# ─────────────────────────────────────────────
#  Agent Class
# ─────────────────────────────────────────────

class DiseaseReasoningAgent:
    """
    Agent 2 – 16-Disease Bayesian Reasoning Engine.

    Scores each disease against vital sign deviations, manual observations,
    and vision findings. Returns a ranked list of disease candidates.
    """

    def analyse(
        self,
        vital_analysis:  dict,
        manual_data:     Optional[dict] = None,
        vision_data:     Optional[dict] = None,
    ) -> dict:
        """
        Run disease reasoning.

        Args:
            vital_analysis: Agent 1 output
            manual_data:    Farmer manual input dict
            vision_data:    Agent 3 vision output (optional)

        Returns:
            Disease reasoning result dict.
        """
        if manual_data is None:
            manual_data = {}
        if vision_data is None:
            vision_data = {}

        vitals = vital_analysis.get("vitals", {})
        candidates = []
        global_chain = [
            f"Stress index: {vital_analysis.get('stress_index', 0):.3f}",
            f"Alert level: {vital_analysis.get('alert_level', 'UNKNOWN')}",
            f"Breed: {vital_analysis.get('breed', 'DEFAULT')}",
        ]

        for disease_id, (scorer_fn, display_name) in DISEASE_SCORERS.items():
            try:
                prob, matched, missing, chain = scorer_fn(vitals, manual_data, vision_data)
            except Exception as exc:
                logger.error("Scorer error for %s: %s", disease_id, exc)
                prob, matched, missing, chain = 0.0, [], [], []

            # Fetch metadata from knowledge base
            kb_entry = knowledge_base.get_disease(disease_id) or {}
            urgency      = kb_entry.get("urgency", "MEDIUM")
            vet_required = kb_entry.get("vet_required", False)
            treatment    = kb_entry.get("treatment_info", {})

            # Confidence: higher when more evidence matched
            evidence_total = len(matched) + len(missing)
            confidence_str = (
                "HIGH"   if len(matched) >= 3
                else "MEDIUM" if len(matched) >= 1
                else "LOW"
            )

            candidates.append({
                "disease":          display_name,
                "disease_id":       disease_id,
                "probability":      round(prob, 4),
                "confidence":       confidence_str,
                "urgency":          urgency,
                "vet_required":     vet_required,
                "evidence_matched": matched,
                "evidence_missing": missing,
                "reasoning_chain":  chain,
                "treatment_info":   treatment,
            })

        # Sort by probability descending
        candidates.sort(key=lambda x: x["probability"], reverse=True)

        # Determine top alert level from top-3 diseases
        top3 = candidates[:3]
        top_alert = "NORMAL"
        for c in top3:
            if c["probability"] >= 0.50 and c["urgency"] == "CRITICAL":
                top_alert = "CRITICAL"
                break
            if c["probability"] >= 0.40 and c["urgency"] in ("CRITICAL", "HIGH"):
                top_alert = "HIGH"
                break
            if c["probability"] >= 0.25:
                top_alert = "MODERATE"

        global_chain.append(
            f"Top disease: {candidates[0]['disease']} ({candidates[0]['probability']:.0%})"
        )
        global_chain.append(
            f"Top 3: {', '.join(c['disease'] for c in top3)}"
        )

        # Agent confidence: weighted by how much valid vital data was available
        stress = vital_analysis.get("stress_index", 0)
        agent_confidence = round(
            min(0.40 + stress * 0.30 + vital_analysis.get("confidence", 0) * 0.30, 0.92),
            3,
        )

        logger.info(
            "Agent2 | top=%s (%.0f%%) | alert=%s | confidence=%.2f",
            candidates[0]["disease"], candidates[0]["probability"] * 100,
            top_alert, agent_confidence,
        )

        return {
            "disease_candidates": candidates,
            "reasoning_chain":    global_chain,
            "top_alert":          top_alert,
            "agent_confidence":   agent_confidence,
        }

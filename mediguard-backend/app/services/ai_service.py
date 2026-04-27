import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

# Configure the Local LLM Endpoint
# Grabs the URL from the docker-compose environment variable we set earlier
OLLAMA_API_URL = os.getenv("LLM_API_URL", "http://cdss-llm:11434/api/generate")
MODEL_NAME = "llama3"


def generate_clinical_prediction(consultation, patient, symptoms):
    """
    Optimized for speed with local Llama 3 model.
    """
    # 1. Format symptoms concisely
    symptoms_text = ", ".join(
        [f"{s.name} ({s.severity}/{s.duration})" for s in symptoms]
    )

    # 2. SHORTER, more focused prompt (less tokens = faster inference)
    prompt = f"""You are a Clinical Decision Support AI. Analyze and return ONLY valid JSON.

PATIENT: {patient.gender}, DOB: {patient.date_of_birth}
Allergies: {patient.known_allergies or 'None'}
Conditions: {patient.chronic_conditions or 'None'}

VITALS: BP {consultation.bp_systolic}/{consultation.bp_diastolic}, HR {consultation.heart_rate}, Temp {consultation.temperature}

CHIEF COMPLAINT: {consultation.chief_complaint}
SYMPTOMS: {symptoms_text}

Return JSON:
{{
  "primary_disease": "Most likely diagnosis",
  "primary_confidence": 0.95,
  "reasoning": "Brief clinical reasoning",
  "confirmatory_symptoms": ["symptom1", "symptom2"],
  "prescribing_alerts": ["alert if any"],
  "differentials": [{{"disease": "Alternative", "reasoning": "Why"}}],
  "recommended_tests": ["test1", "test2"]
}}"""

    # 3. Optimized payload
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            # Removed num_thread - controlled by environment variable now
            "num_ctx": 4096,  # Reduced from 8192 - faster with q4_0 cache
            "num_predict": 512,  # Reduced from 1024 - your JSON won't be that long
            "temperature": 0.1,  # Lower = more deterministic = faster
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        result_data = response.json()
        model_output_string = result_data.get("response", "")
        return json.loads(model_output_string)

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to local LLM: {e}")
        raise RuntimeError(
            "AI Inference Engine is currently unreachable. Please check the Docker container."
        )
    except json.JSONDecodeError:
        logger.error(f"Model failed to return valid JSON: {model_output_string}")
        raise ValueError("AI failed to return valid JSON.")


def generate_lab_interpretation(patient, lab_request):
    """
    Generates a brief AI Lab Interpretation string based on the result.
    """
    prompt = f"""
    You are an expert clinical laboratory specialist AI. 
    Analyze the following lab test result for this patient and provide a brief interpretation.
    
    PATIENT PROFILE:
    - Age/DOB: {patient.date_of_birth}
    - Gender: {patient.gender}
    - Known Allergies: {patient.known_allergies}
    - Chronic Conditions: {patient.chronic_conditions}
    
    LAB TEST DETAILS:
    - Test Name: {lab_request.test_name}
    - Result: {lab_request.result_value}
    - Reference Range: {lab_request.reference_range or "Not provided"}
    - Flag: {lab_request.flag or "Normal"}
    - Notes: {lab_request.notes or "None"}
    
    INSTRUCTIONS:
    Provide a concise (1-3 sentences) clinical interpretation of this result.
    Highlight if the result is critical or concerning given the patient's history.
    Return ONLY the interpretation string.
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        # Notice we omit "format": "json" here because we just want a standard text string back
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        response.raise_for_status()

        result_data = response.json()
        return result_data.get("response", "").strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to local LLM for lab interpretation: {e}")
        return "AI interpretation currently unavailable due to engine offline."

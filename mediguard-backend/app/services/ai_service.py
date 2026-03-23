import os
import json
import google.generativeai as genai

# Configure the API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_clinical_prediction(consultation, patient, symptoms):
    """
    Takes structured clinical data, engineers a prompt, and calls Gemini.
    """
    # 1. Format the symptoms into a readable string (using the updated attributes)
    symptoms_text = ", ".join(
        [f"{s.name} (Severity: {s.severity}, Duration: {s.duration})" for s in symptoms]
    )

    # 2. Build the clinical prompt
    prompt = f"""
    You are an expert Clinical Decision Support System (CDSS) AI assistant. 
    Analyze the following patient data and provide a differential diagnosis.
    
    PATIENT PROFILE:
    - Age/DOB: {patient.date_of_birth}
    - Gender: {patient.gender}
    - Known Allergies: {patient.known_allergies}
    - Chronic Conditions: {patient.chronic_conditions}
    
    CONSULTATION DETAILS:
    - Chief Complaint: {consultation.chief_complaint}
    - Clinical Notes: {consultation.clinical_notes or "None"}
    
    VITALS:
    - BP: {consultation.bp_systolic}/{consultation.bp_diastolic}
    - Heart Rate: {consultation.heart_rate}
    - Temp: {consultation.temperature}
    
    REPORTED SYMPTOMS:
    {symptoms_text}
    
    INSTRUCTIONS:
    Analyze the data and return a STRICT JSON object matching this exact schema:
    {{
        "primary_disease": "Name of the most likely condition",
        "primary_confidence": 0.95, // Float between 0.0 and 1.0
        "reasoning": "General clinical reasoning explaining why this primary disease is the most likely conclusion based on the vitals, symptoms, and history.",
        "confirmatory_symptoms": ["Symptom to ask about 1", "Physical exam check 2"],
        "prescribing_alerts": ["Warning: Do not prescribe X due to Allergy Y", "Note: Patient has asthma, avoid Z"],
        "differentials": [
            {{"disease": "Alternative 1", "reasoning": "Why it might be this..."}},
            {{"disease": "Alternative 2", "reasoning": "..."}}
        ],
        "recommended_tests": ["Complete Blood Count (CBC)", "Chest X-Ray"]
    }}
    """

    # 3. Call the Gemini Model
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"} # Forces valid JSON output
    )
    
    response = model.generate_content(prompt)
    
    # 4. Parse and return the JSON dictionary
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        raise ValueError("AI failed to return valid JSON.")
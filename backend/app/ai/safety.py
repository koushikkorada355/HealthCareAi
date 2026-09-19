BANNED = ["diagnos", "prescrib", "you have ", "you likely have", "take ", "dosage", "treatment plan", "medication"]
def check_admin_only(text: str) -> tuple[bool, str]:
    low = (text or "").lower()
    for b in ["diagnose", "prescribe", "dosage", "take ibuprofen", "you have cancer", "you have a heart"]:
        if b in low: return False, "I can help with appointments and admin tasks, but I can't provide diagnosis or prescriptions. I've noted what you reported for the care team."
    return True, ""
def reflect_reported(text: str) -> str:
    return text  # always echo as patient-reported, never conclude

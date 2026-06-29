# feedback/salinity_feedback.py


def classify_salinity(I_M):
    """
    Convert ionic strength into BioLoop environmental feedback.

    Controls:
        red/yellow/green/blue/white LEDs
    """

    if I_M > 0.50:
        return {
            "level": "plasmolysis_risk",
            "led": "red",
            "status": "Plasmolysis-risk hypertonic condition",
            "action": "dilute_or_replace_media",
        }

    elif I_M >= 0.20:
        return {
            "level": "hypertonic_suboptimal",
            "led": "yellow",
            "status": "Hypertonic suboptimal growth condition",
            "action": "dilute_media",
        }

    elif I_M >= 0.08:
        return {
            "level": "optimal_growth_range",
            "led": "green",
            "status": "Optimal ionic growth condition",
            "action": "maintain_conditions",
        }

    elif I_M >= 0.01:
        return {
            "level": "hypotonic_suboptimal",
            "led": "blue",
            "status": "Hypotonic suboptimal growth condition",
            "action": "increase_media_strength",
        }

    else:
        return {
            "level": "severe_hypotonic_stress",
            "led": "white",
            "status": "Severe hypotonic condition / lysis risk",
            "action": "replace_media",
        }
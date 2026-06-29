# feedback/fault_feedback.py

def diagnose_fault(result):
    """
    Diagnose BioLoop measurement/system problems.

    Controls ONLY the dedicated red fault LED.

    Fault LED meanings:
        off         = system OK
        solid       = questionable measurement
        slow blink  = noisy EIS / rerun
        pulse       = possible electrode/model drift
        fast blink  = serious fault / intervention needed
    """

    Rs_sd = result.get("Rs_sd_ohm", None)

    empirical_error = result.get(
        "empirical_error_percent",
        None,
    )

    grounded_error = result.get(
        "grounded_error_percent",
        None,
    )

    decision = result.get(
        "decision",
        "REVIEW",
    )


    if decision == "ACCEPT":
        return {
            "fault_level": "none",
            "fault_led": "off",
            "message": "System OK",
            "action": "continue",
        }


    if Rs_sd is None:
        return {
            "fault_level": "scan_failed",
            "fault_led": "fast_blink",
            "message": "No EIS data received",
            "action": "restart_emstat",
        }


    if Rs_sd > 2.5:
        return {
            "fault_level": "unstable_signal",
            "fault_led": "slow_blink",
            "message": "High EIS variability",
            "action": "rerun_scan_check_bubbles",
        }


    if empirical_error is not None and abs(empirical_error) > 30:
        return {
            "fault_level": "empirical_model_drift",
            "fault_led": "pulse",
            "message": "Measurement far from empirical model",
            "action": "recheck_standard_or_recalibrate",
        }


    if grounded_error is not None and abs(grounded_error) > 60:
        return {
            "fault_level": "physical_reference_drift",
            "fault_led": "pulse",
            "message": "Measurement far from grounded reference",
            "action": "check_electrode_wetting_fouling_or_Kcell",
        }


    return {
        "fault_level": "review",
        "fault_led": "solid",
        "message": "Measurement requires review",
        "action": "inspect_data",
    }
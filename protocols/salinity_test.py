# protocols/salinity_test.py

from electrochem.eis import PalmSens
from electrochem.quality_gate import evaluate_measurement
from electrochem.salinity_model import (
    solve_I_from_Rs,
    plot_advanced_model_update,
)
from electrochem.calibration import save_calibration_point

from feedback.salinity_feedback import classify_salinity
from feedback.fault_feedback import diagnose_fault
from utils.logger import log_result
from config.settings import CALIBRATION
from electrochem.kcell_calibration import save_kcell_calibration, get_latest_kcell



def run_salinity_demo(
    system,
    mode="known",
    expected_I=None,
    n_scans=3,
    sample_name=None,
    simulate=False,
):
    valves = system["valves"]
    leds = system["leds"]

    print("=== BioLoop Demo 1 ===")
    print(f"Mode: {mode}")

    if sample_name is None:
        if mode == "calibrate" and expected_I is not None:
            sample_name = f"NaCl_{expected_I:.3f}M"
        elif mode == "kcell":
            sample_name = CALIBRATION["standard_name"]
        elif mode == "predict":
            sample_name = "unknown_prediction"
        else:
            sample_name = "sample"

    pot = PalmSens(simulate=simulate)
    pot.connect()

    run_metadata = {
        "mode": mode,
        "sample_name": sample_name,
        "known_I": expected_I,
    }

    eis = pot.run_batch(
        n_scans=n_scans,
        metadata=run_metadata,
    )

    Rs_mean = eis["Rs_mean"]
    Rs_sd = eis["Rs_sd"]

    if mode == "known":
        if expected_I is None:
            raise ValueError("known mode requires expected_I")
        I_value = expected_I
        predicted_I = None

    elif mode == "predict":
        try:
            I_value = solve_I_from_Rs(Rs_mean)
            prediction_valid = True
            prediction_note = ""

        except ValueError as exc:
            I_value = float("nan")
            prediction_valid = False
            prediction_note = str(exc)

            print("\nSalinity prediction unavailable.")
            print("The measured Rs is outside the calibrated model range.")
            print(prediction_note)
        predicted_I = I_value

    elif mode == "calibrate":
        if expected_I is None:
            raise ValueError("calibrate mode requires expected_I")
        I_value = expected_I

        try:
            predicted_I = solve_I_from_Rs(Rs_mean)
        except ValueError: 
            predicted_I = None
            print("Prediction failed: Rs is outside model-solvable range.")


    elif mode == "kcell":
        if CALIBRATION["standard_kappa_S_cm"] is None:
            raise ValueError("kcell mode requires CALIBRATION['standard_kappa_S_cm']")
        I_value = expected_I if expected_I is not None else CALIBRATION["standard_I_M"]
        
        try:
            predicted_I = solve_I_from_Rs(Rs_mean)
        except ValueError:
            predicted_I = None
            print("Prediction failed: Rs is outside model-solvable range.")

    else:
        raise ValueError(f"Unknown mode: {mode}")

    quality = evaluate_measurement(
        I_expected=I_value if mode in ["known", "calibrate", "kcell"] else None,
        Rs_mean=Rs_mean,
        Rs_sd=Rs_sd,
    )

    quality_recommendation = quality["decision"]
    accepted = quality_recommendation == "ACCEPT"
    Kcell = None

    if mode == "calibrate":
        print("\n=== Calibration Review ===")
        print(f"Recommendation: {quality_recommendation}")

        if quality.get("notes"):
            print("\nNotes:")
            for note in quality["notes"]:
                print(f" - {note}")

        response = input(
            "\nAccept this calibration point? (y/n): "
        ).strip().lower()

        accepted = response in ["y", "yes"]

        if accepted:
            save_calibration_point(
                Rs_mean=Rs_mean,
                Rs_sd=Rs_sd,
                I_known=expected_I,
                empirical_error=None,
                grounded_error=quality.get("grounded_error_percent"),
                sample_name=sample_name,
                source="user_accepted",
                recommendation=quality_recommendation,
                accepted=True,
                Kcell_at_time=get_latest_kcell(),
            )
            print("Calibration point saved.")
        else:
            print("Calibration point NOT saved.")

    if mode == "kcell":
        print("\n=== K-cell Calibration Review ===")
        print(f"Recommendation: {quality_recommendation}")

        if quality.get("notes"):
            print("\nNotes:")
            for note in quality["notes"]:
                print(f" - {note}")

        response = input(
            "\nAccept this K-cell calibration? (y/n): "
        ).strip().lower()

        accepted = response in ["y", "yes"]

        Kcell = save_kcell_calibration(
            Rs_mean=Rs_mean,
            Rs_sd=Rs_sd,
            kappa_standard=CALIBRATION["standard_kappa_S_cm"],
            standard_name=CALIBRATION["standard_name"],
            accepted=accepted,
        )

        print("Kcell:", Kcell)

    plot_advanced_model_update(
        latest_I=I_value,
        latest_Rs=Rs_mean,
        latest_Rs_sd=Rs_sd,
        mode=mode,
        accepted=accepted,
        sample_name=sample_name,
    )

    salinity = classify_salinity(I_value)
    fault = diagnose_fault(quality)

    print("Rs mean:", Rs_mean)
    print("Rs SD:", Rs_sd)
    print("Known/used ionic strength:", I_value)
    print("Predicted ionic strength:", predicted_I)
    print("Salinity:", salinity["status"])
    print("Quality recommendation:", quality_recommendation)
    print("Final accepted:", accepted)
    print("Fault:", fault["message"])

    leds.show_salinity(salinity["led"])
    leds.show_fault(fault)

    if accepted:
        valves.open("sample")
    else:
        valves.release_all()

    log_row = {
        **eis,
        **quality,
        "mode": mode,
        "sample_name": sample_name,
        "known_I": expected_I if mode in ["known", "calibrate", "kcell"] else None,
        "predicted_I": predicted_I,
        "I_value": I_value,
        "quality_recommendation": quality_recommendation,
        "accepted": accepted,
        "salinity_level": salinity["level"],
        "salinity_led": salinity["led"],
        "salinity_status": salinity["status"],
        "fault_level": fault["fault_level"],
        "fault_led": fault["fault_led"],
        "fault_message": fault["message"],
    }

    if Kcell is not None:
        log_row["Kcell"] = Kcell

    log_result(log_row)

    return log_row
import numpy as np
from electrochem.salinity_model import corrected_kohlrausch, predict_kappa_grounded


def test_corrected_kohlrausch_shape():
    I = np.array([0.001, 0.01, 0.1])
    vals = corrected_kohlrausch(I)
    assert vals.shape == I.shape


def test_predict_kappa_grounded_nonnegative():
    kappa = predict_kappa_grounded(0.01)
    assert kappa >= 0

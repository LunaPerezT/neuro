"""Checks of the closed-form HOI estimators. Run: python -m pytest -q tests"""
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hoi_metrics as H  # noqa: E402


def gauss_entropy(C):
    return 0.5 * np.linalg.slogdet(2 * np.pi * np.e * C)[1]


def oinfo_direct(X):
    """O-information from entropies of the sample covariance (definition, Rosas 2019), bits."""
    C = np.cov(X, rowvar=False)
    n = C.shape[0]
    h = gauss_entropy(C)
    o = (n - 2) * h
    for i in range(n):
        rest = [k for k in range(n) if k != i]
        o += gauss_entropy(C[[i]][:, [i]]) - gauss_entropy(C[np.ix_(rest, rest)])
    return o / np.log(2)


def test_moebius_matrix_matches_reference_layout():
    ref = np.array([
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0], [1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
        [1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0], [1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0],
        [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0], [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], [1] * 16])
    assert np.array_equal(H.knowns_to_atoms_matrix(), ref)


def test_triplet_closed_form_equals_definition():
    rng = np.random.default_rng(0)
    N, T = 12, 400
    Z = rng.standard_normal((T, 4)) 
    X = Z[:, rng.integers(0, 4, N)] + rng.standard_normal((T, N))   # shared latent sources -> redundancy
    X[:, 0] = X[:, 1] + X[:, 2] + 0.3 * rng.standard_normal(T)      # a sum -> synergy candidates
    Xs = H.zscore(X)
    R = H.corr(Xs)
    res = H.triplet_oinfo(R, None, np.array(list("aabbccddeeff")), top_k=10_000, keep_all=True)
    vals = res["all_triplet_oinfo"].astype(float)
    trip = list(itertools.combinations(range(N), 3))
    direct = np.array([oinfo_direct(Xs[:, list(t)]) for t in trip])
    # float16 storage -> compare with tolerance
    assert np.allclose(vals, direct, atol=2e-3)
    # n-plet closed form equals definition too
    for idx in ([0, 1, 2, 3], list(range(8))):
        o, s = H.nplet_info(R, idx)
        assert np.isclose(o, oinfo_direct(Xs[:, idx]), atol=1e-8)


def test_signs_synergy_and_redundancy():
    rng = np.random.default_rng(1)
    T = 5000
    # redundancy: three noisy copies of one source -> O > 0
    s = rng.standard_normal(T)
    Xr = np.c_[s, s, s] + 0.5 * rng.standard_normal((T, 3))
    # synergy: X3 = X1 + X2 with X1, X2 independent -> O < 0
    a, b = rng.standard_normal((2, T))
    Xs = np.c_[a, b, a + b + 0.3 * rng.standard_normal(T)]
    assert H.nplet_info(H.corr(Xr), [0, 1, 2])[0] > 0.3
    assert H.nplet_info(H.corr(Xs), [0, 1, 2])[0] < -0.3


def test_bias_correction_shrinks_null_oinfo():
    rng = np.random.default_rng(2)
    T, n = 100, 20
    raw, cor = [], []
    for _ in range(200):
        R = H.corr(rng.standard_normal((T, n)))
        raw.append(H.nplet_info(R, list(range(n)))[0])
        cor.append(H.nplet_info(R, list(range(n)), T)[0])
    assert abs(np.mean(cor)) < abs(np.mean(raw))


def test_phiid_matches_phyid_reference():
    phyid = __import__("pytest").importorskip("phyid.calculate")
    rng = np.random.default_rng(3)
    T, N = 1500, 5
    X = np.zeros((T, N))
    W = 0.4 * rng.standard_normal((N, N)) / np.sqrt(N)
    for t in range(1, T):                                   # coupled VAR(1)
        X[t] = X[t - 1] @ W + rng.standard_normal(N)
    mine = H.phiid_pairs(X, tau=1)
    for i, j in [(0, 1), (2, 4), (3, 1)]:
        atoms, _ = phyid.calc_PhiID(X[:, i], X[:, j], tau=1, kind="gaussian", redundancy="MMI")
        for name in ("sts", "rtr", "xtx", "xty", "ytx", "str"):
            ref = np.mean(atoms[name]) / np.log(2)
            assert np.isclose(mine[name][i, j], ref, atol=5e-3), (i, j, name, mine[name][i, j], ref)


def test_phiid_censoring_and_symmetry():
    rng = np.random.default_rng(4)
    X = rng.standard_normal((300, 6))
    valid = rng.random(300) > 0.2
    out = H.phiid_pairs(X, 1, valid)
    assert out["n_samples"] == int((valid[:-1] & valid[1:]).sum())
    assert np.allclose(out["sts"], out["sts"].T) and np.allclose(out["rtr"], out["rtr"].T)
    assert np.allclose(out["xty"], out["ytx"].T)


def test_subject_metrics_runs_on_realistic_size():
    rng = np.random.default_rng(5)
    T, N = 150, 60
    lat = rng.standard_normal((T, 7))
    X = lat[:, rng.integers(0, 7, N)] + rng.standard_normal((T, N))
    nets = np.array([f"net{k % 7}" for k in range(N)])
    valid = np.ones(T, bool); valid[40:48] = False
    res = H.subject_metrics(X, valid, nets, matched_T=120)
    s = H.scalar_summary(res)
    assert res["fc"].shape == (N, N) and res["phiid_sts"].shape == (N, N)
    assert res["tri_n_triplets"] == N * (N - 1) * (N - 2) // 6
    assert res["n_valid"] == T - 8 and s["matched_T"] == 120
    assert np.isfinite(res["tri_node_oinfo"]).all()

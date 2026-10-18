"""Higher-order interaction (HOI) metrics for parcellated rs-fMRI, Gaussian estimators in closed form.

Everything here is a function of (lagged) correlation matrices, so whole-brain metrics for ~450 regions take
seconds on a laptop. Units are bits.

Implemented
-----------
* Static functional connectivity (Pearson).
* O-information (Rosas et al. 2019) and S-information for every triplet of regions:
      O(i,j,k) = 1/2 log|R_ijk| - 1/2 sum_{pairs} log(1 - r^2)      (O < 0: synergy-dominated, O > 0: redundancy)
  summarised per region, per network triplet, plus the most extreme triplets.
* O- and S-information of whole networks (n-plets), via
      O(S) = -log|R_S| - 1/2 sum_i log (R_S^-1)_ii ,   S(S) = 1/2 sum_i log (R_S^-1)_ii
* Integrated Information Decomposition, PhiID-MMI (Mediano et al. 2021; Luppi et al. 2022) for every pair of
  regions with lag 1: the 16 atoms, of which synergy (sts) and redundancy (rtr) are saved as region x region
  matrices. Validated against the reference implementation `phyid` in tests/.

Bias: Gaussian entropy estimates are biased for finite T; the analytic correction of Ince et al. 2017 (gcmi) is
applied to O/S-information. It assumes independent samples, so subjects should also be compared at matched T.
"""
from __future__ import annotations

import numpy as np
from scipy.special import psi

LN2 = np.log(2.0)

# PhiID atoms in the order used by phyid: source lattice node -> target lattice node
# r = redundant {1}{2}, x = unique to region 1, y = unique to region 2, s = synergistic {12}
NODES = ["r", "x", "y", "s"]
ATOMS = [a + "t" + b for a in NODES for b in NODES]
_DOWN = {"r": {"r"}, "1": {"r", "x"}, "2": {"r", "y"}, "12": {"r", "x", "y", "s"}}
# knowns, each = sum of atoms (i -> j) with i in down(source set) and j in down(target set); ("r" = redundancy)
KNOWNS = [("r", "r"),                                   # double redundancy (MMI)
          ("r", "1"), ("r", "2"), ("r", "12"),          # redundancy of the two pasts about future a, b, ab
          ("1", "r"), ("2", "r"), ("12", "r"),          # redundancy of the two futures given past x, y, xy
          ("1", "1"), ("1", "2"), ("2", "1"), ("2", "2"),
          ("12", "1"), ("12", "2"), ("1", "12"), ("2", "12"), ("12", "12")]


def knowns_to_atoms_matrix() -> np.ndarray:
    """16x16 Moebius matrix of the PhiID product lattice, built from down-sets (not copied)."""
    M = np.zeros((16, 16))
    for row, (src, trg) in enumerate(KNOWNS):
        for col, atom in enumerate(ATOMS):
            if atom[0] in _DOWN[src] and atom[2] in _DOWN[trg]:
                M[row, col] = 1
    return M


_M_INV = np.linalg.inv(knowns_to_atoms_matrix())


# ----------------------------------------------------------------------------------------------- helpers
def zscore(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, float)
    sd = X.std(0, ddof=1)
    sd[sd == 0] = 1
    return (X - X.mean(0)) / sd


def copula_normalize(X: np.ndarray) -> np.ndarray:
    """Gaussian-copula transform per column (rank -> standard normal), as in Ince et al. 2017."""
    from scipy.stats import norm, rankdata
    X = np.asarray(X, float)
    U = rankdata(X, axis=0) / (X.shape[0] + 1)
    return norm.ppf(U)


def corr(X: np.ndarray) -> np.ndarray:
    R = np.clip(np.corrcoef(X, rowvar=False), -0.999999, 0.999999)
    np.fill_diagonal(R, 1.0)
    return R


def entropy_bias(d: int, T: int) -> float:
    """Bias (nats) of the plug-in Gaussian entropy of d variables from T samples (gcmi ent_g)."""
    dterm = (np.log(2.0) - np.log(T - 1.0)) / 2.0
    return d * dterm + psi((T - np.arange(1, d + 1)) / 2.0).sum() / 2.0


def oinfo_bias(n: int, T: int) -> float:
    """Bias (nats) of plug-in O-information for an n-plet:  (n-2) b(n) + n b(1) - n b(n-1)."""
    return (n - 2) * entropy_bias(n, T) + n * entropy_bias(1, T) - n * entropy_bias(n - 1, T)


def sinfo_bias(n: int, T: int) -> float:
    """Bias (nats) of plug-in S-information: S = TC + DTC = sum_i H(X_i) - n H(X) + sum_i H(X_-i)."""
    return n * entropy_bias(1, T) - n * entropy_bias(n, T) + n * entropy_bias(n - 1, T)


# ----------------------------------------------------------------------------------------------- O-information
def nplet_info(R: np.ndarray, idx, T: int | None = None) -> tuple[float, float]:
    """O- and S-information (bits) of the variables idx, from their correlation matrix."""
    S = R[np.ix_(idx, idx)]
    n = len(idx)
    sign, logdet = np.linalg.slogdet(S)
    inv_diag = np.diag(np.linalg.inv(S))
    o = -logdet - 0.5 * np.log(inv_diag).sum()
    s = 0.5 * np.log(inv_diag).sum()
    if T is not None:
        o -= oinfo_bias(n, T)
        s -= sinfo_bias(n, T)
    return o / LN2, s / LN2


def triplet_oinfo(R: np.ndarray, T: int | None = None, labels_net: np.ndarray | None = None,
                  top_k: int = 2000, keep_all: bool = False) -> dict:
    """O- and S-information of every triplet i<j<k, summarised.

    Returns per-region mean O and S over the triplets containing the region, mean O per network triplet
    (unordered, with repetition), global distribution summaries and the top_k most synergistic and redundant
    triplets. keep_all=True also returns every triplet's O as float16 (N=450: 15.1 M values, 30 MB).
    """
    N = R.shape[0]
    with np.errstate(divide="ignore"):
        L2 = np.log(1 - R ** 2)                   # log(1 - r^2) for all pairs (diagonal unused)
    bias_o = oinfo_bias(3, T) if T else 0.0
    bias_s = sinfo_bias(3, T) if T else 0.0
    node_o = np.zeros(N); node_s = np.zeros(N); node_n = np.zeros(N)
    if labels_net is not None:
        nets, net_id = np.unique(labels_net, return_inverse=True)
        K = len(nets)
        cls_sum = np.zeros((K, K, K)); cls_n = np.zeros((K, K, K)); cls_syn = np.zeros((K, K, K))
    hist_edges = np.linspace(-0.5, 0.5, 201)
    hist = np.zeros(len(hist_edges) - 1)
    tot = tot2 = 0.0; n_tot = 0; n_syn = 0
    syn_best = (np.empty(0), np.empty((0, 3), int)); red_best = (np.empty(0), np.empty((0, 3), int))
    all_o = [] if keep_all else None
    for i in range(N - 2):
        j, k = np.triu_indices(N - i - 1, 1)
        j += i + 1; k += i + 1
        a, b, c = R[i, j], R[i, k], R[j, k]
        det3 = 1 - a * a - b * b - c * c + 2 * a * b * c
        sumL = L2[i, j] + L2[i, k] + L2[j, k]
        o = (0.5 * np.log(det3) - 0.5 * sumL - bias_o) / LN2
        # S = 1/2 sum_i log (R^-1)_ii ; (R^-1)_ii = (1 - r_jk^2)/det3
        s = (0.5 * (sumL - 3 * np.log(det3)) - bias_s) / LN2
        node_o[i] += o.sum(); node_s[i] += s.sum(); node_n[i] += len(o)
        node_o += np.bincount(j, o, N) + np.bincount(k, o, N)
        node_s += np.bincount(j, s, N) + np.bincount(k, s, N)
        node_n += np.bincount(j, None, N) + np.bincount(k, None, N)
        tot += o.sum(); tot2 += (o * o).sum(); n_tot += len(o); n_syn += int((o < 0).sum())
        hist += np.histogram(np.clip(o, -0.4999, 0.4999), hist_edges)[0]
        if labels_net is not None:
            t = np.sort(np.stack([np.full_like(j, net_id[i]), net_id[j], net_id[k]]), axis=0)
            flat = np.ravel_multi_index(t, (K, K, K))
            cls_sum += np.bincount(flat, o, K ** 3).reshape(K, K, K)
            cls_n += np.bincount(flat, None, K ** 3).reshape(K, K, K)
            cls_syn += np.bincount(flat, (o < 0).astype(float), K ** 3).reshape(K, K, K)
        trip = np.stack([np.full_like(j, i), j, k], 1)
        syn_best = _merge_top(syn_best, o, trip, top_k, smallest=True)
        red_best = _merge_top(red_best, o, trip, top_k, smallest=False)
        if keep_all:
            all_o.append(o.astype(np.float16))
    out = {
        "node_oinfo": node_o / node_n, "node_sinfo": node_s / node_n,
        "oinfo_mean": tot / n_tot, "oinfo_sd": np.sqrt(tot2 / n_tot - (tot / n_tot) ** 2),
        "frac_synergistic": n_syn / n_tot, "n_triplets": n_tot,
        "oinfo_hist": hist, "oinfo_hist_edges": hist_edges,
        "top_synergy_value": syn_best[0], "top_synergy_triplets": syn_best[1],
        "top_redundancy_value": red_best[0], "top_redundancy_triplets": red_best[1],
    }
    if labels_net is not None:
        with np.errstate(invalid="ignore"):
            out["net_triplet_oinfo"] = cls_sum / cls_n
            out["net_triplet_frac_syn"] = cls_syn / cls_n
        out["networks"] = nets
    if keep_all:
        out["all_triplet_oinfo"] = np.concatenate(all_o)
    return out


def _merge_top(best, vals, trip, k, smallest):
    v = np.concatenate([best[0], vals]); t = np.concatenate([best[1], trip])
    if len(v) > k:
        sel = np.argpartition(v if smallest else -v, k)[:k]
        v, t = v[sel], t[sel]
    return v, t


def network_info(R: np.ndarray, labels_net: np.ndarray, T: int | None = None) -> dict:
    """O/S-information of each network and of each pair of networks (union) as n-plets."""
    nets = np.unique(labels_net)
    K = len(nets)
    O = np.full((K, K), np.nan); S = np.full((K, K), np.nan)
    for a in range(K):
        for b in range(a, K):
            idx = np.where((labels_net == nets[a]) | (labels_net == nets[b]))[0]
            if T is not None and len(idx) >= T - 2:
                continue  # covariance not estimable
            O[a, b], S[a, b] = O[b, a], S[b, a] = nplet_info(R, idx, T)
    return {"networks": nets, "net_oinfo": O, "net_sinfo": S}


# ----------------------------------------------------------------------------------------------- PhiID
def _gauss_mi(C, a, b):
    """MI (nats) between variable sets a and b for a batch of covariance matrices C (P, d, d)."""
    ab = a + b
    _, la = np.linalg.slogdet(C[:, a][:, :, a])
    _, lb = np.linalg.slogdet(C[:, b][:, :, b])
    _, lab = np.linalg.slogdet(C[:, ab][:, :, ab])
    return 0.5 * (la + lb - lab)


def phiid_pairs(X: np.ndarray, tau: int = 1, valid: np.ndarray | None = None, pairs=None,
                chunk: int = 20000) -> dict:
    """PhiID-MMI atoms (bits) for region pairs, Gaussian, lag tau.

    X: (T, N) time series. valid: boolean (T,) frames kept after censoring; a lagged sample (t, t+tau) is
    used only if both frames are valid. Returns dict atom -> (N, N) symmetric matrix (synergy 'sts' and
    redundancy 'rtr' are the usual summaries), plus 'n_samples'.
    """
    X = np.asarray(X, float)
    T, N = X.shape
    ok = np.ones(T - tau, bool) if valid is None else (valid[:-tau] & valid[tau:])
    P_, F_ = X[:-tau][ok], X[tau:][ok]
    P_ = zscore(P_); F_ = zscore(F_)
    n = len(P_)
    A = P_.T @ P_ / (n - 1)          # past-past
    B = F_.T @ F_ / (n - 1)          # future-future
    L = P_.T @ F_ / (n - 1)          # past_i -> future_j
    if pairs is None:
        pairs = np.stack(np.triu_indices(N, 1), 1)
    out = {a: np.zeros((N, N)) for a in ATOMS}
    for s in range(0, len(pairs), chunk):
        i, j = pairs[s:s + chunk, 0], pairs[s:s + chunk, 1]
        C = np.empty((len(i), 4, 4))
        # variable order: x_past, y_past, x_future (a), y_future (b)
        C[:, 0, 0] = A[i, i]; C[:, 1, 1] = A[j, j]; C[:, 2, 2] = B[i, i]; C[:, 3, 3] = B[j, j]
        C[:, 0, 1] = C[:, 1, 0] = A[i, j]
        C[:, 2, 3] = C[:, 3, 2] = B[i, j]
        C[:, 0, 2] = C[:, 2, 0] = L[i, i]
        C[:, 0, 3] = C[:, 3, 0] = L[i, j]
        C[:, 1, 2] = C[:, 2, 1] = L[j, i]
        C[:, 1, 3] = C[:, 3, 1] = L[j, j]
        x, y, ta, tb = [0], [1], [2], [3]
        I = {
            "xta": _gauss_mi(C, x, ta), "xtb": _gauss_mi(C, x, tb), "yta": _gauss_mi(C, y, ta), "ytb": _gauss_mi(C, y, tb),
            "xyta": _gauss_mi(C, x + y, ta), "xytb": _gauss_mi(C, x + y, tb), "xtab": _gauss_mi(C, x, ta + tb),
            "ytab": _gauss_mi(C, y, ta + tb), "xytab": _gauss_mi(C, x + y, ta + tb),
        }
        mmi = np.minimum
        knowns = np.stack([
            mmi(mmi(I["xta"], I["xtb"]), mmi(I["yta"], I["ytb"])),          # rtr (MMI double redundancy)
            mmi(I["xta"], I["yta"]), mmi(I["xtb"], I["ytb"]), mmi(I["xtab"], I["ytab"]),
            mmi(I["xta"], I["xtb"]), mmi(I["yta"], I["ytb"]), mmi(I["xyta"], I["xytb"]),
            I["xta"], I["xtb"], I["yta"], I["ytb"], I["xyta"], I["xytb"], I["xtab"], I["ytab"], I["xytab"],
        ])
        atoms = _M_INV @ knowns / LN2
        for a_i, name in enumerate(ATOMS):
            out[name][i, j] = atoms[a_i]
            # the swapped pair gives the mirrored atom (x<->y); store the mirrored name for j,i
            out[_mirror(name)][j, i] = atoms[a_i]
    out["n_samples"] = n
    return out


def _mirror(atom: str) -> str:
    sw = {"r": "r", "s": "s", "x": "y", "y": "x"}
    return sw[atom[0]] + "t" + sw[atom[2]]


# ----------------------------------------------------------------------------------------------- per-subject driver
def subject_metrics(X: np.ndarray, valid: np.ndarray | None, labels_net: np.ndarray, matched_T: int | None = 120,
                    copula: bool = True, top_k: int = 2000) -> dict:
    """All metrics for one subject. X: (T, N) denoised series at the common TR; valid: frames kept."""
    valid = np.ones(len(X), bool) if valid is None else valid.astype(bool)
    Xv = X[valid]
    Z = copula_normalize(Xv) if copula else zscore(Xv)
    R = corr(Z)
    T = len(Z)
    res = {"fc": R.astype(np.float32), "n_frames": len(X), "n_valid": T}
    tri = triplet_oinfo(R, T, labels_net, top_k=top_k)
    res.update({f"tri_{k}": v for k, v in tri.items()})
    res.update({f"net_{k}": v for k, v in network_info(R, labels_net, T).items() if k != "networks"})
    Xc = copula_normalize(X) if copula else X     # PhiID needs the time order; censored pairs are skipped
    ph = phiid_pairs(Xc, 1, valid)
    res["phiid_sts"] = ph["sts"].astype(np.float32)
    res["phiid_rtr"] = ph["rtr"].astype(np.float32)
    res["phiid_n_samples"] = ph["n_samples"]
    # synergy-redundancy gradient (Luppi et al. 2022): rank of nodal synergy minus rank of nodal redundancy
    syn = ph["sts"].sum(1); red = ph["rtr"].sum(1)
    res["node_phiid_synergy"] = syn; res["node_phiid_redundancy"] = red
    res["node_syn_red_gradient"] = (np.argsort(np.argsort(syn)) - np.argsort(np.argsort(red))).astype(np.int16)
    if matched_T and T >= matched_T:
        Rm = corr(Z[:matched_T])
        trim = triplet_oinfo(Rm, matched_T, labels_net, top_k=10)
        res["matchedT_tri_oinfo_mean"] = trim["oinfo_mean"]
        res["matchedT_tri_frac_synergistic"] = trim["frac_synergistic"]
        res["matchedT_node_oinfo"] = trim["node_oinfo"]
        res["matchedT_net_triplet_oinfo"] = trim["net_triplet_oinfo"]
    res["matched_T"] = matched_T if matched_T and T >= matched_T else 0
    return res


def scalar_summary(res: dict) -> dict:
    """One-row summary for the group table."""
    out = {k: res[k] for k in ("n_frames", "n_valid", "phiid_n_samples", "tri_oinfo_mean", "tri_oinfo_sd",
                               "tri_frac_synergistic", "matched_T") if k in res}
    iu = np.triu_indices_from(res["fc"], 1)
    out["fc_mean"] = float(np.mean(res["fc"][iu]))
    out["phiid_synergy_mean"] = float(np.mean(res["phiid_sts"][iu]))
    out["phiid_redundancy_mean"] = float(np.mean(res["phiid_rtr"][iu]))
    for k in ("matchedT_tri_oinfo_mean", "matchedT_tri_frac_synergistic"):
        if k in res:
            out[k] = res[k]
    return out

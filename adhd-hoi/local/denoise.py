"""Parcellation, denoising, censoring and TR harmonisation of rs-fMRI.

Atlas (450 regions, identical labels in every dataset):
  Schaefer-400 (7 networks) cortex + Tian S3 subcortex (50).
  * Volume data (fMRIPrep on brainlife, MNI152NLin6Asym 2 mm): FSL-MNI 2 mm versions of both atlases.
  * GRMPY: XCP-D series already parcellated with the same atlases in fsLR (4S456 first 400 columns + Tian).

Denoising mirrors XCP-D "linc" mode used for GRMPY: 36 parameters (6 motion + WM + CSF + global, their
derivatives, squares and squared derivatives) regressed together with a 0.01-0.08 Hz Butterworth band-pass
applied to signal and confounds, no censoring during regression. Linear operations commute with region
averaging, so cleaning parcel means equals cleaning voxels then averaging (despiking is the one XCP-D step not
reproduced). Censoring (FD > threshold) is applied afterwards, identically for every dataset.
"""
from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.signal import resample_poly

from common import download

SCHAEFER = ("https://raw.githubusercontent.com/ThomasYeoLab/CBIG/master/stable_projects/brain_parcellation/"
            "Schaefer2018_LocalGlobal/Parcellations/MNI/")
TIAN = "https://raw.githubusercontent.com/yetianmed/subcortex/master/Group-Parcellation/3T/Subcortex-Only/"
ATLAS_FILES = {
    "schaefer_img": SCHAEFER + "Schaefer2018_400Parcels_7Networks_order_FSLMNI152_2mm.nii.gz",
    "schaefer_lut": SCHAEFER + "freeview_lut/Schaefer2018_400Parcels_7Networks_order.txt",
    "tian_img": TIAN + "Tian_Subcortex_S3_3T.nii",
    "tian_lut": TIAN + "Tian_Subcortex_S3_3T_label.txt",
}
CONF36 = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z", "white_matter", "csf", "global_signal"]


# ----------------------------------------------------------------------------------------------- atlas
def load_atlas(atlas_dir: Path):
    """Returns (label image array 91x109x91 with values 1..450, affine, labels list, network per region)."""
    p = {k: download(u, atlas_dir / Path(u).name) for k, u in ATLAS_FILES.items()}
    sch = nib.load(p["schaefer_img"]); tian = nib.load(p["tian_img"])
    assert np.allclose(sch.affine, tian.affine) and sch.shape == tian.shape
    a = np.asarray(sch.dataobj).astype(np.int32)
    t = np.asarray(tian.dataobj).astype(np.int32)
    a[t > 0] = 400 + t[t > 0]
    s_labels = [ln.split()[1].replace("7Networks_", "") for ln in p["schaefer_lut"].read_text().splitlines() if ln.strip()]
    t_labels = [ln.strip() for ln in p["tian_lut"].read_text().splitlines() if ln.strip()]
    assert len(s_labels) == 400 and len(t_labels) == 50
    labels = s_labels + t_labels
    return a, sch.affine, labels, networks(labels)


def networks(labels):
    """Yeo-7 network of each Schaefer label ('LH_Vis_1' -> 'Vis'); Tian regions -> 'Subcortex'."""
    out = []
    for lab in labels:
        m = re.match(r"(?:7Networks_)?[LR]H_([A-Za-z]+)_", lab)
        out.append(m.group(1) if m else "Subcortex")
    return np.array(out)


# ----------------------------------------------------------------------------------------------- volume data
def parcellate(bold_path: Path, mask_path: Path | None, atlas: np.ndarray, affine, min_coverage=0.5):
    """Mean signal per region (T x 450). Regions with < min_coverage of voxels inside the brain mask -> NaN."""
    img = nib.load(str(bold_path))
    if img.shape[:3] != atlas.shape or not np.allclose(img.affine, affine, atol=1e-3):
        raise ValueError(f"BOLD grid {img.shape[:3]} does not match the 2 mm MNI152NLin6Asym atlas grid")
    lab = atlas.ravel()
    inmask = np.ones_like(lab, bool) if mask_path is None else (np.asarray(nib.load(str(mask_path)).dataobj).ravel() > 0)
    vox = np.where(lab > 0)[0]
    data = np.asarray(img.dataobj, dtype=np.float32).reshape(-1, img.shape[3])[vox]      # V x T
    good = inmask[vox] & np.isfinite(data).all(1) & (data.std(1) > 0)
    n_all = np.bincount(lab[vox], minlength=451)[1:]
    n_ok = np.bincount(lab[vox][good], minlength=451)[1:]
    sums = np.zeros((450, data.shape[1]), np.float64)
    np.add.at(sums, lab[vox][good] - 1, data[good])
    with np.errstate(invalid="ignore", divide="ignore"):
        ts = (sums / n_ok[:, None]).T
    coverage = n_ok / np.maximum(n_all, 1)
    ts[:, coverage < min_coverage] = np.nan
    tr = float(img.header.get_zooms()[3]) if len(img.header.get_zooms()) > 3 else np.nan
    return ts.astype(np.float32), coverage, tr


def confounds_36p(regressors_tsv: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """36P matrix, framewise displacement and non-steady-state (dummy) frames from fMRIPrep confounds."""
    C = pd.read_csv(regressors_tsv, sep="\t")
    cols = []
    for b in CONF36:
        for suf in ("", "_derivative1", "_power2", "_derivative1_power2"):
            c = b + suf
            if c not in C:  # older fMRIPrep: build the expansion ourselves
                base = C[b].to_numpy(float)
                d = np.r_[0.0, np.diff(base)]
                C[c] = {"": base, "_derivative1": d, "_power2": base ** 2, "_derivative1_power2": d ** 2}[suf]
            cols.append(c)
    X = C[cols].fillna(0).to_numpy(float)
    fd = C["framewise_displacement"].fillna(0).to_numpy(float)
    dummy = np.zeros(len(C), bool)
    for c in C.columns:
        if c.startswith("non_steady_state_outlier"):
            dummy |= C[c].to_numpy() > 0
    return X, fd, dummy


def clean(ts: np.ndarray, conf: np.ndarray, tr: float, bandpass=(0.01, 0.08)) -> np.ndarray:
    """36P regression + Butterworth band-pass of parcel series (NaN regions kept as NaN)."""
    from nilearn.signal import clean as nclean
    out = np.full_like(ts, np.nan, dtype=np.float32)
    ok = np.isfinite(ts).all(0)
    out[:, ok] = nclean(ts[:, ok], confounds=conf, detrend=True, standardize="zscore_sample",
                        filter="butterworth", low_pass=bandpass[1], high_pass=bandpass[0], t_r=tr)
    return out


# ----------------------------------------------------------------------------------------------- XCP-D data (GRMPY)
def xcpd_series(seg4s456_tsv: Path, tian_tsv: Path, labels: list[str]) -> np.ndarray:
    """450-region series from XCP-D outputs, columns reordered to the common label order."""
    a = pd.read_csv(seg4s456_tsv, sep="\t")
    t = pd.read_csv(tian_tsv, sep="\t")
    cort = [c for c in a.columns if re.match(r"[LR]H_", c)][:400]
    if len(cort) != 400:
        raise ValueError("unexpected 4S456 columns")
    df = pd.concat([a[cort], t[[c for c in t.columns]]], axis=1)
    missing = [l for l in labels if l not in df.columns]
    if missing:
        raise ValueError(f"labels missing in XCP-D series: {missing[:5]}")
    return df[labels].to_numpy(np.float32)


def xcpd_fd(motion_tsv: Path) -> np.ndarray:
    M = pd.read_csv(motion_tsv, sep="\t")
    return M["framewise_displacement"].fillna(0).to_numpy(float)


# ----------------------------------------------------------------------------------------------- harmonisation
def censor_mask(fd: np.ndarray, thresh: float, dummy: np.ndarray | None = None) -> np.ndarray:
    valid = fd <= thresh
    if dummy is not None:
        valid &= ~dummy
    return valid


def to_common_tr(ts: np.ndarray, valid: np.ndarray, tr: float, new_tr: float):
    """Resample (polyphase, anti-aliased) to new_tr. A new frame is valid only if every original frame within
    its +-new_tr/2 window was valid. NaN regions stay NaN."""
    if abs(tr - new_tr) < 1e-6:
        return ts, valid
    ratio = Fraction(tr / new_tr).limit_denominator(50)        # up/down factors
    ok = np.isfinite(ts).all(0)
    out = np.full((int(np.floor(len(ts) * tr / new_tr)), ts.shape[1]), np.nan, np.float32)
    res = resample_poly(np.nan_to_num(ts[:, ok]), ratio.numerator, ratio.denominator, axis=0)
    out[:, ok] = res[: len(out)]
    t_old = np.arange(len(ts)) * tr
    t_new = np.arange(len(out)) * new_tr
    bad_times = t_old[~valid]
    nv = np.ones(len(out), bool)
    if len(bad_times):
        idx = np.searchsorted(bad_times, t_new - new_tr / 2)
        idx2 = np.searchsorted(bad_times, t_new + new_tr / 2)
        nv = idx2 == idx
    return out, nv

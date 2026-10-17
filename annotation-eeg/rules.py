"""Expert annotation rules: how each reviewed EEG dataset's participants are labelled.

Each rule says where the label comes from (a participants.tsv column, the group code in
subject ids, or the whole dataset) and maps raw values to a condition key in CONDITIONS.
Raw values are kept as `subgroup`, so nothing is lost. Healthy participants become
'control' when their dataset also has patients, otherwise 'healthy'.

Fields: cond (whole dataset), col + map (per participant), prefix + map (id code),
conf (high/medium/low), cohort (datasets sharing the same people), dup_of (exact duplicate,
excluded from counts), intervention (drug or procedure), flag (caution for users), note.
"""

# condition key -> human label (SNOMED CT codes are attached in conditions_snomed.json)
CONDITIONS = {
    "HEALTHY": "Healthy participant",
    "PRESUMED_HEALTHY": "No clinical label (non-clinical study)",
    "NOT_REPORTED": "Clinical status not reported",
    "PD": "Parkinson's disease",
    "COVID19": "COVID-19 (post-infection)",
    "EPILEPSY": "Epilepsy",
    "ICU": "Critically ill patient (intensive care)",
    "SUBCLIN_DEPRESSION": "Elevated depressive symptoms (non-diagnosed, questionnaire-defined)",
}

R: dict[str, dict] = {}


def rule(ds: str, **kw) -> None:
    assert ds not in R, f"duplicate rule for {ds}"
    R[ds] = kw


# ---- batch 1 ----------------------------------------------------------------------------
rule("ds007358", cond="PRESUMED_HEALTHY", conf="low", note="Large community sample (India, Tanzania); id prefixes are recording sites, not groups.")
rule("ds005385", cond="HEALTHY", conf="high", note="Healthy adult lifespan cohort; README disease terms are exclusion criteria.")
rule("ds008768", col="group", map={"PD": "PD", "Control": "HEALTHY"}, conf="high", cohort="PD_rest_ds008768",
     flag="Authors ask not to analyse until a new version is released (README, Oct 2026).")
rule("ds008875", col="group", map={"PD": "PD", "Control": "HEALTHY", "DBS": "PD"}, conf="high",
     note="DBS = Parkinson's disease patients with deep brain stimulation.")
rule("ds008115", cond="ICU", conf="medium", note="Critical-care patients, nociception monitoring.")
rule("ds007823", dup_of="ds008082", note="Same 173 COVID-19 survivors/contacts as ds008082, which has per-participant groups.")
rule("ds008082", col="group", map={"Covid": "COVID19", "Control": "HEALTHY"}, conf="high", cohort="covid_cuba")
rule("ds005305", cond="HEALTHY", conf="high")
rule("ds005486", cond="NOT_REPORTED", conf="low", note="No participants.tsv or README on the mirror.", check=True)
rule("ds004118", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds004584", col="GROUP", map={"PD": "PD", "Control": "HEALTHY"}, conf="high", cohort="cavanagh_pd_unm")
rule("ds004580", col="GROUP", map={"PD": "PD", "Control": "HEALTHY"}, conf="high", cohort="cavanagh_pd_unm")
rule("ds004574", col="GROUP", map={"PD": "PD", "Control": "HEALTHY"}, conf="high", cohort="cavanagh_pd_unm")
rule("ds007526", col="group", map={"PD": "PD", "HC": "HEALTHY"}, conf="high")
rule("ds006923", col="Subject type", map={"Offender": "HEALTHY", "No Offender": "HEALTHY"}, conf="medium",
     note="Juvenile offenders vs non-offenders: a legal, not clinical, grouping (kept as subgroup).")
rule("ds004579", col="GROUP", map={"PD": "PD", "Control": "HEALTHY"}, conf="high", cohort="cavanagh_pd_unm")
rule("ds005555", cond="HEALTHY", conf="medium", check=True)
rule("ds005863", dup_of="ds006018", note="Same 127 participants as ds006018.")
rule("ds006018", cond="HEALTHY", conf="high", cohort="ses_adulthood")
rule("ds005873", cond="EPILEPSY", conf="high", note="SeizeIT2 wearable EEG, people with epilepsy.")
rule("ds003474", cond="SUBCLIN_DEPRESSION", conf="medium", cohort="allen_bdi", check=True,
     note="College students selected for high or low Beck Depression Inventory scores; not a diagnosis.")
rule("ds003478", cond="SUBCLIN_DEPRESSION", conf="medium", cohort="allen_bdi", check=True)
rule("ds006861", col="Group", map={"Low Lonely": "HEALTHY", "High Lonely": "HEALTHY"}, conf="high",
     note="Loneliness groups (non-clinical).", intervention="tDCS")
rule("ds003518", cond="HEALTHY", conf="high", cohort="cavanagh_cabergoline", intervention="cabergoline (subset)")
rule("ds004532", cond="HEALTHY", conf="high", cohort="cavanagh_cabergoline", intervention="cabergoline (subset)")
rule("ds004120", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds005628", cond="PRESUMED_HEALTHY", conf="medium", note="Group = stimulus condition, not clinical.")
rule("ds007827", col="group", map={"Lonely": "HEALTHY", "Non-Lonely": "HEALTHY"}, conf="high", note="Loneliness groups (non-clinical).")
rule("ds003969", col="group", map={"ctr": "HEALTHY", "htr": "HEALTHY", "sny": "HEALTHY", "vip": "HEALTHY", "tm": "HEALTHY"},
     conf="high", note="Meditators of several traditions vs controls (non-clinical).")
rule("ds008878", cond="PRESUMED_HEALTHY", conf="low", flag="Local review snapshot, not an authorised public release (README).")

# ---- batch 2 ----------------------------------------------------------------------------
CONDITIONS.update({
    "POST_COVID": "Post-COVID-19 condition",
    "TBI": "Traumatic brain injury",
    "CLN3": "CLN3 disease (juvenile Batten disease)",
    "AD": "Alzheimer's disease",
    "FTD": "Frontotemporal dementia",
    "FEP": "First-episode psychosis",
    "STROKE": "Stroke",
    "LEARNING_DISORDER": "Specific learning disorder",
    "ZAN": "Zoster-associated neuralgia",
    "DEAF": "Deafness",
})
rule("ds007605", col="group", map={"withPCS": "POST_COVID", "withoutPCS": "COVID19"}, conf="high",
     note="All had SARS-CoV-2; withPCS = post-COVID syndrome with subjective cognitive impairment.")
rule("ds003522", col="Group", map={"0": "TBI", "1": "HEALTHY", "2": "TBI"}, conf="high", cohort="cavanagh_tbi",
     note="0 = sub-acute mild TBI, 2 = chronic TBI (data dictionary uses 'zero/one/two').")
rule("ds008896", col="group", map={"HV": "HEALTHY", "CLN3": "CLN3"}, conf="high")
rule("ds007020", cond="PD", conf="low", check=True,
     note="README says PD plus age-matched controls, but only survival status is coded per participant.")
rule("ds003523", col="Group", map={"0": "TBI", "1": "HEALTHY"}, conf="high", cohort="cavanagh_mtbi_acute")
rule("ds005114", col="Group", map={"0": "TBI", "1": "HEALTHY"}, conf="high", cohort="cavanagh_mtbi_acute")
rule("ds004504", col="Group", map={"A": "AD", "F": "FTD", "C": "HEALTHY"}, conf="high", cohort="ad_ftd_thessaloniki")
rule("ds006036", col="Group", map={"A": "AD", "F": "FTD", "C": "HEALTHY"}, conf="high", cohort="ad_ftd_thessaloniki",
     note="Same 88 people as ds004504, photic stimulation recordings.")
rule("ds003944", col="type", map={"Psychosis": "FEP", "Control": "HEALTHY"}, conf="high", cohort="fep_pitt_1")
rule("ds007801", cond="STROKE", conf="low", check=True, note="35 stroke patients + 5 controls per README; id codes not mapped yet.")
rule("ds004796", cond="HEALTHY", conf="high", note="PEARL-Neuro: healthy middle-aged adults with APOE genotypes (risk, not disease).")
rule("ds008092", cond="HEALTHY", conf="high", cohort="diet_identity", note="Dietary groups (non-clinical).")
rule("ds008940", cond="HEALTHY", conf="high", cohort="diet_identity")
rule("ds006260", cond="LEARNING_DISORDER", conf="medium", check=True,
     note="Children with learning difficulties; exp/cont = intervention arms.")
rule("ds003690", cond="HEALTHY", conf="high", note="Young vs older healthy adults.")
rule("ds004166", cond="HEALTHY", conf="high")
rule("ds006222", cond="HEALTHY", conf="high", cohort="flicker_pvt", intervention="40 Hz audiovisual flicker")
rule("ds007509", cond="HEALTHY", conf="high", cohort="flicker_pvt", intervention="40 Hz audiovisual flicker")
rule("ds006576", cond="HEALTHY", conf="high")
rule("ds007615", cond="HEALTHY", conf="high", note="Healthy women grouped by hormonal contraceptive use.")
rule("ds006480", cond="PRESUMED_HEALTHY", conf="medium", cohort="heartbeam", note="Young adults; threat-of-shock arousal.")
rule("ds007558", cond="NOT_REPORTED", conf="low", check=True)
rule("ds006434", cond="PRESUMED_HEALTHY", conf="medium", note="Id prefixes are listening conditions.")
rule("ds006466", cond="PRESUMED_HEALTHY", conf="medium", cohort="heartbeam_older")
rule("ds007181", col="group", map={"ZAN": "ZAN", "HC": "HEALTHY"}, conf="high")
rule("ds005291", cond="HEALTHY", conf="high")
rule("ds006110", cond="HEALTHY", conf="high", intervention="psilocybin 19 mg", note="PsiConnect.")
rule("ds008711", cond="PRESUMED_HEALTHY", conf="low", check=True, note="Group 1/2 undocumented (same lab as deaf/hearing ds005296).")
rule("ds006803", cond="HEALTHY", conf="high")
rule("ds006850", cond="HEALTHY", conf="high")
rule("ds008095", cond="NOT_REPORTED", conf="low", check=True, note="Not on the GitHub mirror.")
rule("ds005296", cond="DEAF", conf="low", check=True, note="Deaf and hearing groups coded 1/2 without a dictionary.")

# ---- batch 3 ----------------------------------------------------------------------------
CONDITIONS.update({
    "AUD": "Alcohol use disorder",
    "HAZARDOUS_DRINKING": "Hazardous / heavy drinking (community sample, not diagnosed AUD)",
    "SCZ": "Schizophrenia spectrum disorder",
})
rule("ds003947", col="type", map={"Psychosis": "FEP", "Control": "HEALTHY"}, conf="high", cohort="fep_pitt_2")
rule("ds005866", cond="PRESUMED_HEALTHY", conf="low", check=True, note="Holcomb/Emmorey lab, Group 1/2 undocumented.")
rule("ds008851", col="group", map={"Alcohol_Dependent": "AUD", "Healthy_Control": "HEALTHY"}, conf="high")
rule("ds007322", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds003506", col="Group", map={"PD": "PD", "CTL": "HEALTHY"}, conf="high", cohort="cavanagh_pd_onoff",
     note="PD tested ON and OFF dopaminergic medication.")
rule("ds003509", col="Group", map={"PD": "PD", "CTL": "HEALTHY"}, conf="high", cohort="cavanagh_pd_onoff")
rule("ds007666", cond="NOT_REPORTED", conf="low", note="Groups G1-G3 and 'unknown' undocumented.")
rule("ds007667", dup_of="ds007666")
rule("ds004515", col="GROUP", map={"ALC": "HAZARDOUS_DRINKING", "CTL": "HEALTHY"}, conf="high", cohort="cavanagh_alcohol")
rule("ds004595", col="GROUP", map={"AUD": "HAZARDOUS_DRINKING", "CTRL": "HEALTHY"}, conf="high", cohort="cavanagh_alcohol",
     note="Coded 'AUD' but README describes hazardous drinkers from the community.")
rule("ds005907", dup_of="ds004595")
rule("ds004626", cond="HEALTHY", conf="high", note="Lonely vs not lonely (non-clinical).")
rule("ds007609", cond="HEALTHY", conf="high", note="Trait anxiety in healthy adults.")
rule("ds003490", col="Group", map={"PD": "PD", "CTL": "HEALTHY"}, conf="high", cohort="cavanagh_pd_onoff")
rule("ds004315", cond="HEALTHY", conf="high", cohort="cavanagh_mood")
rule("ds004317", cond="HEALTHY", conf="high", cohort="cavanagh_mood")
rule("ds002893", cond="HEALTHY", conf="high", note="Younger vs older adults.")
rule("ds005868", cond="PRESUMED_HEALTHY", conf="low", check=True, note="Holcomb/Emmorey lab, Group 1/2 undocumented.")
rule("ds006554", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds007176", cond="HEALTHY", conf="medium", check=True, note="Id prefixes g/ctr; same group as ds007427.")
rule("ds007864", cond="PD", conf="medium", check=True, intervention="NeuroEPO (erythropoietin)")
rule("ds003620", cond="HEALTHY", conf="medium", note="2 participants self-report an unspecified neurological/psychiatric diagnosis.")
rule("ds007427", cond="NOT_REPORTED", conf="low", check=True, note="Alzheimer risk study; id prefixes g/ctr/dcl/dta to decode.")
rule("ds004000", col="group", map={"P": "SCZ", "HC": "HEALTHY"}, conf="high")
rule("ds005363", cond="HEALTHY", conf="high")
rule("ds008083", cond="HEALTHY", conf="medium", note="Psychosis proneness in a non-clinical sample.")
rule("ds004621", cond="HEALTHY", conf="high")
rule("ds007753", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds003570", cond="HEALTHY", conf="medium", note="Musicians (improvisers vs classical).")
rule("ds003751", cond="HEALTHY", conf="high")
rule("ds004367", col="Group", map={"Patient": "SCZ", "Control": "HEALTHY"}, conf="high")
rule("ds004388", cond="HEALTHY", conf="high")
rule("ds004563", cond="HEALTHY", conf="high", note="Vicarious touch groups; 'E' = excluded participants.")

# ---- batch 4 ----------------------------------------------------------------------------
CONDITIONS.update({
    "AMPUTATION": "Limb amputation (with or without phantom limb pain)",
    "MCI": "Mild cognitive impairment",
    "ANIMAL": "Non-human animal (excluded from human counts)",
})
rule("ds004368", col="Group", map={"Patient": "SCZ", "Control": "HEALTHY"}, conf="high", cohort="scz_marseille")
R["ds004367"]["cohort"] = "scz_marseille"
rule("ds005289", cond="HEALTHY", conf="high", cohort="laser_pain_cn")
rule("ds004802", cond="HEALTHY", conf="medium", note="Loneliness pilot; 6 report a past mental-health diagnosis.")
rule("ds006921", col="Amputee", map={"1": "AMPUTATION", "0": "HEALTHY"}, conf="high",
     note="Amputees with and without phantom limb pain vs intact controls.")
rule("ds005048", col="Group", map={"Mild AD": "AD", "Moderate AD": "AD", "MCI": "MCI", "Normal": "HEALTHY"}, conf="high",
     intervention="40 Hz auditory stimulation")
rule("ds006817", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds003004", cond="HEALTHY", conf="high")
rule("ds004521", cond="PRESUMED_HEALTHY", conf="medium", cohort="ester_pytel")
rule("ds004520", cond="PRESUMED_HEALTHY", conf="medium", cohort="ester_pytel_2")
rule("ds005795", cond="HEALTHY", conf="high")
rule("ds003768", cond="HEALTHY", conf="high", note="33 healthy participants (README); EEG-fMRI during sleep.")
rule("ds007822", cond="PRESUMED_HEALTHY", conf="medium", note="Group = hyperscanning triad.")
rule("ds004122", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds002778", prefix=True, map={"pd": "PD", "hc": "HEALTHY"}, conf="high", cohort="ucsd_pd",
     note="Diagnosis only encoded in subject ids (sub-pd*/sub-hc*).")
rule("ds003555", cond="EPILEPSY", conf="high", note="Paediatric epilepsy with HFO markings.")
rule("ds005286", cond="HEALTHY", conf="high", cohort="laser_pain_cn_ant")
rule("ds007537", cond="HEALTHY", conf="high")
rule("ds008099", cond="HEALTHY", conf="high")
rule("ds008465", cond="HEALTHY", conf="high")
rule("ds004123", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds007114", cond="HEALTHY", conf="high")
rule("ds003519", cond="HEALTHY", conf="high", cohort="cavanagh_cabergoline", intervention="cabergoline")
rule("ds004106", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds006735", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004389", cond="HEALTHY", conf="high", cohort="spinal_sep")
R["ds004388"]["cohort"] = "spinal_sep"
rule("ds001787", cond="HEALTHY", conf="high", note="Expert vs novice meditators.")
rule("ds004350", cond="PRESUMED_HEALTHY", conf="medium", note="Neurofeedback vs sham.")
rule("ds006104", cond="HEALTHY", conf="high")
rule("ds006269", cond="ANIMAL", conf="high", note="Syngap1 rat model.")
rule("ds007216", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds007865", cond="PD", conf="medium", check=True, cohort="neuroepo", intervention="placebo (NeuroEPO trial)")
R["ds007864"]["cohort"] = "neuroepo"
rule("ds003987", cond="HEALTHY", conf="high", intervention="d-amphetamine 10/20 mg vs placebo")
rule("ds005520", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds002814", cond="PRESUMED_HEALTHY", conf="low", note="Template metadata (TODO placeholders).")
rule("ds004119", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")

# ---- batch 5 ----------------------------------------------------------------------------
CONDITIONS.update({
    "PROCEDURE_PATIENT": "Patient undergoing surgery or anaesthesia (intraoperative recording)",
    "DEMENTIA": "Dementia (unspecified type)",
    "BURN": "Burn injury (intensive care)",
    "ORTHOPEDIC": "Orthopaedic impairment",
    "SSPI": "Severe speech and physical impairment (incl. ALS)",
    "PHANTOM": "Phantom head (non-biological, excluded)",
})
rule("ds004121", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds005620", cond="HEALTHY", conf="high", intervention="propofol sedation")
rule("ds006801", cond="HEALTHY", conf="high")
rule("ds001849", cond="PRESUMED_HEALTHY", conf="low", note="No participants.tsv or README.")
rule("ds002691", cond="HEALTHY", conf="high")
rule("ds003774", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004043", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004995", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds005688", cond="ANIMAL", conf="high", note="Mice (transcranial diagnostic ultrasound).")
rule("ds005815", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds001785", cond="HEALTHY", conf="high")
rule("ds002218", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds002718", cond="HEALTHY", conf="high", cohort="wakeman_henson_faces", note="EEG/MEG subset of ds000117.")
rule("ds003574", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004033", cond="HEALTHY", conf="high")
rule("ds004381", cond="PROCEDURE_PATIENT", conf="high", note="Intraoperative neuromonitoring during neurosurgery.")
rule("ds002338", cond="HEALTHY", conf="high")
rule("ds004105", col="group", map={"Normal": "HEALTHY"}, conf="high", cohort="BCIT")
rule("ds004661", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds003194", cond="PD", conf="high", cohort="neuroepo_2019", intervention="NeuroEPO (erythropoietin)")
rule("ds004752", cond="EPILEPSY", conf="high", note="Focal epilepsy, intracranial monitoring.")
rule("ds002034", cond="HEALTHY", conf="high")
rule("ds003061", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds003710", cond="HEALTHY", conf="high", note="Typically developing infants (4-12 months).")
rule("ds003800", cond="DEMENTIA", conf="medium", intervention="40 Hz auditory stimulation")
rule("ds005262", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004951", cond="NOT_REPORTED", conf="low", check=True, note="Braille study in visually deprived brain; group column says 'control'.")
rule("ds003195", cond="PD", conf="high", cohort="neuroepo_2019", intervention="placebo (NeuroEPO trial)")
rule("ds004598", cond="ANIMAL", conf="high", note="TgF344-AD rats.")
rule("ds004840", cond="BURN", conf="high", intervention="music therapy")
rule("ds007591", cond="PRESUMED_HEALTHY", conf="medium")
rule("ds004541", cond="PROCEDURE_PATIENT", conf="high", intervention="general anaesthesia (endoscopy/colonoscopy)")
rule("ds004022", cond="ORTHOPEDIC", conf="high")
rule("ds005307", cond="HEALTHY", conf="medium")
rule("ds007788", cond="HEALTHY", conf="high")
rule("ds006126", cond="PRESUMED_HEALTHY", conf="medium", intervention="tDCS")
rule("ds006945", cond="HEALTHY", conf="high")
rule("ds007720", cond="SSPI", conf="medium", note="BCI users with severe speech and physical impairment, including ALS.")
rule("ds004196", cond="HEALTHY", conf="high")
rule("ds007813", cond="NOT_REPORTED", conf="high", exclude=True, flag="Practice data; authors say not fit for any analysis.")
rule("ds007028", cond="ANIMAL", conf="high", note="Macaque monkeys.")
rule("ds007314", cond="STROKE", conf="high", note="Post-stroke anomia (aphasia).", intervention="tACS")
rule("ds007315", dup_of="ds007314")
rule("ds003380", cond="ANIMAL", conf="high", note="Juvenile pigs.")
rule("ds003805", cond="HEALTHY", conf="high")
rule("ds004784", cond="PHANTOM", conf="high", exclude=True)
rule("ds005079", cond="HEALTHY", conf="low", note="Single-participant case study.")
rule("ds004940", cond="HEALTHY", conf="high", note="Neurotypical adolescents.")

# ---- resolved checks ---------------------------------------------------------------------
CONDITIONS.update({
    "PSEN1_CARRIER": "Asymptomatic PSEN1-E280A carrier (autosomal dominant Alzheimer's disease risk)",
    "BLINDNESS": "Blindness",
})
R["ds005486"] = dict(cond="HEALTHY", conf="medium", intervention="experimental muscle pain (NGF injection)",
                     note="PREDICT: healthy volunteers, pain-sensitivity prediction study (Chowdhury, Seminowicz et al.).")
R["ds005555"].update(check=False, person_col="pid", note="128 nights; 'pid' identifies the person (several nights each).")
R["ds003474"] = dict(derive={"col": "BDI", "threshold": 13, "above": "SUBCLIN_DEPRESSION", "below": "HEALTHY"},
                     conf="medium", cohort="allen_bdi",
                     note="College students selected for high/low Beck Depression Inventory; BDI >= 13 labelled elevated symptoms (not a diagnosis).")
R["ds003478"] = dict(R["ds003474"])
R["ds007020"].update(check=False, conf="medium", note="All 94 shared ids are sub-PD*; README mentions controls that are not in this release.")
R["ds007801"] = dict(person_regex=r"^sub-[DM](.+)$", id_map={"25MB": "HEALTHY", "26MK": "HEALTHY", "35YT": "HEALTHY", "21IS": "HEALTHY", "36YB": "HEALTHY"},
                     default="STROKE", conf="high",
                     note="40 people x 2 recordings (D = imagined, M = attempted movement); 5 controls listed in README; patients have left/right paralysis.")
R["ds006260"].update(check=False, note="Children with learning difficulties (reading/math); Group = intervention vs control arm; ids M/R = math/reading.")
R["ds007558"].update(check=False)
for _ds, _cohort in (("ds008711", "holcomb_sentences"), ("ds005296", "holcomb_sentences"), ("ds005866", "holcomb_flankers"), ("ds005868", "holcomb_flankers")):
    R[_ds] = dict(col="Group", map={"1": "DEAF", "2": "HEALTHY"}, conf="medium", cohort=_cohort,
                  note="Group 1 has ASL age-of-acquisition values (deaf signers), group 2 has none (hearing); dataset dxStatus of ds005296 says 'Deaf and Hearing'.")
R["ds007176"] = dict(prefix=True, prefix_regex=r"^sub-(G[12]|[A-Za-z]+)", map={"ctr": "HEALTHY", "g2": "HEALTHY"}, conf="high", cohort="antioquia_psen1",
                     note="Healthy controls (CTR) and PSEN1 non-carrier family controls (G2).")
R["ds007427"] = dict(prefix=True, prefix_regex=r"^sub-(G[12]|[A-Za-z]+)",
                     map={"ctr": "HEALTHY", "g2": "HEALTHY", "g1": "PSEN1_CARRIER", "dcl": "MCI", "dta": "AD"}, conf="medium", cohort="antioquia_psen1",
                     note="README defines G1/G2; CTR, DCL (deterioro cognitivo leve) and DTA (demencia tipo Alzheimer) are the standard Spanish abbreviations.")
R["ds007864"].update(check=False)
R["ds007865"].update(check=False)
R["ds004951"] = dict(cond="BLINDNESS", conf="medium", note="Braille readers in a study of the visually deprived brain; group column only says 'control'.")

# ---- possible overlaps between cohorts (same lab / same programme) --------------------------
# 'group' joins cohorts that may share people. Counts report a conservative lower bound
# (one maximum per group) and an upper bound (one maximum per cohort).
for _ds in ("ds008768", "ds008875", "ds007020", "ds004584", "ds004580", "ds004574", "ds004579"):
    R[_ds]["group"] = "iowa_pd_narayanan"
for _ds in ("ds004584", "ds004580", "ds004574", "ds004579"):
    R[_ds]["cohort"] = "iowa_pd_2017_2021"
R["ds007020"]["cohort"] = "iowa_pd_mortality"
R["ds008875"]["cohort"] = "iowa_pd_dbs"
for _ds in ("ds007864", "ds007865", "ds003194", "ds003195"):
    R[_ds]["group"] = "neuroepo_cuba"
for _ds in ("ds003522", "ds003523", "ds005114"):
    R[_ds]["group"] = "cavanagh_tbi_unm"
for _ds in ("ds004515", "ds004595", "ds005907"):
    R[_ds]["group"] = "cavanagh_alcohol"

# ---- second pass: clinical groups missed by keyword triage (found by scanning all names) ----
CONDITIONS.update({
    "MIXED_COMMUNITY": "Community sample with mixed or dimensional clinical status (diagnoses not shared)",
    "OBESITY": "Obesity",
    "MISOPHONIA": "Misophonia",
    "CANCER_PAIN": "Cancer pain (head and neck)",
})
for _ds in ("ds005505", "ds005506", "ds005507", "ds005508", "ds005509", "ds005510", "ds005512", "ds005514", "ds005515", "ds005516"):
    R[_ds] = dict(cond="MIXED_COMMUNITY", conf="high", cohort=f"hbn_{_ds}", group="healthy_brain_network",
                  note="Healthy Brain Network: transdiagnostic paediatric sample. participants.tsv has p_factor, attention, "
                       "internalizing and externalizing scores; clinical diagnoses require the HBN data-use agreement.")
R["ds002181"] = dict(cond="MIXED_COMMUNITY", conf="medium", note="Bangladeshi infant/toddler birth cohorts in a study of stunting.")
R["ds003602"] = dict(cond="MIXED_COMMUNITY", conf="medium",
                     note="Women twins studied for childhood sexual abuse and problem drinking; group status not in participants.tsv.")
R["ds004019"] = dict(col="WS", map={"O": "OBESITY", "N-O": "HEALTHY"}, conf="high", cohort="acnc_obesity",
                     note="WS = weight status: O obese, N-O non-obese preteens.")
R["ds004151"] = dict(col="WS", map={"O": "OBESITY", "N-O": "HEALTHY"}, conf="high", cohort="acnc_obesity")
R["ds008003"] = dict(cond="NOT_REPORTED", conf="medium",
                     note="README: 23 misophonic + 32 controls, but participants.tsv carries no group labels.")
R["ds007347"] = dict(cond="CANCER_PAIN", conf="high", intervention="focused ultrasound mesencephalotomy")
R["ds006866"] = dict(cond="HEALTHY", conf="medium", note="Non-clinical adults with loneliness/social anxiety/depression questionnaires.")
# HBN releases contain different children: no overlap group.
for _ds in ("ds005505", "ds005506", "ds005507", "ds005508", "ds005509", "ds005510", "ds005512", "ds005514", "ds005515", "ds005516"):
    R[_ds].pop("group", None)

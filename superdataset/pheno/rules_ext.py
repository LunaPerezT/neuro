"""Expert phenotype rules for non-EEG OpenNeuro datasets (MRI, fMRI, dMRI, MEG, iEEG, PET...).

Same format as the EEG rules (eeg-annotation/rules.py), plus:
  default        condition for values not in `map` (instead of NOT_REPORTED)
  multi          {column: {value: COND}} secondary diagnoses (comorbidities); if the primary label is
                 HEALTHY and a secondary diagnosis is present, the first one becomes primary
  study_cond     with cond="UNRESOLVED": the study recruited patients with this condition and/or
                 controls, but the per-participant group is not in the public metadata
  counts         published group sizes for UNRESOLVED datasets, e.g. {"EPILEPSY": 442, "HEALTHY": 100}
  derivative_of  processed derivatives of another dataset (same people, not raw data)
  pheno_check    group may be recoverable from phenotype/ files (second pass)
"""

NEW_CONDITIONS = {
    "UNRESOLVED": "Patient or control, group not public per participant",
    "TRANSDIAGNOSTIC": "Psychiatric patient, mixed diagnoses (transdiagnostic sample)",
    "MDD": "Major depressive disorder",
    "DEPRESSION": "Depressive disorder (episode, unspecified severity/type)",
    "DYSTHYMIA": "Persistent depressive disorder (dysthymia)",
    "BIPOLAR": "Bipolar disorder",
    "ADHD": "Attention deficit hyperactivity disorder",
    "ASD": "Autism spectrum disorder",
    "ANXIETY": "Anxiety disorder",
    "PANIC": "Panic disorder",
    "SOCIAL_ANXIETY": "Social anxiety disorder",
    "GAD": "Generalized anxiety disorder",
    "PTSD": "Post-traumatic stress disorder",
    "OCD": "Obsessive-compulsive disorder",
    "BPD": "Borderline personality disorder",
    "IRRITABILITY": "Clinically significant irritability (youth)",
    "MOOD_NOS": "Mood disorder, not otherwise specified",
    "CHR_PSYCHOSIS": "Clinical high risk for psychosis (prodromal)",
    "PSYCHOSIS": "Psychotic disorder",
    "SUD": "Substance use disorder",
    "CUD": "Cocaine use disorder",
    "CANNABIS_UD": "Cannabis use disorder",
    "NICOTINE_DEP": "Tobacco/nicotine dependence (smoker)",
    "GAMBLING": "Gambling disorder",
    "ANOREXIA": "Anorexia nervosa",
    "FIBROMYALGIA": "Fibromyalgia",
    "DCM": "Degenerative cervical myelopathy",
    "CHRONIC_LBP": "Chronic low back pain",
    "KNEE_OA": "Knee osteoarthritis",
    "MYOFASCIAL_PAIN": "Masticatory myofascial pain syndrome",
    "TRIGEMINAL_NEURALGIA": "Trigeminal neuralgia",
    "GLIOBLASTOMA": "Glioblastoma",
    "BRAIN_TUMOR": "Brain tumour (mixed types)",
    "ANEURYSM": "Intracranial aneurysm",
    "FOCAL_LESION": "Chronic focal brain lesion (mixed aetiology)",
    "STROKE_WORKUP": "Evaluated for suspected acute stroke (no acute ischaemic stroke recorded)",
    "DYSTONIA": "Focal dystonia",
    "DYSLEXIA": "Developmental dyslexia",
    "DYSCALCULIA": "Developmental dyscalculia (math learning difficulty)",
    "PROSOPAGNOSIA": "Developmental prosopagnosia",
    "SYNESTHESIA": "Synaesthesia (non-clinical trait)",
    "CAD": "Coronary artery disease",
    "PERIPHERAL_NERVE_INJURY": "Peripheral nerve injury (upper limb)",
    "NEUROSURGICAL": "Neurosurgical patient (epilepsy or brain tumour, unspecified)",
    "HEARING_LOSS": "Hearing loss",
}

R: dict[str, dict] = {}


def rule(ds: str, **kw) -> None:
    assert ds not in R, f"duplicate rule for {ds}"
    R[ds] = kw


def D(ds, cond, conf="medium", **kw):          # whole dataset
    rule(ds, cond=cond, conf=conf, **kw)


def C(ds, col, mapping, conf="high", **kw):    # participants.tsv column
    rule(ds, col=col, map=mapping, conf=conf, **kw)


def U(ds, study, counts=None, conf="low", **kw):  # unresolved patient/control mix
    rule(ds, cond="UNRESOLVED", study_cond=study, counts=counts or {}, conf=conf, **kw)


HC = "HEALTHY"
PH = "PRESUMED_HEALTHY"

# ---- batch 1 (largest 130 datasets) ---------------------------------------------------------
C("ds004889", "acuteischaemicstroke", {"1": "STROKE"}, default="STROKE_WORKUP", conf="medium",
  note="SOOP: consecutive patients evaluated for stroke; acute ischaemic stroke flagged; others are stroke-code patients (TIA, haemorrhage, mimics).")
D("ds004169", HC, cohort="qtim", note="Queensland Twin Imaging: young adult twins/siblings, screened volunteers.")
D("ds008685", HC, cohort="qtim", note="QTIM diffusion release (same participants as ds004169).")
D("ds007522", HC, note="Precision Aging Network: cognitively healthy older adults.")
D("ds007111", PH, conf="low", pheno_check=True, note="NEUROLINGUA language database; no participants metadata fetched.")
U("ds005602", "EPILEPSY", {"EPILEPSY": 442, "HEALTHY": 100}, conf="medium", cohort="ideas",
  note="IDEAS: 442 drug-refractory focal epilepsy (surgical) + 100 controls; group list is on cnnp-lab.com/figshare, not OpenNeuro.")
U("ds007401", "EPILEPSY", {"EPILEPSY": 216, "HEALTHY": 98}, conf="medium", cohort="ideas",
  note="IDEAS II (adds DWI); same subject ids as IDEAS (ds005602).")
D("ds004856", HC, conf="high", note="Dallas Lifespan Brain Study (healthy ageing; MRI + amyloid/tau PET).")
D("ds004146", PH, conf="low", note="QTAB: community twin sample aged 9-14; no diagnoses shared.")
D("ds007286", "TRANSDIAGNOSTIC", conf="low", pheno_check=True, note="YaleNeuroConnect: diagnostically diverse sample; diagnoses not in participants.tsv.")
C("ds005143", "pathology", {"HC": HC, "FM": "FIBROMYALGIA", "CSM": "DCM", "DCM": "DCM"})
D("ds007045", "GLIOBLASTOMA", conf="high", note="Multi-centre primary glioblastoma; MGMT status per participant.")
D("ds000221", HC, conf="high", note="MPI-Leipzig Mind-Brain-Body (LEMON-related), healthy adults.")
C("ds007857", "group", {"CN": HC, "MCI": "MCI", "DAT": "AD"})
C("ds003949", "group", {"patient": "ANEURYSM", "control": HC}, note="Controls are clinical TOF-MRA scans without aneurysm.")
D("ds004789", "EPILEPSY", conf="high", cohort="upenn_ram", note="Intracranial (RAM project) patients with drug-resistant epilepsy.")
C("ds000030", "diagnosis", {"CONTROL": HC, "SCHZ": "SCZ", "BIPOLAR": "BIPOLAR", "ADHD": "ADHD"})
D("ds005896", HC, cohort="ahdc", note="Adolescent Health and Development in Context (community adolescents).")
D("ds004809", "EPILEPSY", conf="high", cohort="upenn_ram")
D("ds005752", HC, conf="high", note="NIMH Healthy Research Volunteers (screened; clinical variables available).")
C("ds005237", "Group", {"Patient": "TRANSDIAGNOSTIC", "GenPop": "MIXED_COMMUNITY"}, pheno_check=True)
D("ds005713", "TRIGEMINAL_NEURALGIA", conf="high", intervention="neurosurgery (pre/post)")
C("ds008579", "group", {"I": "IRRITABILITY", "TD": HC, "BPD": "BPD"}, cohort="grmpy",
  multi={"dx_adhd": {"1": "ADHD"}, "dx_anx": {"1": "ANXIETY"}, "dx_bp": {"1": "BIPOLAR"}, "dx_brderpd": {"1": "BPD"},
         "dx_mdd": {"1": "MDD"}, "dx_prodromal": {"1": "CHR_PSYCHOSIS"}, "dx_psychosis": {"1": "PSYCHOSIS"},
         "dx_ptsd": {"1": "PTSD"}, "dx_scz": {"1": "SCZ"}, "dx_sub": {"1": "SUD"}, "dx_moodnos": {"1": "MOOD_NOS"}})
C("ds004884", "wab_type", {}, default="STROKE", note="Aphasia Recovery Cohort: chronic left-hemisphere stroke with aphasia; WAB type kept as raw label.")
for _d in ("ds008590", "ds008606", "ds008602"):
    rule(_d, derivative_of="ds008579", cohort="grmpy", conf="medium")
U("ds005339", "DYSLEXIA", pheno_check=True, note="Yale reading disability study (RD + typical readers).")
D("ds000158", PH)
U("ds006636", "DYSLEXIA", pheno_check=True, note="Readers with and without dyslexia.")
D("ds007212", "FOCAL_LESION", conf="high", note="CCNRP chronic focal lesions (stroke, tumour resection, etc.) with lesion masks.")
D("ds007474", PH, conf="low", pheno_check=True, note="Transdiagnostic questionnaires in volunteers (2-step task).")
U("ds007606", "ANOREXIA", pheno_check=True, note="BEACON (anorexia nervosa T1w).")
D("ds005398", "EPILEPSY", conf="high", overlap="wsu_ieeg", note="Detroit/UCLA iEEG; pathology and Engel class per patient.")
D("ds003823", HC, conf="high", intervention="HRV biofeedback")
C("ds004199", "group", {"fcd": "EPILEPSY", "hc": HC}, note="Epilepsy due to focal cortical dysplasia type II.")
D("ds002843", PH, intervention="cognitive training")
D("ds006107", "EPILEPSY", conf="high")
D("ds005460", PH)
D("ds000228", PH)
C("ds005366", "participant_type", {"healthy": HC, "patient": "NEUROSURGICAL"})
rule("ds005498", prefix=True, map={"nthc": HC, "tehc": HC}, default="UNRESOLVED", study_cond="PTSD", conf="medium", pheno_check=True,
     multi={"Current PTSD Diagnosis": {"1": "PTSD"}, "Panic Disorder": {"1": "PANIC"}})
C("ds006303", "group", {"ANX": "ANXIETY", "HV": HC})
D("ds003145", PH)
U("ds005016", "CHRONIC_PAIN", {"CHRONIC_PAIN": 112, "HEALTHY": 35}, pheno_check=True, intervention="MBSR vs stress management (patients)")
C("ds007907", "group", {"IGN_CLBP": "CHRONIC_LBP", "PBRCBD": "CHRONIC_LBP", "PBRKOA_KOA": "KNEE_OA", "PBRKOA_HC": HC}, intervention="TSPO PET")
D("ds003481", PH)
C("ds003346", "group", {"2": "CUD", "1": HC, "CUD": "CUD", "HC": HC}, intervention="rTMS (patients)")
D("ds002380", PH, conf="low", pheno_check=True)
U("ds007741", "ANOREXIA", pheno_check=True, note="SCAN (anorexia nervosa T1w).")
C("ds007694", "group", {"LS": HC, "HS": HC}, note="Low vs high schizotypy, healthy general-population volunteers.")
D("ds003826", HC, conf="high")
U("ds003599", "CUD", pheno_check=True)
D("ds004965", PH)
D("ds004605", "TRANSDIAGNOSTIC", conf="low", pheno_check=True, note="NIMH Emotion & Development Branch: ADHD, DMDD and healthy volunteers.")
C("ds007116", "study_group", {"PRO/CHR": "CHR_PSYCHOSIS", "TD/NC": HC, "ADHD": "ADHD"}, cohort="penn_lead",
  multi={"dx_prodromal": {"1": "CHR_PSYCHOSIS"}, "dx_psychosis": {"1": "PSYCHOSIS"}, "dx_mdd": {"1": "MDD"},
         "dx_bp": {"1": "BIPOLAR"}, "dx_adhd": {"1": "ADHD"}, "dx_ptsd": {"1": "PTSD"}, "dx_moodnos": {"1": "MOOD_NOS"}})
for _d in ("ds007089", "ds007088", "ds006744"):
    rule(_d, derivative_of="ds007116", cohort="penn_lead", conf="medium")
U("ds004627", "MDD", pheno_check=True, note="NIMH CAT-D adolescents: depression and healthy volunteers.")
C("ds004466", "group", {"syn": "SYNESTHESIA", "control": HC})
U("ds005754", "TRANSDIAGNOSTIC", pheno_check=True, overlap="nimh_inhibitory")
U("ds005166", "TRANSDIAGNOSTIC", pheno_check=True, overlap="nimh_inhibitory")
D("ds005901", HC, cohort="ahdc")
for _d in ("ds006234", "ds006233", "ds005545"):
    D(_d, "EPILEPSY", conf="high", overlap="wsu_ieeg")
for _d in ("ds005256", "ds007446", "ds005123", "ds003701", "ds001747", "ds002647", "ds000258", "ds008765", "ds006926",
           "ds000222", "ds004873", "ds003831", "ds003643", "ds005613", "ds000201"):
    D(_d, HC, conf="high")
for _d in ("ds003798", "ds005731", "ds001734", "ds008055", "ds004946", "ds003416", "ds000202", "ds003345", "ds004765",
           "ds004228", "ds006736", "ds006169"):
    D(_d, PH)
D("ds006533", "STROKE", conf="high", note="Left-hemisphere chronic stroke survivors (lesion masks).")
for _d in ("ds007119", "ds007118", "ds007120"):
    D(_d, "EPILEPSY", conf="high", split="wsu_hfa", overlap="wsu_ieeg", note="One study split into 3 releases with disjoint subjects.")
C("ds005364", "COVID", {"1": "POST_COVID", "0": HC})
C("ds006577", "group", {"Anx": "ANXIETY", "HV": HC}, intervention="gamified attention bias modification + CBT")
C("ds006395", "group", {"HC": HC, "ULD": "DYSTONIA", "CD": "DYSTONIA"})
C("ds003653", "group_dx", {"HC": HC, "MDD": "MDD", "PDD": "DYSTHYMIA", "HCconvertedMDD": "MDD"})
D("ds004725", HC, conf="high", intervention="intranasal oxytocin vs placebo")
U("ds005356", "MDD", pheno_check=True)
C("ds004697", "risk_status_mom", {}, default=HC, conf="medium", note="Children 7-8 y; familial obesity risk kept as raw label.")
D("ds006905", "ADHD", conf="medium", pheno_check=True, intervention="Organizational Skills Training", note="Children in an OST trial; comorbidities in Diagnosis 1-7 columns.")
C("ds008719", "group", {"CAD": "CAD", "control": HC})
C("ds008783", "group", {"MMPS": "MYOFASCIAL_PAIN", "control": HC})
U("ds006045", "ANXIETY", pheno_check=True, intervention="CBT")
U("ds005026", "HEARING_LOSS", pheno_check=True)
C("ds001461", "diagnosis", {"schizophrenia": "SCZ", "healthy controls": HC}, multi={"smoking_status": {"smoking": "NICOTINE_DEP"}})
C("ds002424", "ADHD_diagnosis", {"1": "ADHD", "0": HC})
for _d in ("ds005265", "ds005263", "ds005266"):
    D(_d, HC, conf="high", cohort="skip")
C("ds000208", "type", {"patient": "KNEE_OA", "control": HC}, conf="medium", intervention="duloxetine vs placebo")
C("ds006948", "clinical_status", {"Healthy Volunteer": HC, "Anxiety Disorder": "ANXIETY"})
C("ds008022", "group", {"control": HC, "amputee": "AMPUTATION"})
D("ds004080", "EPILEPSY", conf="high")
C("ds004848", "group", {"Control": HC, "DP": "PROSOPAGNOSIA"})
C("ds002748", "group", {"depr": "DEPRESSION", "control": HC})
D("ds005059", "EPILEPSY", conf="high", cohort="upenn_ram")
C("ds004302", "group", {"HC": HC, "AVH-": "SCZ", "AVH+": "SCZ"})
C("ds008162", "isPatient", {"1": "PERIPHERAL_NERVE_INJURY", "0": HC})
C("ds005577", "group", {"dyslexia": "DYSLEXIA", "control": HC})
C("ds004791", "group", {"DD": "DYSCALCULIA", "TA": HC})
U("ds004144", "FIBROMYALGIA", {"FIBROMYALGIA": 33, "HEALTHY": 33}, pheno_check=True)
C("ds004469", "Group", {"Patient": "EPILEPSY", "Healthy": HC})
C("ds007182", "autism_diagnosis", {"yes": "ASD", "no": HC}, multi={"adhd_diagnosis": {"yes": "ADHD"}})
U("ds002513", "GAMBLING", pheno_check=True)

# ---- batch 2 --------------------------------------------------------------------------------
NEW_CONDITIONS.update({
    "T1D": "Type 1 diabetes mellitus", "TINNITUS": "Tinnitus", "GLAUCOMA": "Glaucoma",
    "PROLONGED_GRIEF": "Prolonged grief disorder", "MND": "Motor neuron disease",
    "MENINGIOMA": "Meningioma", "PITUITARY_ADENOMA": "Pituitary adenoma", "SPECIFIC_PHOBIA": "Specific phobia (spiders)",
    "FEP": "First-episode psychosis",
})
C("ds006156", "group", {"con": HC, "t1d": "T1D"})
C("ds007990", "group", {"experimental": "TINNITUS", "control": HC})
C("ds006837", "Group", {"patient": "GLAUCOMA", "control": HC})
U("ds007714", "DEMENTIA", pheno_check=True, note="Cambridge dementia dataset; no participant metadata.")
D("ds005096", "ANEURYSM", conf="high")
rule("ds006683", derive={"col": "n_diagnoses", "threshold": 1, "above": "TRANSDIAGNOSTIC", "below": HC}, conf="medium",
     note="Repetitive thought study; number of current diagnoses per participant.")
D("ds005083", "EPILEPSY", conf="high", note="Paediatric SEEG after prior craniotomy.")
C("ds006092", "group", {"experimental": "PROLONGED_GRIEF", "control": HC}, conf="medium", note="Post-pandemic prolonged grief disorder vs controls.")
U("ds004837", "FEP", pheno_check=True, note="Pittsburgh PEPP MEG mismatch negativity: first-episode psychosis and controls.")
U("ds005899", "ADHD", pheno_check=True)
D("ds006131", "MIXED_COMMUNITY", conf="low", pheno_check=True, note="PAFIN affective instability sample.")
D("ds007026", PH, conf="low", pheno_check=True)
D("ds004630", "SPECIFIC_PHOBIA", conf="medium", note="Adults with fear of spiders (dimensional, includes low fear).")
D("ds007345", "MENINGIOMA", conf="high", intervention="surgery (pre/post)")
D("ds006248", "PITUITARY_ADENOMA", conf="high")
for _d in ("ds003872", "ds003988", "ds003974"):
    D(_d, HC, cohort="reading_brain_project" if _d != "ds003974" else "reading_brain_project_l1")
C("ds005874", "group", {"Case": "MND", "Control": HC})
C("ds003126", "group", {"TD": HC, "DL": "DYSLEXIA", "SpD": "LEARNING_DISORDER"})
C("ds005917", "group", {"MDD": "MDD", "HC": HC, "BP": "BIPOLAR"}, intervention="ketamine vs placebo (crossover)")
C("ds005892", "group", {"Control": HC, "PD-NC": "PD", "PD-MCI": "PD"})
D("ds008110", "OCD", conf="high")
D("ds003037", "CUD", conf="high", overlap="sudmex", intervention="5 Hz rTMS lDLPFC (sham-controlled)",
  note="group column = treatment arm, all participants are CUD patients.")
R["ds003346"]["overlap"] = "sudmex"
R["ds003599"]["overlap"] = "sudmex"
C("ds008919", "group", {"patient": "CHRONIC_LBP", "control": HC})
C("ds003568", "group", {"MDD": "MDD", "HV": HC}, overlap="nimh_mmi")
C("ds003709", "group", {"MDD": "MDD", "HV": HC}, overlap="nimh_mmi")
for _d in ("ds005522", "ds004865"):
    D(_d, "EPILEPSY", conf="high", cohort="upenn_ram")
D("ds004100", "EPILEPSY", conf="high", note="HUP iEEG; surgical outcome and Engel class per patient.")
D("ds005431", "ANIMAL", conf="high", note="Animal Brain Collection Project (ex vivo animal brains).")
D("ds004767", "AD", conf="high", flag="ex vivo post-mortem specimens", note="Ex vivo MTL MRI + histology from brain donors.")
for _d in ("ds006686", "ds004044", "ds008813", "ds006243", "ds007022", "ds007953", "ds002731", "ds004920", "ds005038",
           "ds003138", "ds001242", "ds001408", "ds004073", "ds003745", "ds004182", "ds005518", "ds003114", "ds003791",
           "ds003763", "ds004665"):
    D(_d, HC, conf="high")
for _d in ("ds001748", "ds003871", "ds007185", "ds007993", "ds003148", "ds004086", "ds007436", "ds007523", "ds004261",
           "ds004359", "ds001838", "ds005386", "ds004553", "ds004996", "ds005040", "ds005616", "ds007524", "ds000107",
           "ds004440", "ds005604", "ds005639", "ds005450"):
    D(_d, PH)
C("ds005341", "code", {"CTL": HC, "DYS": "DYSLEXIA"})

# ---- batch 3 --------------------------------------------------------------------------------
NEW_CONDITIONS.update({"GLIOMA": "Glioma (lower grade / non-GBM)"})
C("ds002522", "group", {"Neurotypical": HC, "ASD": "ASD"})
D("ds003799", PH, conf="low", pheno_check=True, intervention="2-week running intervention", note="Volunteers with depressive symptoms (non-clinical?).")
for _d in ("ds004068", "ds004386"):
    D(_d, HC, conf="high", cohort="graz_spinal_zshim")
D("ds005411", "EPILEPSY", conf="high", cohort="upenn_ram")
D("ds005489", "EPILEPSY", conf="high", cohort="upenn_ram", intervention="open-loop stimulation at encoding")
D("ds006693", HC, conf="high", intervention="TMS (anterior vs posterior OFC)")
U("ds007179", "ANXIETY", pheno_check=True, note="NIMH youth error processing: anxiety and healthy volunteers.")
C("ds001371", "group", {"control": HC, "patient": "CHR_PSYCHOSIS"})
rule("ds001907", prefix=True, prefix_regex=r"^sub-(RC4[12])", map={"rc41": HC, "rc42": "PD"}, conf="high")
rule("ds000245", prefix=True, map={"odp": "PD", "odn": "PD", "ctl": HC}, conf="high",
     note="Cognitively normal PD with (ODP) and without (ODN) severe hyposmia, and controls (Yoneyama et al. 2018).")
D("ds000144", HC, conf="high", multi={"SADDx_p": {"1": "ANXIETY"}, "GADDx_p": {"1": "GAD"}, "SOCDx_p": {"1": "SOCIAL_ANXIETY"}},
  note="Youth anxiety study; separation/generalized/social anxiety diagnoses at pre-treatment.")
U("ds006564", "ASD", pheno_check=True)
D("ds006583", PH, conf="low", pheno_check=True)
C("ds008894", "primary_diagnosis", {"MDD": "MDD", "BP": "BIPOLAR"}, default=HC, note="group HV / clinical control / suicide risk kept in raw metadata.")
C("ds000174", "group", {"HC": HC, "CB": "CANNABIS_UD"}, conf="medium", note="Cannabis users (CUDIT scored), baseline and 3-year follow-up.")
C("ds001386", "group", {"TBI": "TBI", "Control": HC})
rule("ds004054", prefix=True, map={"control": HC, "patient": "EPILEPSY"}, conf="high", note="Interictal temporal lobe epilepsy, FDG-PET/MRI.")
C("ds004717", "tumor_type", {"astrocytoma": "GLIOMA", "glioblastoma": "GLIOBLASTOMA", "oligodendroglioma": "GLIOMA"})
D("ds005003", "BRAIN_TUMOR", conf="high")
D("ds007318", "NOT_REPORTED", conf="low", pheno_check=True, note="participants.tsv says all are patients; condition not stated.")
for _d in ("ds001725", "ds001529"):
    D(_d, "ANIMAL", conf="high", note="Mouse resting-state fMRI.")
C("ds001928", "group", {"FM": "FIBROMYALGIA", "HC": HC}, intervention="music vs pink noise")
D("ds003367", "TBI", conf="medium", pheno_check=True, note="Recovery from traumatic coma; metadata not fetched.")
D("ds004471", "PD", conf="high", intervention="DBS surgery")
C("ds004786", "group", {"CTL": HC, "DYS": "DYSLEXIA"})
C("ds006472", "group", {"DP": "PROSOPAGNOSIA", "control": HC})
D("ds006644", HC, conf="high", intervention="DMT + harmine vs placebo")
C("ds000171", "group", {"Never-Depressed Control": HC, "Major Depressive Disorder": "MDD"})
C("ds000212", "group", {"NT": HC, "ASD": "ASD"})
D("ds003876", "EPILEPSY", conf="high", overlap="hup_ieeg")
R["ds004100"]["overlap"] = "hup_ieeg"
U("ds005017", "CHRONIC_PAIN", pheno_check=True, overlap="pain_mbsr", note="Resting + pain scans, same design as ds005016 (MBSR).")
R["ds005016"]["overlap"] = "pain_mbsr"
C("ds006731", "group", {"MDD": "MDD", "HV": HC})
C("ds002896", "CONTROLS", {"1": HC, "0": "TINNITUS"}, note="Non-bothersome tinnitus.")
C("ds003500", "adhd", {"1": "ADHD", "0": HC}, note="11 adults + 12 ADHD children + 15 typically developing children.")
D("ds008462", "EPILEPSY", conf="high")
C("ds001226", "tumor type & grade", {"none": HC}, default="BRAIN_TUMOR", note="Glioma and meningioma (type/grade in raw label) + controls.")
C("ds000214", "group", {"Patient": "BPD", "Control": HC})
for _d in ("ds002419", "ds004327", "ds006521", "ds006628", "ds004533", "ds003787", "ds004934", "ds005374", "ds005469",
           "ds001534", "ds005559", "ds006902", "ds008941", "ds008714", "ds005700", "ds006179", "ds006642", "ds008784",
           "ds007115", "ds000113", "ds004094", "ds005479", "ds006568"):
    D(_d, HC, conf="high")
for _d in ("ds006676", "ds008255", "ds007335", "ds008727", "ds002979", "ds006240", "ds006844", "ds001247", "ds003950",
           "ds000217", "ds001521", "ds002989", "ds005934", "ds007806", "ds003085", "ds008830", "ds007952", "ds001576"):
    D(_d, PH)

# ---- batch 4 --------------------------------------------------------------------------------
NEW_CONDITIONS.update({"AMBLYOPIA": "Amblyopia", "FRAGILE_X": "Fragile X syndrome", "MS": "Multiple sclerosis"})
D("ds003029", "EPILEPSY", conf="high", overlap="hup_ieeg")
for _d in ("ds001945", "ds001890", "ds001653"):
    D(_d, "ANIMAL", conf="high")
C("ds006952", "group", {"control": HC, "patient": "NOT_REPORTED"}, conf="low", cohort="psych_rest", pheno_check=True)
R["ds008813"]["cohort"] = "psych_rest"
D("ds003892", "AMBLYOPIA", conf="high", note="Amblyopic (AE) vs fellow eye (FE) sessions.")
rule("ds007036", prefix=True, map={"p": "MND", "h": HC}, conf="high", note="7T MND-FTD spectrum vs non-neurodegenerative controls.")
C("ds005073", "groupID", {"2": "SCZ", "1": "BIPOLAR"})
D("ds002006", HC, conf="high")
C("ds002080", "tumor type & grade", {"none": HC, "": HC}, default="BRAIN_TUMOR", cohort="btc", note="Post-operative scans of BTC participants.")
R["ds001226"]["cohort"] = "btc"
D("ds002726", HC, conf="high", note="Gifted and control children.")
D("ds003007", "DEPRESSION", conf="high", overlap="moscow_depression", intervention="CBT or rt-fMRI neurofeedback vs none")
R["ds002748"]["overlap"] = "moscow_depression"
D("ds003999", "STROKE", conf="high", intervention="rehabilitation (pre/post)", note="Post-stroke aphasia; aphasia type kept in metadata.")
C("ds004654", "diagnosis", {"HC": HC, "FrX": "FRAGILE_X"}, overlap="nimh_rcps")
D("ds004731", HC, conf="high", overlap="nimh_rcps")
D("ds005264", HC, conf="high", cohort="skip")
C("ds007908", "group", {"patient": "MS", "control": HC})
D("ds008064", "MDD", conf="high", intervention="fMRI-guided rTMS + self-system therapy vs sham", note="Treatment-resistant depression.")
D("ds000133", HC, conf="high", intervention="modafinil vs placebo")
for _d in ("ds007532", "ds002878", "ds003401", "ds003521", "ds006559", "ds003542", "ds004958", "ds003146", "ds004274",
           "ds003357", "ds002938", "ds004331", "ds004496", "ds002411", "ds003691", "ds004693", "ds004909", "ds004974",
           "ds004775", "ds007394", "ds002898", "ds007588", "ds005596", "ds007342", "ds008725", "ds003540", "ds005075"):
    D(_d, HC, conf="high")
for _d in ("ds002144", "ds002316", "ds002873", "ds005658", "ds004081", "ds005492", "ds007947", "ds001551", "ds001715",
           "ds003176", "ds004663", "ds005125", "ds001972", "ds004009", "ds001607", "ds001847", "ds001926", "ds003772",
           "ds003778", "ds003789", "ds004323", "ds005589", "ds007368", "ds001614", "ds001762", "ds002241", "ds003096",
           "ds006601", "ds007388", "ds001218", "ds004829", "ds007387", "ds007508", "ds005464", "ds008495", "ds001105",
           "ds000164", "ds003682", "ds005933"):
    D(_d, PH)

# ---- batch 5 --------------------------------------------------------------------------------
NEW_CONDITIONS.update({"SCA": "Spinocerebellar ataxia", "CHRONIC_PAIN": "Chronic pain (mixed/unspecified)",
                       "OB_AGENESIS": "Absent olfactory bulbs (with preserved olfaction)", "BRAIN_ABSCESS": "Brain abscess",
                       "CORTICAL_MALFORMATION": "Malformation of cortical development (heterotopia)",
                       "APHANTASIA": "Aphantasia (non-clinical trait)", "NF1": "Neurofibromatosis type 1"})
rule("ds000220", prefix=True, map={"tbi": "TBI", "control": HC}, conf="high")
C("ds000213", "group", {}, default=HC, conf="medium", note="Overweight vs normal-weight healthy adults (raw label kept).")
D("ds002799", "EPILEPSY", conf="high", note="es-fMRI: electrical stimulation in patients with refractory epilepsy.")
for _d in ("ds003468", "ds002154", "ds003464"):
    D(_d, "ANIMAL", conf="high")
C("ds001378", "group", {"CONTROL": HC, "SCA2": "SCA"})
for _d in ("ds003052", "ds003417"):
    D(_d, "NOT_REPORTED", conf="medium", overlap="penn_exvivo_mtl", flag="ex vivo post-mortem specimens",
      note="Ex vivo MTL specimens from brain donors with mixed neurodegenerative pathology.")
R["ds004767"]["overlap"] = "penn_exvivo_mtl"
D("ds007135", "CHRONIC_LBP", conf="high", note="Patients only; epigenetic PET.")
D("ds002675", "TBI", conf="high", overlap="edlow_tbi", note="Severe TBI, recovery of the language network.")
R["ds003367"]["overlap"] = "edlow_tbi"
for _d in ("ds005624", "ds004944", "ds006253", "ds003498"):
    D(_d, "EPILEPSY", conf="high")
for _d in ("ds006519", "ds005169"):
    D(_d, "EPILEPSY", conf="high", overlap="grenoble_seeg", note="Drug-resistant epilepsy, SEEG stimulation.")
for _d in ("ds005523", "ds005494", "ds005491", "ds005557"):
    D(_d, "EPILEPSY", conf="high", cohort="upenn_ram", intervention="intracranial stimulation")
U("ds003027", "NF1", pheno_check=True, note="'plp_nf1' dMRI/fMRI; condition inferred from title only.")
U("ds005562", "APHANTASIA", pheno_check=True)
C("ds002185", "group", {"control": HC}, default="OB_AGENESIS")
C("ds004910", "group", {"health control": HC, "healthy": HC, "glioma who ii": "GLIOMA", "glioma who iii": "GLIOMA",
                        "glioma who iv": "GLIOBLASTOMA", "glioblastoma": "GLIOBLASTOMA", "meningioma who i": "MENINGIOMA",
                        "multiple sclerosis": "MS", "cortical cerebral infarction": "STROKE",
                        "diffuse large b-cell lymphoma": "BRAIN_TUMOR", "brain abscess": "BRAIN_ABSCESS",
                        "gray matter heterotopia": "CORTICAL_MALFORMATION"}, default="NEUROSURGICAL")
D("ds004998", "PD", conf="high", intervention="externalised STN DBS; levodopa ON/OFF")
D("ds006949", "CHRONIC_PAIN", conf="low", intervention="low-intensity focused ultrasound",
  note="Complex patients: chronic pain, opioid use disorder and/or anxiety (safety MRIs).")
C("ds007561", "diagnosis", {"Control": HC, "MCI": "MCI", "AD": "AD"})
D("ds007384", HC, conf="medium", flag="fMRIPrep derivatives only", note="Hyperface derivatives.")
for _d in ("ds003433", "ds003434"):
    D(_d, PH, cohort="newbi4fmri")
D("ds004733", HC, conf="high", overlap="nimh_rcps")
D("ds008600", PH, conf="low", pheno_check=True, note="Speech and sign language under challenging conditions (participants may include deaf signers).")
for _d in ("ds002776", "ds004783", "ds006506", "ds006623", "ds002041", "ds002712", "ds003233", "ds005704", "ds000256",
           "ds001454", "ds002687", "ds002940", "ds003487", "ds006212", "ds007942", "ds008464", "ds004332", "ds004937",
           "ds005360", "ds007442", "ds003466", "ds005025", "ds000253", "ds001597", "ds003089", "ds003338", "ds004141",
           "ds008460", "ds001634", "ds002773", "ds003342", "ds008948", "ds001233", "ds004467"):
    D(_d, HC, conf="high")
for _d in ("ds000203", "ds003136", "ds004007", "ds005894", "ds000009", "ds001145", "ds001612", "ds001745", "ds001775",
           "ds001946", "ds007468", "ds001302", "ds002311", "ds004286", "ds001621", "ds001751", "ds002155", "ds003484",
           "ds003715", "ds004594", "ds000223", "ds001357", "ds000116"):
    D(_d, PH)

# ---- batch 6 --------------------------------------------------------------------------------
NEW_CONDITIONS.update({"ESSENTIAL_TREMOR": "Essential tremor", "NEUROPATHIC_PAIN": "Neuropathic pain"})
for _d in ("ds003520", "ds001541", "ds001875"):
    D(_d, "ANIMAL", conf="high")
D("ds005573", "NEUROSURGICAL", conf="medium", note="Paediatric patients with invasive electrocortical stimulation mapping.")
C("ds004798", "group", {"control": HC}, default="EPILEPSY", conf="medium", note="fMRI participants labelled control; iEEG participants are epilepsy patients.")
C("ds001784", "dx", {"MDD": "MDD", "OCD": "OCD"}, intervention="DBS ON/OFF (treatment-resistant)")
for _d in ("ds004194", "ds006136", "ds004703", "ds003374", "ds004473", "ds004696", "ds007095", "ds005415"):
    D(_d, "EPILEPSY", conf="high")
for _d in ("ds004774", "ds005448", "ds004370"):
    D(_d, "EPILEPSY", conf="high", overlap="umcu_respect")
R["ds004080"]["overlap"] = "umcu_respect"
for _d in ("ds004770", "ds005931"):
    D(_d, "EPILEPSY", conf="high", overlap="peds_ieeg_gameplay")
D("ds005849", "NOT_REPORTED", conf="low", pheno_check=True, note="DBS patients (precision imaging); indication not stated.")
D("ds002908", "PD", conf="medium", pheno_check=True)
D("ds008174", "DYSTONIA", conf="high", intervention="continuous theta-burst stimulation")
D("ds008798", "STROKE", conf="high", note="Bedside HD-DOT during stroke recovery.")
C("ds001743", "group", {"Patient": "GLAUCOMA", "Control": HC})
rule("ds006190", derivative_of="ds006131", conf="medium")
C("ds008336", "diagnosis", {"ET": "ESSENTIAL_TREMOR", "ETp": "ESSENTIAL_TREMOR"})
D("ds006072", HC, conf="high", intervention="psilocybin vs methylphenidate (crossover)")
for _d in ("ds007034", "ds007109"):
    D(_d, HC, conf="high", cohort="maastricht_assoc7t")
D("ds004642", "BRAIN_TUMOR", conf="high", note="Intraoperative ECoG during tumour surgery.")
D("ds004730", HC, conf="high", overlap="nimh_rcps", intervention="propofol")
D("ds004868", PH, conf="low", pheno_check=True, note="[11C]PS13 COX-1 PET.")
D("ds005906", "PD", conf="high")
D("ds004101", HC, conf="low", intervention="infra-low frequency neurofeedback", note="Subclinical emotional dysregulation (anxiety, mild depression, somatoform symptoms).")
D("ds005558", "EPILEPSY", conf="high", cohort="upenn_ram", intervention="closed-loop stimulation")
D("ds002715", "BLINDNESS", conf="medium", pheno_check=True)
D("ds003770", "DEPRESSION", conf="high", overlap="moscow_depression", intervention="mPFC rt-fMRI neurofeedback")
D("ds005691", "NEUROPATHIC_PAIN", conf="high")
D("ds001293", HC, conf="high", cohort="studyforrest")
R["ds000113"]["cohort"] = "studyforrest"
for _d in ("ds003171", "ds005295", "ds001635", "ds005783", "ds007862", "ds003397", "ds004489", "ds004956", "ds006483",
           "ds007156", "ds007768", "ds003524", "ds000233", "ds008704", "ds005238", "ds005525", "ds001942", "ds003382",
           "ds004142", "ds004539", "ds005085", "ds006598", "ds005664", "ds006512", "ds004097", "ds003192", "ds007780"):
    D(_d, HC, conf="high")
for _d in ("ds001912", "ds004744", "ds001132", "ds001832", "ds002237", "ds003170", "ds001921", "ds001984", "ds003059",
           "ds003758", "ds004656", "ds001339", "ds001923", "ds001978", "ds006401", "ds007067", "ds007847", "ds000051",
           "ds000052", "ds000237", "ds002076", "ds001235", "ds000241", "ds006145", "ds000205", "ds004715", "ds001497",
           "ds002001", "ds007799", "ds007932", "ds001652", "ds002295", "ds003927", "ds004670"):
    D(_d, PH)
R["ds003059"].update(cond=HC, conf="high", intervention="LSD vs placebo")

# ---- batch 7 (small and single-subject datasets, derivatives) ---------------------------------
NEW_CONDITIONS.update({"HEMISPHERECTOMY": "Adult with a single cerebral hemisphere (hemispherectomy)",
                       "PROSOPOMETAMORPHOPSIA": "Prosopometamorphopsia (face distortion)",
                       "TOF": "Tetralogy of Fallot (congenital heart disease)"})
EXVIVO = "ex vivo post-mortem specimens"
D("ds005090", "PHANTOM", conf="high", exclude=True)
D("ds005563", PH, conf="low", flag="fetal/infant specimens", note="Fetal and infant brains (development of arousal network).")
for _d in ("ds006001", "ds007677", "ds005422", "ds002016", "ds003590", "ds007975"):
    D(_d, "NOT_REPORTED", conf="medium", flag=EXVIVO)
D("ds002179", HC, conf="high", flag=EXVIVO, note="Donor without neurological disease.")
for _d in ("ds006065", "ds003078", "ds004457", "ds004977", "ds004993", "ds005670", "ds007703", "ds003708", "ds007445"):
    D(_d, "EPILEPSY", conf="high")
for _d in ("ds003844", "ds003848"):
    D(_d, "EPILEPSY", conf="high", overlap="umcu_respect")
for _d in ("ds006188", "ds006193", "ds006143", "ds006182", "ds006184", "ds006189", "ds006191"):
    rule(_d, derivative_of="ds006131", conf="medium")
for _d in ("ds006779", "ds007090", "ds007091", "ds007402"):
    rule(_d, derivative_of="ds007116", cohort="penn_lead", conf="medium")
for _d in ("ds008325", "ds008328", "ds008547", "ds008601"):
    rule(_d, derivative_of="ds008579", cohort="grmpy", conf="medium")
rule("ds005472", derivative_of="ds004331", conf="high")
rule("ds005481", derivative_of="ds004496", conf="high")
rule("ds007378", derivative_of="ds007384", conf="medium", note="Hyperface FreeSurfer derivatives.")
rule("ds001769", derivative_of="ds000113", cohort="studyforrest", conf="high")
C("ds002232", "group", {f"CNT{i}": HC for i in range(1, 7)}, default="HEMISPHERECTOMY")
D("ds005063", "ESSENTIAL_TREMOR", conf="high", intervention="coordinated reset DBS")
C("ds006206", "group", {"control": HC, "patient": "NOT_REPORTED"}, conf="medium")
D("ds007486", HC, conf="low", pheno_check=True, note="Work in progress; only controls released so far.")
D("ds003011", HC, conf="high", note="SPINS travelling human phantoms.")
D("ds005597", "BRAIN_TUMOR", conf="high", overlap="tumor_retro_fmri")
R["ds005003"]["overlap"] = "tumor_retro_fmri"
C("ds005699", "group", {"control": HC, "patient": "NOT_REPORTED"}, conf="low", flag="software test dataset")
U("ds004450", "TRANSDIAGNOSTIC", pheno_check=True, note="EFR01: healthy, ADHD and psychosis-spectrum (3 subjects).")
D("ds006815", "FIBROMYALGIA", conf="medium", note="Dense sampling of individuals in chronic pain.")
for _d in ("ds001591",):
    D(_d, "ANIMAL", conf="high")
D("ds002040", "PD", conf="low")
D("ds002293", "NOT_REPORTED", conf="low", flag="software test dataset")
for _d in ("ds004129", "ds004130", "ds004131"):
    D(_d, HC, conf="high", dup_of="ds003982", flag="copy of the NIMH Healthy Research Volunteer dataset (BIDS phenotype example)")
D("ds004498", "STROKE", conf="low", note="Perinatal stroke (single subject).")
D("ds002674", HC, conf="high", flag="dense sampling: 1 person, sessions stored as subjects")
D("ds005115", HC, conf="high", flag="dense sampling: 1 person, sessions stored as subjects")
D("ds006592", "PROSOPOMETAMORPHOPSIA", conf="high")
D("ds003444", "PROSOPAGNOSIA", conf="high", cohort="newbi4fmri")
D("ds004392", "PD", conf="high")
C("ds005234", "group", {"td": HC, "asd": "ASD"})
D("ds006224", "PD", conf="medium", pheno_check=True)
C("ds006318", "label", {"tumor": "BRAIN_TUMOR", "non_tumor": HC}, conf="low", cohort="brain_tumor_ai")
C("ds006638", "label", {"tumor": "BRAIN_TUMOR", "non_tumor": HC}, conf="low", cohort="brain_tumor_ai")
D("ds006556", "TOF", conf="medium", pheno_check=True)
for _d in ("ds006777", "ds006780"):
    C(_d, "group", {"ASD": "ASD", "TD": HC, "ASD SIBLING": HC}, overlap="sfari_eeg", note="Unaffected ASD siblings coded HEALTHY (raw label kept).")
D("ds008205", "NOT_REPORTED", conf="low", note="Paediatric clinical quantitative MRI.")
for _d in ("ds003441", "ds003438", "ds003439", "ds003440", "ds003442", "ds003443", "ds003445", "ds003446"):
    D(_d, HC, conf="medium", cohort="newbi4fmri")
for _d in ("ds006917", "ds000206", "ds001399", "ds001839", "ds000247", "ds002278", "ds004906", "ds005454", "ds006035",
           "ds002684", "ds006491", "ds006707", "ds000246", "ds003082", "ds000031", "ds003716", "ds004401", "ds004776",
           "ds005299", "ds007313", "ds007328", "ds008101", "ds006883", "ds007690", "ds001553", "ds001555", "ds003043",
           "ds004943", "ds005903", "ds006947", "ds004720", "ds006373", "ds005134", "ds005365", "ds002372"):
    D(_d, HC, conf="high")
for _d in ("ds001705", "ds004283", "ds001037", "ds004229", "ds007713", "ds001107", "ds005630", "ds005926", "ds007043",
           "ds007501", "ds008321", "ds005191", "ds007408", "ds007816", "ds001246", "ds002425", "ds002672", "ds003661",
           "ds007473", "ds007792", "ds002013", "ds001506", "ds003642", "ds003659", "ds004187", "ds006128", "ds000255",
           "ds003993", "ds004458", "ds004640", "ds004710", "ds007739", "ds001419", "ds000204", "ds001595", "ds001600",
           "ds001780", "ds002087", "ds002153", "ds002156", "ds002274", "ds002328", "ds002367", "ds002549", "ds002614",
           "ds002733", "ds003098", "ds003455", "ds003563", "ds003714", "ds003850", "ds004398", "ds004742", "ds005978",
           "ds006181", "ds006486", "ds006935", "ds000105"):
    D(_d, PH)

# ---- phenotype-file pass (second pass over pheno_check datasets) ------------------------------
NEW_CONDITIONS.update({"DMDD": "Disruptive mood dysregulation disorder", "ODD": "Oppositional defiant disorder",
                       "CONDUCT": "Conduct disorder", "TIC": "Tic disorder", "SEPARATION_ANXIETY": "Separation anxiety disorder"})
KSADS = {"K_SADS_PL_MDD": {"1": "MDD"}, "K_SADS_PL_MANIA": {"1": "BIPOLAR"}, "K_SADS_PL_HYPOMANIA": {"1": "BIPOLAR"},
         "K_SADS_PL_PSYCHOSIS": {"1": "PSYCHOSIS"}, "K_SADS_PL_PANIC_DISORDER": {"1": "PANIC"},
         "K_SADS_PL_SAD": {"1": "SEPARATION_ANXIETY"}, "K_SADS_PL_AVOID_DISORDER": {"1": "ANXIETY"},
         "K_SADS_PL_AGORAPHOBIA": {"1": "ANXIETY"}, "K_SADS_PL_GAD": {"1": "GAD"}, "K_SADS_PL_OCD": {"1": "OCD"},
         "K_SADS_PL_ANOREXIA": {"1": "ANOREXIA"}, "K_SADS_PL_ADHD": {"1": "ADHD"}, "K_SADS_PL_ODD": {"1": "ODD"},
         "K_SADS_PL_CONDUCT": {"1": "CONDUCT"}, "K_SADS_PL_DMDD": {"1": "DMDD"}, "K_SADS_PL_TIC": {"1": "TIC"},
         "K_SADS_PL_PTSD": {"1": "PTSD"}, "K_SADS_PL_SOCIAL_PHOBIA": {"1": "SOCIAL_ANXIETY"},
         "K_SADS_PL_SPECIFIC_PHOBIA": {"1": "SPECIFIC_PHOBIA"}, "K_SADS_PL_ALCOHOL_ABUSE": {"1": "AUD"},
         "K_SADS_PL_SUBSTANCE_ABUSE": {"1": "SUD"}}
R["ds004605"].update(cond="HEALTHY", conf="high", pheno_files=["phenotype/phenotype.tsv"], cond_unmatched="TRANSDIAGNOSTIC",
                     multi={"DX.ADHD": {"1": "ADHD"}, "DX.DMDD": {"1": "DMDD"}, "DX.ANX": {"1": "ANXIETY"}, "DX.ODD": {"1": "ODD"}},
                     pheno_check=False, note="Diagnoses from phenotype/phenotype.tsv (DX.* flags).")
for _d in ("ds005754", "ds005166"):
    R[_d] = dict(cond="HEALTHY", conf="high", pheno_files=["ds005754/phenotype/KSADS.tsv"], cond_unmatched="UNRESOLVED",
                 study_cond="TRANSDIAGNOSTIC", multi=KSADS, overlap="nimh_inhibitory",
                 note="K-SADS-PL diagnoses from ds005754 phenotype/KSADS.tsv (shared participant ids).")
R["ds005498"] = dict(col="No Diagnosis", map={"1": "HEALTHY"}, default="TRANSDIAGNOSTIC", conf="high", multi_primary=True,
                     multi={"Current PTSD Diagnosis": {"1": "PTSD"}, "Panic Disorder": {"1": "PANIC"}},
                     note="Trauma-exposed and non-exposed adults; current PTSD / panic flags; 'Diagnosis Other Misc' kept as TRANSDIAGNOSTIC.")

# ---- second pass over automatically labelled datasets (names / domains with clinical terms) -----
U("ds005112", "TRANSDIAGNOSTIC", conf="low", note="NIMH CTNB (00-M-0085) + Behavioral Endocrinology (11-M-0251) protocols; diagnoses not shared.")
D("ds003688", "EPILEPSY", conf="high", note="UMC Utrecht iEEG-fMRI film dataset: presurgical epilepsy patients.")
D("ds005483", HC, conf="high", note="[11C]PS13 COX-1 PET in healthy volunteers.")
D("ds004470", HC, conf="high", note="SNSX: 32 healthy participants at 7T.")

# ---- links found by metadata dedup (pheno/meta_dedup.py) -------------------------------------
# Applied on top of any rule (EEG or extended). cohort = same people (ids are linked when they match);
# overlap = may share people; dup_of / derivative_of = not counted.
LINKS: dict[str, dict] = {
    "ds004795": {"derivative_of": "ds004173", "flag": "simulated motion artefacts on MR-ART images"},
    "ds005920": {"dup_of": "ds005596"},
    "ds007661": {"derivative_of": "ds004662"},
    "ds005363": {"cohort": "orha"}, "ds005374": {"cohort": "orha"},
    "ds004152": {"cohort": "drum_feedback"}, "ds004262": {"cohort": "drum_feedback"}, "ds004264": {"cohort": "drum_feedback"},
    "ds004444": {"cohort": "bmi_hdeeg"}, "ds004446": {"cohort": "bmi_hdeeg"}, "ds004447": {"cohort": "bmi_hdeeg"},
    "ds004448": {"overlap": "bmi_hdeeg"},
    "ds004484": {"overlap": "csf_flow"}, "ds004493": {"overlap": "csf_flow"}, "ds004478": {"overlap": "csf_flow"},
    "ds003518": {"overlap": "cavanagh_simon"}, "ds003509": {"overlap": "cavanagh_simon"},
    "ds003523": {"overlap": "cavanagh_vwm"}, "ds003519": {"overlap": "cavanagh_vwm"},
    "ds005810": {"overlap": "nod"}, "ds005811": {"overlap": "nod"},
    "ds005964": {"overlap": "fresh"}, "ds005963": {"overlap": "fresh"},
    "ds006265": {"cohort": "toam"}, "ds006266": {"cohort": "toam"},
    "ds006459": {"cohort": "stroop_fnirs"}, "ds006460": {"cohort": "stroop_fnirs"},
    "ds007169": {"cohort": "workload"}, "ds007262": {"cohort": "workload"},
    "ds007647": {"cohort": "narrative_reward"}, "ds007968": {"cohort": "narrative_reward"},
    "ds007663": {"overlap": "crossmodal"}, "ds007648": {"overlap": "crossmodal"},
    "ds005697": {"overlap": "perceive_imagine"}, "ds005672": {"overlap": "perceive_imagine"},
    "ds005479": {"overlap": "mid_circadian"}, "ds003858": {"overlap": "mid_circadian"},
    "ds004158": {"overlap": "retinomaps"}, "ds008507": {"overlap": "retinomaps"},
    "ds004012": {"cohort": "brar"}, "ds004278": {"cohort": "brar"},
    "ds003877": {"overlap": "bangladesh_bean"}, "ds005504": {"overlap": "bangladesh_bean"},
    "ds005872": {"overlap": "eegeyenet"}, "ds007338": {"overlap": "eegeyenet"},
    "ds006648": {"overlap": "poetry_eeg"}, "ds006647": {"overlap": "poetry_eeg"},
    "ds005069": {"overlap": "seq_integration"}, "ds005072": {"overlap": "seq_integration"}, "ds005581": {"overlap": "seq_integration"},
    "ds000234": {"overlap": "ds000234_6"}, "ds000235": {"overlap": "ds000234_6"}, "ds000236": {"overlap": "ds000234_6"},
}

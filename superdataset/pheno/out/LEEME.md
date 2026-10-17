# Fenotipos por participante de todo OpenNeuro humano (v1, 17-10-2026)

Anotación clínica de **todos los participantes con datos** en los **1.821 datasets humanos** de OpenNeuro y en todas las modalidades (EEG, MEG, iEEG, MRI, fMRI, dMRI, PET, ASL, fNIRS). Extiende la anotación de EEG v1 al resto de modalidades.

## Archivos

| Archivo | Contenido |
|---|---|
| `neuro_openneuro.sqlite` | Todas las tablas en una base SQLite |
| `participants.csv` | Una fila por persona y dataset (97.124 filas) |
| `datasets.csv` | Una fila por dataset: regla aplicada, cohorte, solapamiento, duplicado o derivado, intervención, avisos y notas |
| `conditions.csv` | Las 110 categorías, con código SNOMED CT y tipo de correspondencia |
| `ranking.csv` | Condición × modalidad: personas únicas (mínimo y máximo), número de datasets y personas multimodales |
| `metadata_duplicate_candidates.csv` | Pares de datasets con README, nombre o (edad, sexo) idénticos, revisados a mano |

## Campos clave de `participants.csv`

- `global_id`: identificador de persona compartido entre datasets. La columna `global_id_source` indica cómo se obtuvo:
  - `content_hash`: archivos idénticos (SHA-256 de git-annex).
  - `cohort_subject_id`: mismo ID de sujeto en datasets de la misma cohorte.
  - `dataset_local`: sin vínculo externo.
- `modalities`: modalidades con datos de esa persona en ese dataset.
- `data_location`: dónde están sus datos.
  - `raw`: en la estructura BIDS principal.
  - `derivatives_only`: solo en `derivatives/` o `sourcedata/`.
  - `participants_tsv_only`: el inventario falló y solo hay fila en `participants.tsv`.
- `condition`: condición principal. `other_conditions` recoge las comorbilidades (por ejemplo, a partir de las columnas dx_* o de K-SADS).
- `role` puede tomar estos valores:
  - `patient`
  - `control`: sano dentro de un dataset con pacientes
  - `healthy`
  - `presumed_healthy`
  - `mixed_community`
  - `unresolved`: el estudio tiene pacientes y controles, pero el grupo de cada persona no es público
  - `unknown`
- `raw_label` y `label_source` guardan el valor original y su origen: columna, prefijo del ID, archivo de `phenotype/`, umbral o nivel de dataset.
- `counted`: es falso en duplicados, derivados, animales, fantomas y datos de prueba.

## Método

1. **Inventario.** Inventario BIDS de los 1.821 datasets: clon git sin datos de los espejos OpenNeuroDatasets.
   - Se suman 9.442 personas cuyos datos solo están en `derivatives/`.
2. **Revisión experta.** Reglas manuales para 729 datasets no-EEG con señales clínicas, más las 195 reglas de EEG v1.
   - Los demás se etiquetan como "sano" (dxStatus de OpenNeuro) o "presunto sano".
3. **Segunda pasada.** Lectura de los archivos `phenotype/` de los datasets dudosos, como NIMH EDB o los K-SADS de NIMH, y búsqueda de términos clínicos en los títulos de los datasets automáticos.
4. **Normalización.** 110 categorías con códigos SNOMED CT verificados en Snowstorm.
5. **Deduplicación y emparejamiento multimodal.**
   - Hash de contenido.
   - Metadatos idénticos: duplicados, derivados y cohortes.
   - IDs coincidentes dentro de una cohorte; por ejemplo, ORHA tiene el EEG y la fMRI de las mismas 43 personas en dos datasets.

## Resultados principales

- **89.243 personas únicas** contadas.
  - 45.718 con dos o más modalidades.
  - 1.619 con dos o más modalidades funcionales: PET+fMRI 722, EEG+fMRI 671, fMRI+fNIRS 70, EEG+MEG 45…
- **Condiciones con más personas únicas** (mínimo–máximo):

| Condición | Personas | Detalle |
|---|---|---|
| Epilepsia | 1.673–2.432 | +442 en IDEAS sin grupo por persona; casi todas con iEEG |
| Ictus | 1.557 | |
| Párkinson | 646–1.029 | EEG hasta 789, MRI 220 |
| Glioblastoma | 381 | |
| TDAH | 258–263 | |
| Esquizofrenia | 195 | |
| Ansiedad | 194–197 | |
| TCE | 187 | |
| Autismo | 172–223 | |
| Depresión mayor | 157–186 | |

## Verificación

- 17 de 18 datasets clínicos coinciden exactamente con las cifras del README o del artículo.
- El que no coincide, ds001907, tiene a los 21 pacientes con párkinson solo en `derivatives/`. Ya están incluidos gracias al inventario de derivados.
- Muestra aleatoria de 20 datasets automáticos: 19 correctos. El fallo, un iEEG de epilepsia, quedó corregido en la segunda pasada. La muestra detectó además un derivado simulado y un duplicado, ambos corregidos.

## Limitaciones conocidas

- "presumed_healthy" es una presunción.
- Muchos estudios clínicos clásicos (ABIDE, ADHD-200, COBRE, PPMI, ADNI) no están en OpenNeuro. Se cubrirán en la fase de fuentes externas.
- 3.148 personas `unresolved`: el grupo existe, pero no es público por participante. Por ejemplo, IDEAS tiene 442 pacientes con epilepsia y 100 controles en figshare.
- Los duplicados re-convertidos (archivos distintos, mismas personas) solo se detectan si coinciden los metadatos.

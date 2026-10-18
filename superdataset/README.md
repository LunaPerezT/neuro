# superdataset · OpenNeuro humano unificado

Inventario BIDS de los 1.821 datasets humanos públicos de OpenNeuro, sin descargar datos de imagen. Incluye:

- personas vinculadas entre datasets y modalidades;
- fenotipo clínico armonizado por participante, con códigos SNOMED CT.

La documentación de las tablas resultantes está en [`pheno/out/LEEME.md`](pheno/out/LEEME.md).

## Regenerar (en este orden)

```bash
pip install -e ../openneuro-mcp httpx
python census.py                                  # census_all.json, meta/census_human.json, ids_human.txt
python meta/fetch_metadata.py meta/census_human.json   # meta/raw/<ds>/: participants, README, description
python meta/extract_profiles.py                   # meta/profiles.jsonl: perfil de etiquetas + triaje
python inventory.py ids_human.txt 8               # inventory/: recordings.csv, subjects.csv (clones git sin blobs)
python link_people.py                             # linked/: global_id por persona (hash git-annex compartido)
python pheno/fetch_phenotype.py ids_human.txt     # meta/raw_extra/<ds>/: phenotype/ y metadatos de nivel superior
python pheno/inventory_derivatives.py ids_human.txt   # inventory/derivative_subjects.csv
python pheno/meta_dedup.py                        # pheno/out/metadata_duplicate_candidates.csv
python pheno/build_pheno.py                       # pheno/out/participants.csv, datasets.csv, ranking.csv
python pheno/filter_recordings.py                 # inventory/recordings_kept.csv (regla de MRI estructural)
python pheno/finalize.py                          # pheno/out/conditions.csv + neuro_openneuro.sqlite
```

Las carpetas de trabajo (`inventory/`, `linked/`, `meta/raw*`, unos 200 MB) no se suben al repositorio. Solo se versionan `pheno/out/*.csv` y `LEEME.md`.

## Ideas clave

- **Deduplicación y vinculación de personas.** Las claves git-annex llevan el SHA-256 del contenido: dos sujetos que comparten al menos dos archivos idénticos son la misma persona. A esto se suman:
  - cohortes enlazadas por ID (Jaccard ≥ 0,5);
  - duplicados por metadatos: README, nombre y multiconjunto de edad y sexo.
- **Fenotipo.** Las reglas expertas de 924 datasets están en `pheno/rules_eeg.py` y `pheno/rules_ext.py`, y cada etiqueta guarda su valor original y su fuente. El resto de datasets se marca como "sano" o "presunto sano".
- **Regla de MRI estructural.** La anatomía solo se conserva si la misma persona tiene otra técnica: fMRI, dMRI, ASL, EEG, MEG, iEEG, PET o fNIRS.
- **Recuentos.** Se dan entre un mínimo y un máximo (`ranking.csv`), porque los solapamientos de cohortes sin IDs comunes no se pueden resolver del todo.

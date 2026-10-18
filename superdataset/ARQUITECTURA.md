# Superdataset BIDS unificado de neurociencia humana: arquitectura (v0.1)

## Objetivo

Reunir en un único recurso todos los datos públicos de neurociencia humana, sin duplicados:

- Cada participante asignado a su estudio.
- Emparejado con sus otras modalidades cuando el estudio las tiene.
- Descrito en BIDS con toda la información disponible: diagnóstico, escalas, medicación, tareas y parámetros técnicos.

## Principios

1. **No copiar datos, apuntar a ellos.** Los archivos siguen en su repositorio de origen. El superdataset guarda punteros (DataLad/git-annex) y metadatos BIDS armonizados, y los datos se descargan solo cuando un análisis los pide. Así no hay coste de almacenamiento ni problemas de redistribución.
2. **Una persona, una vez.** Cada conjunto de personas aparece una sola vez. Los duplicados se detectan con evidencia (hash de contenido, DOI, participantes) y se registran, no se borran.
3. **Trazabilidad total.** Cada etiqueta guarda su valor original, su fuente y su nivel de confianza.
4. **Solo humanos** en esta versión.
5. **MRI estructural solo como apoyo.** Un T1/T2/FLAIR se conserva únicamente si la misma persona tiene otra técnica (fMRI, dMRI, ASL, EEG, MEG, iEEG, PET o fNIRS). Lo retirado queda listado en `removed_structural_only.csv`.

## Fuentes y orden de incorporación

| Fase | Fuente | Formato | Cómo se incorpora |
|---|---|---|---|
| 1 | OpenNeuro (1.911 datasets públicos) | BIDS nativo | Inventario de archivos por clonado git sin datos |
| 2 | NEMAR, EEGDash, Hugging Face | Espejos de OpenNeuro | Solo se registran como espejos: no aportan datos nuevos |
| 3 | Publicaciones (PubMed/PMC, bioRxiv) | Variable | Se extrae de cada artículo la sección de disponibilidad de datos para encontrar Zenodo, OSF, Figshare, Dryad y repositorios institucionales |
| 4 | Zenodo / OSF / Figshare / Dryad | No BIDS | Conversión a BIDS (sidecars y estructura) con punteros al archivo original |
| 5 | Datos con acuerdo de uso (HBN, etc.) | BIDS + DUA | Solo metadatos públicos y enlace al procedimiento de acceso |

## Deduplicación (por orden de fuerza de la evidencia)

1. **Contenido idéntico.** En OpenNeuro, cada archivo grande es un puntero git-annex cuyo identificador contiene el SHA-256 del contenido. Dos datasets que comparten esos identificadores comparten grabaciones exactas. Validado: detecta 171 de 173 archivos idénticos entre ds007823 y ds008082.
2. **Mismo DOI de dataset o de artículo.**
3. **Mismos participantes:** `participants.tsv` idéntico, o coincidencia del multiconjunto de edad y sexo.
4. **Misma persona en estudios distintos** (mismo laboratorio, misma muestra, tareas diferentes): se agrupan en una *cohorte* y se cuentan una sola vez.

## Modelo de datos (Supabase / Postgres)

- `source`: plataforma de origen.
- `dataset`: id de origen, versión, DOI, licencia, acceso, modalidades, tamaño, `duplicate_of` y evidencia.
- `study`: protocolo o muestra que agrupa datasets, aunque estén en plataformas o modalidades distintas, con su DOI principal.
- `participant`: ID global estable (`sub-NB000001`…), estudio y cohorte.
- `participant_source`: correspondencia participante global ↔ (dataset, ID original).
- `phenotype`: edad, sexo, condición, código SNOMED, rol, fuente de la etiqueta, confianza, valor original, medicación y escalas (JSON con nombres normalizados).
- `session`: participante, sesión y edad en esa sesión.
- `recording`: participante, sesión, tipo de dato (eeg/meg/ieeg/anat/func/dwi/pet/nirs…), tarea original y normalizada (Cognitive Atlas), entidades BIDS, hash de contenido, URL y parámetros técnicos (frecuencia de muestreo, canales, referencia, TR, campo magnético…).
- Vocabularios: `condition_vocab` (SNOMED CT) y `task_vocab` (Cognitive Atlas).

## Superdataset BIDS (GitHub)

- **Nivel superior:**
  - `dataset_description.json`, con `SourceDatasets` y los DOI de todo lo incluido.
  - `participants.tsv`/`.json` armonizados, con `TermURL` a SNOMED en los niveles de diagnóstico.
  - Tablas de correspondencia.
- **Subdatasets DataLad:** los repositorios originales de OpenNeuro, mantenidos por OpenNeuro y sin copiar nada.
- **Vistas materializables:** un script genera bajo demanda un dataset BIDS listo para analizar con una selección, por ejemplo "todo el EEG en reposo de párkinson y controles". Renombra a IDs globales, armoniza sidecars y crea punteros a los archivos originales con `datalad addurls`.

## Trabajo previo relacionado (y en qué se diferencia)

| Recurso | Qué hace | Qué le falta |
|---|---|---|
| DataLad `///openneuro` | Ya agrega OpenNeuro como subdatasets | No armoniza fenotipos, no deduplica y no incluye otras fuentes |
| EEGDash / NEMAR | Catálogo de EEG/MEG con etiquetas por dataset | Sin fenotipos por participante, sin MRI/fMRI y sin fuentes externas |
| Brain-OF y otros modelos fundacionales | Combinan fMRI, EEG y MEG para entrenar | No publican un recurso armonizado por participante |

## Fases

1. Inventario de OpenNeuro y emparejamiento multimodal. **Hecho**: 1.821 datasets, más 9.442 personas con datos solo en `derivatives/`.
2. Deduplicación y estudios. **Hecho**:
   - Por hash de contenido.
   - Por metadatos (README, nombre, edad y sexo): duplicados, derivados y cohortes.
   - Por IDs dentro de una cohorte.
3. Fenotipos de todas las modalidades. **Hecho** (v1): 110 condiciones SNOMED y 84.267 personas únicas tras retirar la MRI solo estructural. Ver `fenotipos_openneuro_v1.md`.
4. Parámetros técnicos y tareas.
5. Cola larga por publicaciones.
6. Carga en Supabase y publicación del superdataset en GitHub.

## Repositorio

Código y tablas en https://github.com/LunaPerezT/neuro (sin licencia).

## Pendiente de la usuaria

- Aprobar la creación del proyecto en Supabase (puede tener coste).

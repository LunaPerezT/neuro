# Anotación por participante del EEG público de OpenNeuro (v1, 17-10-2026)

Base de datos de los **463 datasets públicos de EEG** de OpenNeuro. Cada participante con datos de EEG está etiquetado con su condición clínica, normalizada y con código SNOMED CT cuando existe.

## Archivos

| Archivo | Contenido |
|---|---|
| `neuro_eeg.sqlite` | Las cuatro tablas en una base SQLite |
| `participants.csv` | Una fila por persona y dataset (26.699 filas) |
| `datasets.csv` | Una fila por dataset: condiciones, cohorte, duplicados, avisos, intervención y notas |
| `conditions.csv` | Vocabulario de condiciones con código SNOMED CT y tipo de correspondencia |
| `ranking.csv` | Condiciones ordenadas por personas únicas, con cotas mínima y máxima |
| `annotation_rules.json` | Reglas de anotación por dataset, con su justificación |
| `scripts/` | Código para reproducir todo desde cero |

## Campos clave de `participants.csv`

- `condition`: clave normalizada (por ejemplo `PD`, `AD`, `HEALTHY`). La etiqueta completa está en `conditions.csv`.
- `role` puede tomar estos valores:
  - `patient`
  - `control`: sano dentro de un dataset con pacientes
  - `healthy`: sano en un estudio no clínico
  - `presumed_healthy`: sin etiquetas clínicas en ninguna fuente
  - `mixed_community`: muestra comunitaria con diagnósticos no compartidos, como Healthy Brain Network
  - `unknown`
  - `excluded`
- `label_source` indica de dónde sale la etiqueta: una columna del `participants.tsv`, el prefijo del ID del sujeto, un umbral sobre una escala (BDI ≥ 13), la lista de IDs del README o el dataset completo.
- `raw_label`: el valor original tal cual, para poder auditar cada decisión.
- `confidence`: high, medium o low.
- `counted`: es falso en duplicados exactos, animales, fantomas y datos marcados por sus autores como no aptos.

## Método

1. **Censo.** Lista de los 463 datasets de EEG desde la API de OpenNeuro, con el servidor MCP `openneuro-mcp`.
2. **Metadatos.** `participants.tsv`, `participants.json`, `dataset_description.json` y README de cada dataset, descargados del espejo OpenNeuroDatasets en GitHub.
3. **Triaje.** Se revisan a mano los 178 datasets con columnas de grupo, códigos de grupo en los IDs o términos clínicos en el README. Otros 268 se etiquetan automáticamente: sanos si OpenNeuro declara "Healthy / Control" y "presumed_healthy" en el resto.
4. **Segunda pasada.** Revisión de los títulos de todos los datasets automáticos. Detectó Healthy Brain Network, obesidad, misofonia y dolor oncológico, que el filtro por palabras clave había pasado por alto.
5. **Solo personas con EEG.** Se cruza con la lista de sujetos que el validador de OpenNeuro detecta con datos. Se descartaron 556 filas de `participants.tsv` sin EEG, y se añadieron sujetos con EEG que no figuraban en ese archivo. Esto se aplicó a 360 datasets; en los otros 103, todos pequeños, se usa `participants.tsv`.
6. **Normalización** a 36 categorías (30 condiciones clínicas, 29 con participantes; más sanos, sin etiqueta, comunitarias, no informadas, animales y fantoma), con códigos SNOMED CT verificados contra el servidor Snowstorm. `conditions.csv` indica si la correspondencia es exacta, más amplia o aproximada.
7. **Solapamientos.** Hay datasets que comparten personas: el mismo laboratorio publica varias tareas con la misma muestra, o `participants.tsv` idénticos.
   - `cohort` agrupa los que tienen las mismas personas.
   - `overlap_group` agrupa los que *podrían* compartirlas.
   - El ranking da un mínimo (un máximo por grupo) y un máximo (un máximo por cohorte) de personas únicas.

## Verificación

- Doce datasets clínicos comprobados contra las cifras de su README o artículo: los doce coinciden.
- Ninguna etiqueta clínica se perdió al cruzar con la lista de sujetos con EEG.

## Limitaciones conocidas

- "presumed_healthy" es una presunción: estudios cognitivos sin información clínica explícita.
- En Healthy Brain Network los diagnósticos existen, pero requieren el acuerdo de uso de datos de HBN.
- ds008003 (misofonia: 23 pacientes y 32 controles según el README) no trae los grupos por participante.
- ds008768 (párkinson, 312 personas) tiene un aviso de los autores: no analizarlo hasta que publiquen una versión nueva.

# TDAH frente a controles: interacciones de orden superior en rs-fMRI (piloto)

Un nuevo análisis de conectómica funcional de orden superior sobre 5 estudios de OpenNeuro. **Los cinco estudios se preprocesan en tándem, con exactamente el mismo pipeline**, gratis: brainlife.io hace la parte cara y tu ordenador hace el resto.

## Muestra

| Estudio | TDAH | Controles | De dónde sale el preprocesado |
|---|---|---|---|
| ds000030 UCLA CNP (21–50 años) | 40 | 122 | brainlife: se importa directamente desde OpenNeuro |
| ds005754 NIMH (9–18 años, multieco) | 26 | 41 | brainlife: se sube desde tu PC |
| ds007116 Penn LEAD (8–16 años) | 67 | 33 | brainlife: se sube desde tu PC |
| ds007182 PRIMAS (19–30 años) | 13 | 29 | brainlife: se sube desde tu PC |
| ds008579 GRMPY (13–30 años, multibanda) | 18 | 42 | brainlife: se sube desde tu PC |
| **Total** | **164** | **267** | **431 personas** |

- **Grupo TDAH.** Incluye a las personas con TDAH como diagnóstico principal o como comorbilidad. La comorbilidad queda en `primary_condition` y `other_conditions`.
- **Controles.** Son los controles sanos del mismo estudio.
- **Otros pacientes.** Los pacientes de esos estudios con otros diagnósticos (229) quedan como prioridad 2. Sirven para los análisis de especificidad (TDAH frente a ansiedad, psicosis, bipolar…).
- **Sin T1w.** 7 personas de CNP no tienen T1w. Quedan fuera (prioridad 0).

Los datos de la muestra están en `data/`:

- `subjects.csv`: persona, grupo, edad, sexo, TR, sesión y ejecución elegidas, y etiqueta en brainlife.
- `files.csv`: archivos exactos que se descargan, con su tamaño.
- `sidecars.jsonl.gz`: metadatos BIDS ya heredados.
- `phenotype_<ds>.csv`: todas las escalas de cada persona.

## Reparto del trabajo

```
OpenNeuro ──(tu PC: 0,15-0,4 GB por persona, se borra al subir)──► brainlife.io
                                                   │  FreeSurfer 7.1.1 (~4 h) + fMRIPrep 20.2.3 (~3 h)
                                                   ▼  gratis, en paralelo, según la cola
tu PC ◄──(salidas de fMRIPrep: BOLD MNI 2 mm + confounds + máscara)──┘
  └─ parcelar (Schaefer-400 + Tian S3 = 450 regiones) → limpiar (36P + 0,01-0,08 Hz)
     → censurar FD > 0,5 mm → remuestrear a TR 2 s → métricas de orden superior
     → guardar unos 3 MB por persona → borrar lo descargado
```

- **Espacio en disco.** Bastan unos 10 GB libres: en ningún momento hay más de 1 o 2 personas descargadas. El resultado final ocupa unos 2 GB.
- **Tu ordenador.** Se usa unos 7 s de cálculo por persona y, sobre todo, conexión: unos 67 GB de subida a brainlife y unos 150–250 GB de bajada de salidas de fMRIPrep, repartidos en días. GRMPY es lo más pesado (1.114 volúmenes por persona): la parcelación lee el BOLD por bloques para no pasar de unos 2 GB de RAM.
- **Coste.** 0 €.

## Paso 1 · Preparar tu ordenador (una vez)

La herramienta de brainlife (`bl`) solo funciona en Linux. En Windows se usa WSL, que Docker Desktop normalmente ya ha instalado.

1. Abre PowerShell y escribe `wsl -l -v`.
   - Si no aparece ninguna distribución Ubuntu, ejecuta `wsl --install -d Ubuntu` y reinicia.
2. Abre la aplicación **Ubuntu** y ejecuta:

   ```bash
   git clone https://github.com/LunaPerezT/neuro.git
   cd neuro/adhd-hoi/local
   ./setup_wsl.sh          # instala Node, brainlife CLI, entorno Python y pasa los tests
   source ~/neuro-env/bin/activate
   ```

3. Crea una cuenta gratuita en https://brainlife.io y ejecuta `bl login`. Con `bl login --ttl 30` la sesión dura 30 días.

## Paso 2 · Proyecto e importación en brainlife (web)

1. En **Projects → New project**, crea el proyecto `ADHD-HOI` (privado). Copia su ID de la URL (24 caracteres) en `local/config.json`, en `"brainlife_project"`.
2. Importa CNP:
   1. Ve a **Datasets** y busca `ds000030`.
   2. Elige la versión `1.0.0`.
   3. Pulsa **Import** e indica el proyecto ADHD-HOI.
3. Sube los otros cuatro estudios desde Ubuntu:

   ```bash
   python stage_upload.py --dataset ds005754 --limit 2 --dry-run   # prueba sin subir: revisa ~/neuro_adhd/staging
   python stage_upload.py --limit 4                                 # primera prueba real
   python stage_upload.py                                           # el resto; puedes cortarlo y relanzarlo
   ```

   - Cada persona se sube con su ID global (`NB…`) para que los estudios no choquen.
   - Se suben solo el T1w, la primera sesión de reposo y su mapa de campo (Penn LEAD y PRIMAS: EPI de fase inversa; GRMPY: *phasediff* + magnitudes).
   - En ds005754 los 3 ecos se combinan antes de subir (combinación óptima ponderada por T2*). Sus JSON dan el mismo TE (42,2 ms) a los tres ecos, que es un error del dataset; se usan los TE del README: 14,8/28,4/42,0 ms. Si prefieres solo el eco medio, usa `"multiecho": "echo2"`.

## Paso 3 · Reglas de pipeline en brainlife (web, una vez)

En el proyecto, ve a **Pipelines → Add rule** y crea estas dos reglas:

**Regla 1: FreeSurfer**

- App: *Freesurfer 7.1.1* (brainlife.app.462). Configuración por defecto.
- Entrada t1: `neuro/anat/t1w`.
- Filtro de sujetos: para empezar, el contenido de `data/brainlife_filter_ds000030_priority1.txt` más `^NB` (las personas subidas). Puedes unirlos con `|`.

**Regla 2: fMRIPrep**

- App: *fMRIPrep - Volume Output* (brainlife.app.160).
- Configuración:
  - space = `MNI152NLin6Asym`
  - resolution = `res-2`
  - aroma = no
  - skipbidsvalidation = sí
- Entradas:
  - t1w = `neuro/anat/t1w`
  - fmri = `neuro/func/task` con *datatype tag* `rest`
  - freesurfer = salida de la regla 1
  - fmap = `neuro/fmap` (opcional)
- Etiqueta de salida: `adhd-hoi`.

> **Antes de lanzar las reglas para todo el mundo**, limita el filtro de sujetos a 2 o 3 personas (por ejemplo `^(10159|10171)$`) y comprueba que el informe HTML de fMRIPrep sale bien. Las reglas reenvían solas a quien vaya faltando, así que basta con ampliar el filtro después.

**Velocidad.** brainlife ejecuta muchos trabajos a la vez en recursos compartidos. La duración media por persona es de unas 4 h (FreeSurfer) más unas 3 h (fMRIPrep). El total depende de la cola: cuenta con días, no con horas. Si un trabajo falla (la tasa de éxito ronda el 70 %), pulsa **Rerun** en *Processes* o revisa el log.

## Paso 4 · Análisis en tu ordenador (puede ir a la vez que brainlife)

```bash
python process.py --refresh                 # quien ya tenga fMRIPrep terminado en brainlife
python process.py --xcpd-benchmark          # opcional y se puede hacer ya: analiza también el XCP-D de los autores de GRMPY
python status.py --refresh                  # progreso por estudio y grupo, y últimos errores
```

- Relánzalo cuando quieras (por ejemplo, cada noche): solo procesa a quien falte y nunca repite a nadie.
- Los resultados quedan en `~/neuro_adhd/results/<estudio>/sub-<id>/`:
  - `metrics.npz`
  - `timeseries_native.npy`: series limpias de 450 regiones, para reanalizar sin volver a descargar nada.
  - `fd_native.npy`
  - `qc.json`
- La tabla resumen está en `~/neuro_adhd/results/summary.csv`.
- **Control externo con GRMPY.** Los autores de GRMPY publicaron su propio preprocesado (fMRIPrep 25.1.4 + XCP-D 0.12.0, ds008601). No se usa en el análisis principal, pero `--xcpd-benchmark` lo pasa por las mismas métricas en `results/xcpd_benchmark/`. Comparar sus 60 personas con las nuestras mide cuánto depende el resultado del preprocesado.

## Métricas que se calculan (`local/hoi_metrics.py`)

| Métrica | Qué captura |
|---|---|
| FC de Pearson (450 × 450) | Conectividad por pares clásica: es la referencia |
| **O-información** de los 15,1 millones de tripletes | Si cada triplete está dominado por sinergia (O < 0) o por redundancia (O > 0). Se resume por región, por triplete de redes de Yeo y en sus extremos |
| **S-información** | Volumen total de interdependencia de orden superior |
| O-información y S-información de redes completas y de pares de redes | Orden superior más allá de los tripletes (n-pletes de 20–110 regiones) |
| **ΦID-MMI** por pares, con retardo 1 | 16 átomos de información integrada. Se guardan la sinergia (sts) y la redundancia (rtr) en matrices 450 × 450, más el gradiente sinergia–redundancia por región |
| Versión con T igualada (120 volúmenes) | Corrige el sesgo del estimador por la longitud de la serie |

- Todos los estimadores son gaussianos de forma cerrada, con transformación cópula y corrección analítica de sesgo.
- Unos 7 s por persona.
- Validación (`local/tests`):
  - la O-información coincide con su definición a partir de entropías;
  - ΦID coincide con la implementación de referencia `phyid` (Imperial-MIND-lab);
  - los sistemas sinérgicos y redundantes dan el signo esperado;
  - el pipeline completo se prueba sobre volúmenes sintéticos.

## Decisiones de armonización

- **Mismo preprocesado en todos los estudios.** FreeSurfer 7.1.1 + fMRIPrep 20.2.3 en brainlife, salida en MNI152NLin6Asym a 2 mm, y la misma limpieza local.
- **Mismo atlas en todos los estudios.** Schaefer-400 de 7 redes en FSL-MNI 2 mm, más Tian S3 (450 regiones).
- **Misma limpieza que XCP-D "linc".** 36P más paso banda de 0,01–0,08 Hz, sin censura en la regresión. La censura con FD > 0,5 mm y el remuestreo a TR = 2 s se aplican igual en todos los estudios.
  - Esto es necesario porque los TR van de 0,5 a 2 s, y el retardo de ΦID debe significar lo mismo en todos.
- **Diferencias que quedan.** Solo las de adquisición (escáner, TR, multibanda, multieco, duración). Son constantes dentro de cada estudio: el análisis de grupo compara TDAH con los controles del mismo estudio y después metaanaliza entre estudios, con ComBat y el movimiento (FD) como covariable. Así no se confunden con el diagnóstico.
- **Control de calidad.** Requisitos:
  - al menos 4 min retenidos;
  - FD medio ≤ 0,5 mm;
  - al menos 430 regiones con cobertura.

  Quien no los cumpla queda marcado (`qc_pass`), no se borra.

## Regenerar la muestra (no hace falta en tu PC)

`select_subjects.py` y `make_sidecars.py` generan `data/`. Necesitan el inventario del superdataset y los clones git de OpenNeuro.

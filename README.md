# neuro

Recurso unificado de datos públicos de neurociencia humana, y primer análisis que lo usa.

| Carpeta | Qué es | Estado |
|---|---|---|
| [`openneuro-mcp/`](openneuro-mcp/) | Servidor MCP de solo lectura para OpenNeuro: censo, búsqueda, participantes, archivos, GraphQL | Terminado. Lo usan los demás scripts |
| [`superdataset/`](superdataset/) | Los 1.821 datasets humanos de OpenNeuro: inventario BIDS, personas vinculadas entre datasets y fenotipo clínico armonizado (SNOMED CT) | v1.1 terminada. Las tablas están en `superdataset/pheno/out/` |
| [`adhd-hoi/`](adhd-hoi/) | Piloto: TDAH frente a controles con interacciones de orden superior (O-información, ΦID) en rs-fMRI. Son 431 personas de 5 estudios, preprocesadas en brainlife.io y analizadas en local | Código probado. Falta ejecutarlo (pasos 1–4 de su README) |

Requisitos: Python ≥ 3.10. Cada carpeta tiene su README con los pasos para reproducirla.

Sin licencia: todos los derechos reservados por la autora salvo indicación contraria.

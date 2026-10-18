# neuro

Recurso unificado de datos públicos de neurociencia humana (EEG, MEG, iEEG, MRI, fMRI, dMRI, PET, fNIRS) con fenotipos armonizados por participante y personas vinculadas entre datasets y modalidades. Construido con agentes (Deep Agents + LangGraph + LangSmith) y servidores MCP.

| Carpeta | Qué es |
|---|---|
| `openneuro-mcp/` | Servidor MCP de OpenNeuro: búsqueda, censo masivo, participantes, archivos y GraphQL de solo lectura |
| `annotation-eeg/` | Anotación clínica por participante de los 463 datasets de EEG de OpenNeuro (v1) |
| `superdataset/` | Inventario BIDS de los 1.821 datasets humanos, vinculación de personas (hash de contenido + cohortes) y fenotipos de todas las modalidades (`pheno/out/LEEME.md`) |
| `adhd-hoi/` | Piloto TDAH vs controles: interacciones de orden superior (O-información, ΦID) en rs-fMRI de 431 personas; preprocesado en brainlife.io + análisis local reanudable |

Los ficheros grandes (inventario de 159 MB, base SQLite) no están en el repositorio; se regeneran con los scripts.

Sin licencia: todos los derechos reservados por la autora salvo indicación contraria.

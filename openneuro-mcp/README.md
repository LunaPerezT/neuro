# openneuro-mcp

Servidor MCP para [OpenNeuro](https://openneuro.org), el archivo abierto de datos de neuroimagen en formato BIDS (MRI, fMRI, EEG, MEG, iEEG, PET). Está pensado para que un agente pueda **hacer un censo del archivo completo y bajar al nivel de cada participante**: quién es paciente, quién es control y cómo lo indica cada dataset.

Todas las herramientas son de solo lectura.

## Herramientas

| Herramienta | Para qué sirve |
|---|---|
| `openneuro_census` | Una fila por dataset público (sujetos, modalidades, estado diagnóstico, especie, tareas, edades, DOI del artículo) y recuentos agregados de datasets y sujetos por modalidad, diagnóstico, especie, tarea o etiqueta de grupo por participante. Tiene caché de 6 horas. |
| `openneuro_search_datasets` | Búsqueda por palabras clave y filtros: modalidad, diagnóstico, tarea, especie, edad y número de sujetos. |
| `openneuro_get_dataset` | Ficha de un dataset: versiones, modalidades, sujetos, grupos según el validador BIDS, licencia, autores, financiación, DOIs, artículos relacionados, derivados (fMRIPrep…) y README. |
| `openneuro_get_participants` | `participants.tsv` cruzado con su diccionario `participants.json`. Por columna da descripción, unidades, códigos, recuentos o rango. Detecta columnas de grupo o diagnóstico y **códigos ocultos en los IDs** (`sub-pd03` / `sub-hc01`). |
| `openneuro_list_files` | Navega carpetas de una versión, con tamaños y URLs. |
| `openneuro_read_file` | Lee archivos de texto: JSON de metadatos, `events.tsv`, README, `phenotype/`. Rechaza los binarios. |
| `openneuro_get_download_info` | Tamaño del dataset y comandos listos para descargarlo (openneuro-py, DataLad, AWS S3), con filtros para bajar solo una parte. No descarga nada por sí misma. |
| `openneuro_count_participants` | Total de participantes en OpenNeuro, global o por modalidad. |
| `openneuro_graphql` | Consulta GraphQL libre de solo lectura para lo que no cubren las demás. Las mutaciones se rechazan. |

**Respaldo sin conexión a OpenNeuro.** Si `openneuro.org` no responde, `get_dataset`, `get_participants` y `read_file` leen los metadatos del espejo [OpenNeuroDatasets en GitHub](https://github.com/OpenNeuroDatasets). Ese espejo solo tiene la última versión y los archivos de texto. La búsqueda, el censo y el listado de carpetas sí necesitan la API.

## Instalación

```bash
pip install git+https://github.com/LunaPerezT/openneuro-mcp.git
# o, desde una copia local:
pip install -e .
```

Funciona con las versiones 1.x y 2.x del SDK de MCP para Python, así que convive con `langchain-mcp-adapters`.

### Claude Desktop

Añade esto a `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openneuro": {
      "command": "openneuro-mcp"
    }
  }
}
```

Si `openneuro-mcp` no está en el PATH de la app, usa la ruta completa, por ejemplo `/Users/<tu-usuario>/.venv/bin/openneuro-mcp`.

### Deep Agents / LangGraph

```python
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import create_deep_agent

client = MultiServerMCPClient(
    {"openneuro": {"command": "openneuro-mcp", "args": [], "transport": "stdio", "env": dict(os.environ)}}
)
tools = await client.get_tools()
agent = create_deep_agent(model="anthropic:claude-sonnet-5-5", tools=tools, system_prompt="...")
```

Pasa `env`: por defecto el lanzador stdio entrega al servidor un entorno mínimo y se pierden los ajustes de proxy. El ejemplo completo, con un subagente que revisa participantes, está en [`examples/deep_agent_census.py`](examples/deep_agent_census.py).

### Como servicio HTTP

```bash
openneuro-mcp --transport streamable-http --port 8000   # endpoint: http://localhost:8000/mcp
```

## Configuración

| Variable | Por defecto | |
|---|---|---|
| `OPENNEURO_GRAPHQL_URL` | `https://openneuro.org/crn/graphql` | Endpoint de la API |
| `OPENNEURO_BACKEND` | `auto` | `auto` (API y, si falla, GitHub), `graphql` o `github` |
| `OPENNEURO_TIMEOUT` | `60` | Segundos por petición |
| `OPENNEURO_MAX_CONCURRENCY` | `4` | Peticiones simultáneas, para no saturar OpenNeuro |

## Pruebas

```bash
pip install -e ".[dev]"
pytest -m "not live"     # sin red: API simulada con el esquema GraphQL oficial
pytest -m live           # prueba real del respaldo vía GitHub
```

Las pruebas sin red ejecutan cada consulta contra una transcripción del esquema oficial de OpenNeuro (`tests/openneuro_schema.graphql`, tomada de `OpenNeuroOrg/openneuro`). Un nombre de campo o un tipo de variable incorrecto falla igual que fallaría contra la API real.


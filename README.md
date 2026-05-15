# Bridge API (OUTPUT/backend)

Sirve las apps en `OUTPUT/frontend` y `OUTPUT/admin-panel` con **datos reales** del mismo MongoDB que usa el CLI `masaas`:

| Endpoint | Datos |
|----------|--------|
| `GET /health` | Estado API + ping Mongo |
| `GET /v1/integrations/status` | `.env`: Mongo, Ollama (`/api/tags`), flags Anthropic/Tavily (sin exponer claves) |
| `GET /v1/metrics/overview` | Agregados sobre `executions`, `pipeline_runs`, `agent_memory` |
| `GET /v1/tenants/current` | Última ejecución (`goal`, `mode`, `workspace_path`) |
| `GET /v1/executions/recent` | Lista reciente de corridas |
| `GET /v1/forma/*` | Perfil, plantillas de cuerpo, plan diario, check-in, calendario |
| `GET /v1/blog` | Artículos del blog (MongoDB, con seed automático al arrancar) |

Lee **`MONGO_URI` y `MONGO_DB`** del archivo **`.env` en la raíz del repositorio** (mismo que `masaas`).

## Ejecutar

```powershell
cd OUTPUT\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Requisitos: Mongo accesible (`docker-compose up -d` en la raíz del monorepo).

Documentación interactiva: http://127.0.0.1:8000/docs

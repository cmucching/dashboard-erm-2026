# Dashboard ERM 2026 — pipeline de datos ONPE

Descarga cada hora los resultados de las Elecciones Regionales y Municipales 2026 desde
<https://resultadoelectoral.onpe.gob.pe> y los publica como JSON/CSV en `data/`.

**Fuente:** ONPE. Los datos se reproducen con atribución; no son oficiales hasta la proclamación del JNE.

## Flujo
GitHub Actions (cron horario) → `scraper/onpe_scraper.py` (Playwright) → control de calidad →
commit solo si cambian los datos → Netlify se despliega desde el repo (o por build hook).

## Archivos en `data/`
| Archivo | Contenido |
|---|---|
| `regional_departamentos.json` | Gobernadores: totales y candidatos por departamento |
| `municipal_provincias.json` | Alcaldías provinciales |
| `municipal_distritos.json` | Alcaldías distritales (incremental por provincia cambiada) |
| `results.csv` | Primer y segundo puesto regional (formato de `/api/results.csv`) |
| `meta.json` | Hora UTC, huella, conteos y problemas de control de calidad |

## Reglas
- Ritmo bajo (4 solicitudes concurrentes, pausas de 120–350 ms).
- No se evaden CAPTCHAs ni defensas anti-bot: ante 401/403 o HTML, el proceso termina con código 3 y se conservan los últimos datos.
- Si falla el control de calidad (código 2) no se publica nada.

## Uso local
```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m unittest discover -s tests -v
python scraper/onpe_scraper.py --out data --smoke
```

## Pendiente
Fase 2: mesas y actas. Integración del código fuente del sitio Netlify en `site/`.

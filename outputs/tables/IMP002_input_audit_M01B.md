# Auditoría de inputs M01B — evidencia real

Generado: 2026-10-23, sesión de diagnóstico (lectura únicamente, `data/raw/` no fue modificado).
Dataset: DS01 / EXP03 (release real del grupo, verificado por hash en T1).

| SOURCE | PATH | ROWS | KEY FIELDS | UNITS | STATUS | POSITIONING STATUS | ROLE IN M01B | OBSERVATIONS |
|---|---|---|---|---|---|---|---|---|
| collar | data/raw/collar.csv | 32 | hole_id, x, y, z, azimuth_deg, dip_deg, final_depth_m | m (x,y,z,depth); deg (az,dip) | AVAILABLE | N/A (es la fuente de posición) | Extensión/origen del grid (T2) | Reutilizado tal cual de M01 |
| survey | data/raw/survey.csv | ver M01 | hole_id, depth_m, azimuth_deg, dip_deg | m; deg | AVAILABLE | N/A (fuente de orientación) | Trayectoria (vía desurvey.py) | Reutilizado tal cual de M01 |
| assay | data/raw/assay.csv | 3619 | hole_id, from_m, to_m, length_m, cu_pct, mo_pct, au_gt | m; % | AVAILABLE | NOT POSITIONED (ver nota) | Input directo del compositado | mo_pct y au_gt = 0.0 en el 100% de los registros; no utilizables |
| lithology | data/raw/lithology.csv | 95 | hole_id, from_m, to_m, length_m, lith_code | m; código | AVAILABLE | NOT POSITIONED | Límite de contacto para el compositado | Códigos: REG(36) DIO(27) POR(22) BRX(8) AIR(2) — código AIR requiere verificación |
| density | data/raw/density.csv | ver M01 | hole_id, from_m, to_m, length_m, density_t_m3 | m; t/m3 | AVAILABLE | NOT POSITIONED | Disponible para análisis futuro, no obligatorio en M01B | Sin procesar aún |
| alteration | data/raw/alteration.csv | 0 | — | — | EMPTY | N/A | Ninguno en esta etapa | INFO — valid empty source (archivo existe, 0 filas, no bloquea M01B) |
| topography | NO ENCONTRADA | — | — | — | MISSING | — | Necesaria para P3 (T2), no para compositado M01B | No existe en `data/raw/`, `data/PL00/` ni en la carpeta `Data/` compartida fuera del repo. Pendiente de solicitar al docente. |
| M01 outputs (desurvey/positioning) | src/m01/desurvey.py, src/m01/positioning.py | — | — | — | IMPLEMENTED + TESTED (fixtures sintéticos) | **NO GENERATED** contra el dataset real | Reutilizable como función, no como tabla ya calculada | `main.py` solo ejecuta loader+validator; desurvey/positioning no se han corrido contra `data/raw/` real, no existe ningún CSV de trayectoria/posición persistido en `data/processed/` |

## Qué falta (AVAILABLE NOW / NEEDS PROCESSING / MISSING / UNKNOWN)

- **AVAILABLE NOW:** collar, survey, assay, lithology, density (sin procesar), alteration (vacío válido).
- **NEEDS PROCESSING:** posicionamiento XYZ real de assay/lithology (código existe, no se ha ejecutado contra `data/raw/`).
- **MISSING:** archivo de topografía — no está en ningún lugar accesible del repo ni de la carpeta de datos compartida.
- **UNKNOWN:** significado exacto del código litológico `AIR` (solo 2 registros) — no está en `data_dictionary.csv` con una definición explícita verificada en esta sesión.

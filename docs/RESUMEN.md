# 📄 Resumen ejecutivo — Limpiador-Deduplicador de CRM

## En una frase

Herramienta en Python (solo librería estándar) que limpia una base de contactos CSV:
detecta duplicados aunque solo coincida el **email o el teléfono**, los fusiona en un
**registro maestro**, deja un **rastro auditable** de cada eliminación y genera un
**informe HTML** — todo de forma **no destructiva**.

## El problema de negocio

Un CRM acumula el mismo cliente varias veces con datos ligeramente distintos (mayúsculas,
espacios, `+34`, erratas de dominio, un móvil mal tecleado). Consecuencia: el comercial
llama dos veces, las métricas mienten y el cliente recibe mensajes repetidos. Limpiarlo a
mano son horas; aquí son **milisegundos**.

## Cómo lo resuelve

1. **Normaliza** email y teléfono para poder compararlos (`Ana@X.com ` → `ana@x.com`).
2. **Agrupa** las filas que son la misma persona si comparten email **o** teléfono,
   resolviendo las cadenas de coincidencias con **union-find** (tiempo casi lineal).
3. **Fusiona** cada grupo en un registro maestro, rellenando huecos sin pisar datos buenos.
4. **Audita**: exporta qué se eliminó, con qué se fusionó y por qué.
5. **Informa**: panel HTML con métricas, motivos y empresas más sucias.

## Métrica principal

**% de duplicados eliminados** y **minutos de limpieza manual ahorrados** (≈ 8 s/fila,
normalizado por cada 1.000 filas). Sobre los datos de ejemplo: **8 de 16 filas eran
duplicados (50 %)**, eliminados al instante.

## Calidad

- **62 pruebas automáticas (pytest)** en 6 fases, incluidos casos difíciles (cadenas
  largas, orden, filas vacías, 3.000 filas de volumen).
- **Cero dependencias externas**: solo Python estándar.
- **No destructivo (GDPR):** el archivo de entrada nunca se toca; cada eliminación queda
  registrada con su motivo.

## Valor para una entrevista

Demuestra: normalización de datos, un algoritmo no trivial bien justificado (union-find),
pensamiento en casos límite, trazabilidad/GDPR, pruebas serias y documentación clara.

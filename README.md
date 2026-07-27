# 🧹 Limpiador-Deduplicador de CRM

> Herramienta en Python que convierte una lista de contactos **"sucia"** en una base
> limpia: detecta los duplicados que un humano no ve a simple vista —aunque solo coincida
> el email **o** el teléfono—, los **fusiona** en un único registro maestro, deja un
> **rastro auditable** de qué se eliminó y por qué, y genera un **informe visual**.
> Solo Python estándar, sin dependencias.

### 🔗 [**Ver la demo interactiva (online)**](https://aulazaro28110-prog.github.io/limpiador-deduplicador-crm/)

*Panel visual con las métricas de una ejecución real sobre datos de ejemplo — se abre en el navegador.*

---

## 🧭 El proyecto de un vistazo

```
CSV sucio  →  normaliza  →  agrupa (email O teléfono)  →  fusiona  →  audita  →  exporta
```

| Fase | Qué hace |
|------|----------|
| 1. Normalización | Pone email y teléfono en un formato común (minúsculas, sin `+34`, corrige `gmial.com`) |
| 2. Validación | Marca (no borra) filas con email o teléfono dudoso |
| 3. Detección | Agrupa duplicados aunque solo coincida **email O teléfono**, incluso en cadena |
| 4. Fusión | Combina cada grupo en un **registro maestro** (golden record) |
| 5. Auditoría | Exporta qué se eliminó, con qué se fusionó y **por qué** (GDPR) |
| 6. Informe | Panel HTML con métricas, motivos y ranking de empresas |

✅ **62 pruebas automáticas (pytest)** cubren las 6 fases, incluidos los casos difíciles.

---

## ❗ El problema

En cualquier CRM el mismo cliente acaba metido varias veces con datos ligeramente
distintos. Para una persona es obvio que son el mismo; para el ordenador no, porque las
mayúsculas, los espacios, el prefijo `+34` o una errata de dominio los hacen parecer
diferentes:

| nombre | email | teléfono |
|--------|-------|----------|
| Ana García | `ana@techcorp.com` | `+34 612 34 56 78` |
| ANA GARCIA | `Ana@TechCorp.com` | `612345678` |
| Ana G. | `ana@techcorp.com` | `666 66 66 66` ← otro móvil |

Las tres son la misma Ana. Sin limpiar, un comercial la llama tres veces, ensucia las
métricas y queda mal con el cliente.

## 💡 La idea clave (y lo que la hace potente)

La versión ingenua compara el dato "en bruto" y se le escapan los casi-duplicados. Esta
herramienta hace dos cosas:

1. **Normaliza antes de comparar.** `Ana@TechCorp.com` y `ana@techcorp.com ` pasan a ser
   la misma clave.
2. **Agrupa por coincidencia parcial.** Dos filas son la misma persona si comparten el
   email **O** el teléfono (no hace falta que coincidan los dos). Y como las coincidencias
   se encadenan (A comparte email con B, B comparte teléfono con C → A, B y C son la misma
   persona), se agrupan con **conjuntos disjuntos (union-find)** para no dejar a nadie suelto.

> 🧠 *Por qué union-find:* recorrer la base es prácticamente **O(n)** (cada operación es
> casi constante gracias a la compresión de caminos), así que aguanta cientos de miles de
> filas sin arrastrarse. Comparar todas las filas entre sí sería O(n²).

## 🆚 Modo normal vs. estricto

| | Normal (por defecto) | Estricto (`--estricto`) |
|---|---|---|
| Regla | misma persona si coincide email **O** teléfono | solo si coinciden email **Y** teléfono |
| Pilla | más duplicados reales (móvil mal tecleado, etc.) | menos, pero con cero falsos positivos |
| Cuándo | limpieza general de un CRM | bases donde un email se comparte (info@empresa) |

---

## 🚀 Uso

```bash
# Limpieza básica (genera contactos_limpios.csv)
python deduplicador.py leads_sucios_demo.csv

# Todo: fusión + auditoría + informe HTML + export Salesforce
python deduplicador.py leads_sucios_demo.csv --fusionar --auditoria --html --salesforce
```

Salida sobre los datos de ejemplo:

```
==================================================
🧹 LIMPIADOR-DEDUPLICADOR DE CRM
==================================================
📥 Contactos leídos:        16
🔁 Duplicados eliminados:   8
✅ Contactos únicos:        8
📊 % duplicados eliminados: 50.0%
⚠️  Filas con datos dudosos: 0
⏱️  Limpieza manual evitada: 2.1 min (133.3 por cada 1.000)
🧭 Modo de detección:       normal (email O teléfono)
🧩 Registros fusionados en maestro (golden record): sí
💾 Archivos generados:      contactos_limpios.csv, duplicados_eliminados.csv, contactos_salesforce.csv, informe.html
==================================================
```

### Opciones

| Opción | Para qué sirve |
|--------|----------------|
| `--salida ARCHIVO` | Nombre del CSV limpio (def: `contactos_limpios.csv`) |
| `--fusionar` | Combina cada grupo en un registro maestro (golden record) |
| `--auditoria` | Exporta `duplicados_eliminados.csv` (qué se quitó y por qué) |
| `--html` | Genera `informe.html` (panel visual para el navegador) |
| `--salesforce` | Exporta `contactos_salesforce.csv` listo para importar |
| `--estricto` | Modo antiguo: duplicado solo si coinciden email Y teléfono |
| `--delimitador ';'` | Fuerza el separador (por defecto se detecta `,` o `;`) |

El CSV de entrada solo necesita las columnas `email` y `telefono` (tolera mayúsculas, BOM y
separador `,` o `;`); puede tener más columnas, se conservan todas.

---

## 📂 Archivos que genera

| Archivo | Para qué sirve |
|---------|----------------|
| `contactos_limpios.csv` | Base depurada (con `--fusionar`, además fusionada) |
| `duplicados_eliminados.csv` | Cada duplicado, con qué maestro se fusiona y el **motivo** |
| `contactos_salesforce.csv` | Columnas `FirstName/LastName/Email/Phone/Company` para importar |
| `informe.html` | 📊 Panel visual con métricas, motivos y ranking de empresas |

## 📊 Métricas

- **% de duplicados eliminados** = duplicados ÷ total × 100.
- **Minutos de limpieza manual ahorrados** = filas × 8 s (estimación conservadora),
  normalizado a "por cada 1.000 filas" para poder comparar a cualquier escala.
- **Desglose por motivo**: cuántos duplicados se pillaron por email, por teléfono, por
  ambos o por enlace transitivo. Es la prueba de que la detección "parcial" aporta valor.

## 🔒 No destructivo (criterio GDPR)

Nunca se modifica ni borra el archivo de entrada; todo se escribe en archivos nuevos. Los
duplicados no desaparecen "en silencio": quedan en `duplicados_eliminados.csv` con su
motivo, para poder auditar cada decisión. Los datos de ejemplo son **sintéticos**.

---

## ✅ Pruebas

```bash
pytest -v
```

**62 pruebas** repartidas en 5 archivos dentro de `tests/`:

| Archivo | Cubre |
|---------|-------|
| `test_normalizacion.py` | email/teléfono normalizados, corrección de erratas, claves |
| `test_validacion.py` | regex de email y teléfono, filas dudosas |
| `test_deteccion.py` | agrupación por email/teléfono, transitividad, modo estricto |
| `test_fusion.py` | registro maestro, motivo del duplicado, auditoría |
| `test_io.py` | carga (separador/BOM/columnas), exportación, métricas, Salesforce |
| `test_dificil.py` | cadenas largas, orden, vacíos, volumen (3.000 filas) |

## 📁 Estructura

```
limpiador-deduplicador/
├── deduplicador.py          ← la herramienta (9 secciones: normaliza → informe)
├── tests/                   ← 62 pruebas (pytest)
│   ├── test_normalizacion.py · test_validacion.py · test_deteccion.py
│   └── test_fusion.py · test_io.py · test_dificil.py
├── conftest.py              ← deja que tests/ importe el módulo
├── docs/RESUMEN.md          ← resumen ejecutivo del proyecto
├── leads_sucios_demo.csv    ← datos de ejemplo con duplicados a propósito
├── requirements-dev.txt · .gitignore · LICENSE · README.md
```

## 🛠️ Decisiones técnicas

- **Normalizar antes de comparar** evita los falsos negativos de comparar el dato en bruto.
- **Union-find** resuelve la transitividad de "email O teléfono" en tiempo casi lineal; el
  representante de cada grupo es la primera fila (el maestro que se conserva).
- **Registro maestro (golden record):** el superviviente se rellena con los datos no vacíos
  de sus copias, sin pisar los buenos del original — *Master Data Management* básico.
- **Auditoría con motivo** (incluido el honesto `enlazado (transitivo)`): nada se borra sin
  dejar rastro.
- **Robustez de entrada:** autodetección de separador, tolerancia a BOM y a mayúsculas en
  las cabeceras, y error claro si faltan las columnas mínimas.

---

## 🛣️ Roadmap (posibles siguientes pasos)

- [ ] **Coincidencia difusa (fuzzy):** detectar duplicados que solo se *parecen* (nombres tecleados distinto, sin ningún dato normalizado en común), con un umbral de similitud.
- [ ] **Origen de datos directo:** leer desde la API del CRM en vez de un CSV exportado a mano.
- [ ] **Ejecución programada:** correr la limpieza de forma periódica para mantener la base siempre depurada.

---

## ⚠️ Limitaciones conocidas

- La detección agrupa por coincidencia **exacta tras normalizar** (email o teléfono). Dos filas de la misma persona que no compartan **ningún** dato normalizado (p. ej. dos móviles distintos y el email tecleado de dos formas no equivalentes) no se detectan como duplicado.
- La validación comprueba el **formato** del email y el teléfono, no que el buzón o la línea existan de verdad (eso requeriría verificación externa).

---

## 👤 Autor

**Álvaro Utazu Lázaro** · En formación como AI Engineer

- 📧 Email: aulazaro.28110@gmail.com
- 💼 LinkedIn: [alvaro-utazu-lázaro](https://www.linkedin.com/in/alvaro-utazu-lázaro-952255291)

Proyecto desarrollado con metodología asistida por IA ([Claude Code](https://claude.ai), Anthropic) como parte de un programa de aprendizaje práctico de ingeniería de software e IA.

---

## 📄 Licencia

Código **visible pero no libre** (*source-available*). Puedes ver, leer y ejecutar este proyecto para **evaluarlo**, pero queda prohibido copiarlo, modificarlo, redistribuirlo o reutilizarlo sin permiso escrito del autor. Consulta el archivo [LICENSE](LICENSE).

© 2026 Álvaro Utazu Lázaro. Todos los derechos reservados.

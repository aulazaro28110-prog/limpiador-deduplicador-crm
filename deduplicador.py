# -*- coding: utf-8 -*-
"""
Limpiador-Deduplicador de CRM
=============================
Convierte una lista de contactos "sucia" (con duplicados disfrazados por
mayúsculas, espacios, el prefijo +34 o erratas de dominio) en una base limpia,
fusiona la información de cada persona en un único "registro maestro", deja un
rastro auditable de qué se eliminó y por qué, y genera un informe visual.

Solo usa la librería estándar de Python (csv, re, argparse, html, os, sys,
datetime). Sin dependencias externas.

Uso básico:
    python deduplicador.py leads_sucios_demo.csv
    python deduplicador.py mi_base.csv --salida base_limpia.csv

Opciones avanzadas:
    --fusionar     Fusiona los duplicados en un registro maestro (golden record).
    --auditoria    Exporta 'duplicados_eliminados.csv' (qué se quitó y por qué).
    --html         Genera 'informe.html' (panel visual con métricas).
    --salesforce   Exporta 'contactos_salesforce.csv' listo para importar.
    --estricto     Modo antiguo: duplicado solo si coinciden email Y teléfono.
    --delimitador  Fuerza el separador del CSV (',' o ';'); por defecto se detecta.

Idea clave: dos filas son la MISMA persona si, tras normalizar, comparten el
email O el teléfono (no hace falta que coincidan los dos). Comparar el dato "en
bruto" dejaría escapar los casi-duplicados (Ana@X.com vs ana@x.com); por eso
primero se normaliza. Y como una cadena de coincidencias puede encadenar a tres
o más filas (A comparte email con B, B comparte teléfono con C), se agrupan con
un algoritmo de conjuntos disjuntos (union-find) para no dejar a nadie suelto.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from html import escape


# =============================================================================
# 1) NORMALIZACIÓN  (poner los datos en un formato común para poder comparar)
# =============================================================================

# Erratas de dominio más típicas al teclear un correo. Se corrigen antes de
# comparar para que "gmial.com" cuente como "gmail.com".
ERRATAS_DOMINIO = {
    "gmail.con": "gmail.com", "gmail.co": "gmail.com", "gmial.com": "gmail.com",
    "gmai.com": "gmail.com", "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com",
    "hotmail.con": "hotmail.com", "outlok.com": "outlook.com", "outloo.com": "outlook.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com",
}


def corregir_dominio_email(email):
    """Corrige erratas típicas del dominio. Si no hay errata, lo deja igual."""
    email = (email or "").strip()
    if "@" not in email:
        return email
    usuario, dominio = email.rsplit("@", 1)
    dominio_corregido = ERRATAS_DOMINIO.get(dominio.lower(), dominio)
    return f"{usuario}@{dominio_corregido}"


def normalizar_email(email):
    """Email en minúsculas y sin espacios en los extremos. Solo para comparar."""
    return (email or "").strip().lower()


def normalizar_telefono(telefono):
    """Deja el teléfono solo con dígitos (quita espacios, guiones y prefijo +34)."""
    t = (telefono or "").strip()
    t = t.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+34"):
        t = t[3:]
    elif t.startswith("0034"):
        t = t[4:]
    return t


def clave_email(contacto):
    """Email ya corregido y normalizado de un contacto (o '' si no tiene)."""
    return normalizar_email(corregir_dominio_email(contacto.get("email", "")))


def clave_telefono(contacto):
    """Teléfono ya normalizado de un contacto (o '' si no tiene)."""
    return normalizar_telefono(contacto.get("telefono", ""))


def clave_contacto(contacto):
    """Par (email normalizado, teléfono normalizado) de un contacto.

    Si dos filas comparten CUALQUIERA de los dos valores (y no están vacíos),
    se consideran la misma persona. Devolver los dos por separado permite
    comparar por uno u otro, no solo por los dos a la vez.
    """
    return (clave_email(contacto), clave_telefono(contacto))


# =============================================================================
# 2) VALIDACIÓN  (avisar de filas con datos sospechosos; nunca se descartan)
# =============================================================================

# Email válido: usuario@dominio.ext, con dominio que lleva al menos un punto y
# una extensión final de 2+ caracteres. Cae lo típico: sin @, dominio sin punto,
# espacios en medio, puntos dobles.
PATRON_EMAIL = re.compile(r"^[^@\s.]+(?:\.[^@\s.]+)*@(?:[^@\s.]+\.)+[^@\s.]{2,}$")

# Teléfono ya normalizado: solo dígitos, de 9 a 15 (rango internacional razonable).
PATRON_TELEFONO = re.compile(r"^\d{9,15}$")


def validar_email(email):
    """True si el email tiene formato válido (una @, dominio con punto, TLD>=2)."""
    return PATRON_EMAIL.match((email or "").strip()) is not None


def validar_telefono(telefono):
    """True si, una vez normalizado, son solo dígitos y mide entre 9 y 15."""
    return PATRON_TELEFONO.match(normalizar_telefono(telefono)) is not None


def es_contacto_valido(contacto):
    """True si email y teléfono tienen formato plausible.

    Sirve para AVISAR de filas problemáticas en el informe, no para borrarlas:
    la herramienta es no destructiva (criterio GDPR) y conserva todo.
    """
    return validar_email(contacto.get("email", "")) and validar_telefono(contacto.get("telefono", ""))


# =============================================================================
# 3) AGRUPACIÓN DE DUPLICADOS  (union-find: quién es quién, aunque sea en cadena)
# =============================================================================
#
# Problema: si "son la misma persona" cuando comparten email O teléfono, una
# coincidencia puede encadenarse. Ejemplo real:
#     A: elena@vista.com / 999  ─┐ (mismo email)
#     B: elena@vista.com / 111  ─┤
#     C: otra@correo.com / 111  ─┘ (mismo teléfono que B)
# A y C no comparten NADA directamente, pero son la misma persona a través de B.
# Para no dejar a C suelto usamos "conjuntos disjuntos" (union-find): cada fila
# empieza en su propio grupo y, cada vez que dos filas comparten un dato, se
# unen sus grupos. Al final, cada grupo es una persona.

def _raiz(padre, i):
    """Representante (raíz) del grupo al que pertenece la fila i.

    De paso 'comprime el camino': cuelga las filas visitadas directamente de la
    raíz para que la próxima consulta sea instantánea. Por eso union-find es casi
    O(1) por operación y aguanta cientos de miles de filas.
    """
    raiz = i
    while padre[raiz] != raiz:
        raiz = padre[raiz]
    while padre[i] != raiz:
        siguiente = padre[i]
        padre[i] = raiz
        i = siguiente
    return raiz


def _unir(padre, i, j):
    """Une los grupos de las filas i y j. El índice MENOR queda de representante.

    Así el representante de cada grupo es siempre la primera fila que apareció:
    esa será la que se conserve como 'maestra' (la original).
    """
    ri = _raiz(padre, i)
    rj = _raiz(padre, j)
    if ri == rj:
        return
    if ri < rj:
        padre[rj] = ri
    else:
        padre[ri] = rj


def agrupar_duplicados(contactos, estricto=False):
    """Agrupa los índices de las filas que son la misma persona.

    - Modo normal: misma persona si comparten email O teléfono (transitivo).
    - Modo estricto: misma persona solo si coinciden email Y teléfono (el
      comportamiento antiguo, más conservador).

    Devuelve una lista de grupos; cada grupo es una lista de índices ordenada,
    y el primero es el 'maestro' (la fila original que se conserva). Los grupos
    salen en el orden en que apareció su maestro.
    """
    n = len(contactos)
    padre = list(range(n))  # al principio, cada fila es su propio grupo

    if estricto:
        # La clave es el par completo (email, teléfono): solo se unen si coincide.
        clave_de = {}
        for i, contacto in enumerate(contactos):
            clave = clave_contacto(contacto)
            if clave == ("", ""):
                continue  # sin datos: no lo emparejamos con otros "vacíos"
            if clave in clave_de:
                _unir(padre, i, clave_de[clave])
            else:
                clave_de[clave] = i
    else:
        # Dos libretas: la primera fila que usó cada email / cada teléfono.
        email_de = {}
        tel_de = {}
        for i, contacto in enumerate(contactos):
            email = clave_email(contacto)
            telefono = clave_telefono(contacto)
            if email:
                if email in email_de:
                    _unir(padre, i, email_de[email])
                else:
                    email_de[email] = i
            if telefono:
                if telefono in tel_de:
                    _unir(padre, i, tel_de[telefono])
                else:
                    tel_de[telefono] = i

    # Reunir los índices por su raíz para formar los grupos finales.
    grupos = {}
    for i in range(n):
        raiz = _raiz(padre, i)
        grupos.setdefault(raiz, []).append(i)
    return [sorted(indices) for _, indices in sorted(grupos.items())]


# =============================================================================
# 4) DEDUPLICACIÓN  (conservar el maestro de cada persona, separar el resto)
# =============================================================================

def deduplicar(contactos, estricto=False):
    """Separa la lista en (unicos, duplicados) conservando el dato original.

    El maestro de cada grupo (la primera fila que apareció) se considera el
    bueno; las repeticiones se apartan. No modifica ningún dato: para eso está
    'deduplicar_fusionando'.
    """
    unicos = []
    duplicados = []
    for grupo in agrupar_duplicados(contactos, estricto=estricto):
        unicos.append(contactos[grupo[0]])
        for idx in grupo[1:]:
            duplicados.append(contactos[idx])
    return unicos, duplicados


def fusionar_grupo(filas):
    """Funde varias filas de la MISMA persona en un único 'registro maestro'.

    Parte de la primera fila (la original) y rellena sus campos VACÍOS con el
    primer valor no vacío que encuentre en las repeticiones. Así el registro
    final es el más completo posible sin inventar ni pisar datos buenos.

    Ejemplo: si la original tiene email pero no empresa, y una copia tiene la
    empresa, el maestro se queda con email + empresa.
    """
    maestro = dict(filas[0])  # copia, para no tocar el original
    for otra in filas[1:]:
        for campo, valor in otra.items():
            actual = (maestro.get(campo) or "").strip()
            if not actual and (valor or "").strip():
                maestro[campo] = valor
    return maestro


def deduplicar_fusionando(contactos, estricto=False):
    """Como 'deduplicar', pero cada único es el registro maestro fusionado."""
    unicos = []
    duplicados = []
    for grupo in agrupar_duplicados(contactos, estricto=estricto):
        filas = [contactos[i] for i in grupo]
        unicos.append(fusionar_grupo(filas))
        duplicados.extend(filas[1:])
    return unicos, duplicados


# =============================================================================
# 5) AUDITORÍA  (por qué cada duplicado es la misma persona que su maestro)
# =============================================================================

def motivo_duplicado(maestro, duplicado):
    """Explica por qué 'duplicado' se considera la misma persona que 'maestro'.

    Puede ser por email, por teléfono, por ambos, o 'enlazado' (cuando no
    comparten nada directamente, sino a través de otra fila del grupo). Decir la
    verdad aquí —incluido el caso 'enlazado'— es lo que hace la herramienta
    auditable y defendible.
    """
    email_maestro = clave_email(maestro)
    email_dup = clave_email(duplicado)
    tel_maestro = clave_telefono(maestro)
    tel_dup = clave_telefono(duplicado)

    mismo_email = bool(email_maestro) and email_maestro == email_dup
    mismo_tel = bool(tel_maestro) and tel_maestro == tel_dup

    if mismo_email and mismo_tel:
        return "email y teléfono"
    if mismo_email:
        return "email"
    if mismo_tel:
        return "teléfono"
    return "enlazado (transitivo)"


def construir_auditoria(contactos, estricto=False):
    """Devuelve, por cada duplicado, con qué maestro se fusiona y por qué.

    Es el rastro de trazabilidad (criterio GDPR): nada se elimina "en silencio".
    """
    filas = []
    for grupo in agrupar_duplicados(contactos, estricto=estricto):
        if len(grupo) < 2:
            continue
        maestro = contactos[grupo[0]]
        for idx in grupo[1:]:
            dup = contactos[idx]
            filas.append({
                "maestro_nombre": maestro.get("nombre", ""),
                "maestro_email": maestro.get("email", ""),
                "maestro_telefono": maestro.get("telefono", ""),
                "duplicado_nombre": dup.get("nombre", ""),
                "duplicado_email": dup.get("email", ""),
                "duplicado_telefono": dup.get("telefono", ""),
                "motivo": motivo_duplicado(maestro, dup),
            })
    return filas


# =============================================================================
# 6) MÉTRICAS Y ESTADÍSTICAS  (los números que demuestran el valor del proyecto)
# =============================================================================

# Segundos que cuesta revisar y limpiar UNA fila a mano (mirar si está
# duplicada, comparar email y teléfono). Estimación conservadora.
SEGUNDOS_LIMPIEZA_MANUAL_POR_FILA = 8


def metrica_duplicados(total, n_duplicados):
    """Devuelve el % de filas que eran duplicadas (0.0 si la base está vacía)."""
    if total == 0:
        return 0.0
    return round(n_duplicados / total * 100, 1)


def minutos_ahorrados(total_filas):
    """Estima el tiempo de limpieza manual evitado por procesar 'total_filas'.

    Devuelve (minutos_totales, minutos_por_1000_filas): lo ahorrado en esta
    ejecución y la tasa normalizada (útil para comparar a otra escala).
    """
    segundos_totales = total_filas * SEGUNDOS_LIMPIEZA_MANUAL_POR_FILA
    minutos_totales = round(segundos_totales / 60, 1)
    minutos_por_1000 = round(SEGUNDOS_LIMPIEZA_MANUAL_POR_FILA * 1000 / 60, 1)
    return (minutos_totales, minutos_por_1000)


def desglose_por_motivo(contactos, estricto=False):
    """Cuenta cuántos duplicados se detectaron por cada motivo."""
    cuenta = {
        "email y teléfono": 0,
        "email": 0,
        "teléfono": 0,
        "enlazado (transitivo)": 0,
    }
    for fila in construir_auditoria(contactos, estricto=estricto):
        cuenta[fila["motivo"]] += 1
    return cuenta


def top_empresas_con_duplicados(contactos, top=5, estricto=False):
    """Empresas con más filas duplicadas (dónde está más sucia la base)."""
    cuenta = {}
    for grupo in agrupar_duplicados(contactos, estricto=estricto):
        for idx in grupo[1:]:
            empresa = (contactos[idx].get("empresa") or "").strip() or "(sin empresa)"
            cuenta[empresa] = cuenta.get(empresa, 0) + 1
    return sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


# =============================================================================
# 7) ENTRADA / SALIDA  (leer el CSV sucio, escribir los resultados)
# =============================================================================

class ErrorColumnas(Exception):
    """El CSV de entrada no trae las columnas mínimas ('email' y 'telefono')."""


def _normalizar_clave_columna(nombre):
    """Pasa el nombre de una columna a minúsculas y sin espacios.

    Así toleramos 'Email', ' TELEFONO ' o 'E-mail' apuntando todo al mismo sitio.
    """
    return (nombre or "").strip().lower().replace("-", "").replace(" ", "")


def _detectar_delimitador(muestra):
    """Adivina si el CSV usa ',' o ';' mirando cuál abunda en la cabecera."""
    primera_linea = muestra.splitlines()[0] if muestra else ""
    return ";" if primera_linea.count(";") > primera_linea.count(",") else ","


def cargar_contactos(ruta, delimitador=None):
    """Lee un CSV y devuelve (lista_de_contactos, nombres_de_columnas).

    - Tolera BOM (encoding utf-8-sig) y separador ',' o ';' (se autodetecta).
    - Normaliza los nombres de columna a minúsculas para ser flexible.
    - Exige que existan 'email' y 'telefono'; si no, lanza ErrorColumnas con un
      mensaje claro en vez de fallar de forma críptica.
    """
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        if delimitador is None:
            delimitador = _detectar_delimitador(muestra)
        lector = csv.DictReader(f, delimiter=delimitador)
        columnas = [_normalizar_clave_columna(c) for c in (lector.fieldnames or [])]
        contactos = []
        for fila in lector:
            contactos.append({
                _normalizar_clave_columna(k): (v if v is not None else "")
                for k, v in fila.items()
            })

    faltan = [c for c in ("email", "telefono") if c not in columnas]
    if faltan:
        encontradas = ", ".join(columnas) if columnas else "(ninguna)"
        raise ErrorColumnas(
            f"El CSV debe incluir las columnas 'email' y 'telefono'. "
            f"Faltan: {', '.join(faltan)}. Columnas encontradas: {encontradas}."
        )
    return contactos, columnas


def exportar_csv(contactos, columnas, ruta):
    """Escribe los contactos en un CSV nuevo con las columnas indicadas."""
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(contactos)


def exportar_auditoria(filas_auditoria, ruta="duplicados_eliminados.csv"):
    """Escribe el rastro de duplicados eliminados (con su motivo)."""
    columnas = [
        "maestro_nombre", "maestro_email", "maestro_telefono",
        "duplicado_nombre", "duplicado_email", "duplicado_telefono", "motivo",
    ]
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas_auditoria)


# --- Exportación lista para Salesforce --------------------------------------

def separar_nombre(nombre):
    """Parte 'Ana García López' en ('Ana', 'García López') -> (nombre, apellidos).

    Salesforce y la mayoría de CRM guardan nombre y apellidos por separado.
    """
    partes = (nombre or "").strip().split()
    if not partes:
        return ("", "")
    if len(partes) == 1:
        return ("", partes[0])
    return (partes[0], " ".join(partes[1:]))


def telefono_e164(telefono):
    """Teléfono en formato internacional '+34600112233' (asume España si son 9)."""
    t = normalizar_telefono(telefono)
    if len(t) == 9 and t.isdigit():
        return "+34" + t
    return t


def exportar_salesforce(unicos, ruta="contactos_salesforce.csv"):
    """Exporta los contactos limpios con columnas estándar de Salesforce."""
    columnas = ["FirstName", "LastName", "Email", "Phone", "Company"]
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        for c in unicos:
            nombre, apellidos = separar_nombre(c.get("nombre", ""))
            escritor.writerow({
                "FirstName": nombre,
                "LastName": apellidos or c.get("nombre", "") or "(sin nombre)",
                "Email": clave_email(c),
                "Phone": telefono_e164(c.get("telefono", "")),
                "Company": c.get("empresa", ""),
            })


# =============================================================================
# 8) INFORME HTML  (panel visual para enseñar el resultado en el navegador)
# =============================================================================

def generar_informe_html(contactos, unicos, duplicados, ruta="informe.html",
                         estricto=False):
    """Crea un panel HTML con las métricas clave y los duplicados detectados."""
    total = len(contactos)
    n_uni, n_dup = len(unicos), len(duplicados)
    pct = metrica_duplicados(total, n_dup)
    min_total, min_por_mil = minutos_ahorrados(total)
    motivos = desglose_por_motivo(contactos, estricto=estricto)
    top_empresas = top_empresas_con_duplicados(contactos, estricto=estricto)
    auditoria = construir_auditoria(contactos, estricto=estricto)
    n_invalidos = sum(1 for c in contactos if not es_contacto_valido(c))
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    filas_motivos = "".join(
        f"<tr><td>{escape(motivo)}</td><td>{n}</td></tr>"
        for motivo, n in motivos.items() if n
    ) or "<tr><td colspan='2'>Sin duplicados</td></tr>"

    filas_empresas = "".join(
        f"<tr><td>{escape(nombre)}</td><td>{n}</td></tr>"
        for nombre, n in top_empresas
    ) or "<tr><td colspan='2'>—</td></tr>"

    filas_dup = "".join(
        f"<tr><td>{escape(f['duplicado_nombre'])}</td>"
        f"<td>{escape(f['duplicado_email'])}</td>"
        f"<td>{escape(f['duplicado_telefono'])}</td>"
        f"<td>{escape(f['maestro_nombre'])}</td>"
        f"<td>{escape(f['motivo'])}</td></tr>"
        for f in auditoria[:20]
    ) or "<tr><td colspan='5'>No se detectaron duplicados</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de Limpieza y Deduplicación</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#0f172a;
         color:#e2e8f0; margin:0; padding:40px; }}
  h1 {{ color:#38bdf8; }}
  h2 {{ color:#94a3b8; border-bottom:1px solid #334155; padding-bottom:6px; }}
  .cards {{ display:flex; gap:20px; flex-wrap:wrap; margin:30px 0; }}
  .card {{ background:#1e293b; border-radius:14px; padding:24px 30px;
           min-width:150px; box-shadow:0 4px 14px rgba(0,0,0,.3); }}
  .card .num {{ font-size:38px; font-weight:700; }}
  .card .lbl {{ color:#94a3b8; font-size:14px; }}
  .ok {{ color:#4ade80; }} .dup {{ color:#fbbf24; }} .bad {{ color:#f87171; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0 34px; }}
  th,td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #334155; }}
  th {{ color:#38bdf8; }}
  tr:hover {{ background:#1e293b; }}
  .tablas {{ display:flex; gap:40px; flex-wrap:wrap; }}
  .tablas > div {{ flex:1; min-width:280px; }}
  footer {{ margin-top:40px; color:#64748b; font-size:13px; }}
</style>
</head>
<body>
  <h1>🧹 Informe de Limpieza y Deduplicación</h1>
  <p>Análisis automático de <b>{total}</b> contactos &middot; {escape(fecha)}</p>
  <div class="cards">
    <div class="card"><div class="num">{total}</div>
      <div class="lbl">📥 Leídos</div></div>
    <div class="card"><div class="num ok">{n_uni}</div>
      <div class="lbl">✅ Únicos</div></div>
    <div class="card"><div class="num dup">{n_dup}</div>
      <div class="lbl">🔁 Duplicados ({pct}%)</div></div>
    <div class="card"><div class="num bad">{n_invalidos}</div>
      <div class="lbl">⚠️ Con datos dudosos</div></div>
    <div class="card"><div class="num">{min_total}</div>
      <div class="lbl">⏱️ Min. manuales ahorrados</div></div>
  </div>

  <div class="tablas">
    <div>
      <h2>🔎 Duplicados por motivo</h2>
      <table><tr><th>Motivo</th><th>Nº</th></tr>{filas_motivos}</table>
    </div>
    <div>
      <h2>🏢 Empresas con más duplicados</h2>
      <table><tr><th>Empresa</th><th>Duplicados</th></tr>{filas_empresas}</table>
    </div>
  </div>

  <h2>🧾 Duplicados detectados (auditoría)</h2>
  <table>
    <tr><th>Duplicado</th><th>Email</th><th>Teléfono</th>
        <th>Se fusiona con</th><th>Motivo</th></tr>
    {filas_dup}
  </table>

  <footer>Generado automáticamente por deduplicador.py — sin librerías externas.
  Herramienta no destructiva: el archivo de entrada nunca se modifica.</footer>
</body>
</html>"""

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)


# =============================================================================
# 9) PROGRAMA PRINCIPAL  (junta todo y enseña el resultado por pantalla)
# =============================================================================

def main():
    # En Windows la consola usa cp1252 y no admite emojis: forzamos UTF-8 para
    # que el resumen con iconos no rompa el programa.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Limpia y deduplica una base de contactos CSV (no destructivo).")
    parser.add_argument("entrada", help="CSV de entrada (la base sucia)")
    parser.add_argument("--salida", default="contactos_limpios.csv",
                        help="CSV de salida sin duplicados (def: contactos_limpios.csv)")
    parser.add_argument("--fusionar", action="store_true",
                        help="Fusiona cada grupo en un registro maestro (golden record)")
    parser.add_argument("--auditoria", action="store_true",
                        help="Exporta duplicados_eliminados.csv con el motivo")
    parser.add_argument("--html", action="store_true",
                        help="Genera informe.html (panel visual)")
    parser.add_argument("--salesforce", action="store_true",
                        help="Exporta contactos_salesforce.csv listo para importar")
    parser.add_argument("--estricto", action="store_true",
                        help="Duplicado solo si coinciden email Y teléfono (modo antiguo)")
    parser.add_argument("--delimitador", default=None,
                        help="Separador del CSV (',' o ';'); por defecto se detecta solo")
    args = parser.parse_args()

    try:
        contactos, columnas = cargar_contactos(args.entrada, args.delimitador)
    except FileNotFoundError:
        print(f"❌ No encuentro el archivo: {args.entrada}")
        sys.exit(1)
    except ErrorColumnas as e:
        print(f"❌ {e}")
        sys.exit(1)

    total = len(contactos)
    if total == 0:
        print("⚠️  El archivo no tiene contactos (solo cabecera o está vacío).")
        sys.exit(1)

    if args.fusionar:
        unicos, duplicados = deduplicar_fusionando(contactos, estricto=args.estricto)
    else:
        unicos, duplicados = deduplicar(contactos, estricto=args.estricto)

    pct = metrica_duplicados(total, len(duplicados))
    min_total, min_por_mil = minutos_ahorrados(total)
    n_invalidos = sum(1 for c in contactos if not es_contacto_valido(c))

    exportar_csv(unicos, columnas, args.salida)

    generados = [args.salida]
    if args.auditoria:
        exportar_auditoria(construir_auditoria(contactos, estricto=args.estricto))
        generados.append("duplicados_eliminados.csv")
    if args.salesforce:
        exportar_salesforce(unicos)
        generados.append("contactos_salesforce.csv")
    if args.html:
        generar_informe_html(contactos, unicos, duplicados, estricto=args.estricto)
        generados.append("informe.html")

    modo = "estricto (email Y teléfono)" if args.estricto else "normal (email O teléfono)"
    print("=" * 50)
    print("🧹 LIMPIADOR-DEDUPLICADOR DE CRM")
    print("=" * 50)
    print(f"📥 Contactos leídos:        {total}")
    print(f"🔁 Duplicados eliminados:   {len(duplicados)}")
    print(f"✅ Contactos únicos:        {len(unicos)}")
    print(f"📊 % duplicados eliminados: {pct}%")
    print(f"⚠️  Filas con datos dudosos: {n_invalidos}")
    print(f"⏱️  Limpieza manual evitada: {min_total} min ({min_por_mil} por cada 1.000)")
    print(f"🧭 Modo de detección:       {modo}")
    if args.fusionar:
        print("🧩 Registros fusionados en maestro (golden record): sí")
    print(f"💾 Archivos generados:      {', '.join(generados)}")
    print("=" * 50)


if __name__ == "__main__":
    main()

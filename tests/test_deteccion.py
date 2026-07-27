# -*- coding: utf-8 -*-
"""
Tests de la FASE de detección/agrupación: el corazón del proyecto.
Comprueba que se detectan duplicados por email O por teléfono (no solo por los
dos a la vez) y que el modo estricto sigue funcionando como antes.
"""

from deduplicador import agrupar_duplicados, deduplicar


# --- agrupar_duplicados (modo normal: email O teléfono) ---------------------

def test_duplicado_por_email_y_telefono():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "+34 612 34 56 78"},
        {"email": "Ana@TechCorp.com", "telefono": "612345678"},
    ]
    grupos = agrupar_duplicados(contactos)
    assert grupos == [[0, 1]]


def test_duplicado_solo_por_email():
    # Mismo email, teléfono distinto: con la regla nueva, son la misma persona.
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "612345678"},
        {"email": "ana@techcorp.com", "telefono": "666666666"},
    ]
    assert agrupar_duplicados(contactos) == [[0, 1]]


def test_duplicado_solo_por_telefono():
    # Mismo teléfono, email distinto: también es la misma persona.
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "612345678"},
        {"email": "otra@correo.com", "telefono": "612345678"},
    ]
    assert agrupar_duplicados(contactos) == [[0, 1]]


def test_personas_distintas_no_se_agrupan():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "612345678"},
        {"email": "luis@datasoft.com", "telefono": "699887766"},
    ]
    assert agrupar_duplicados(contactos) == [[0], [1]]


def test_cadena_transitiva_tres_filas():
    # A y C no comparten nada directamente, pero sí a través de B.
    contactos = [
        {"email": "elena@vista.com", "telefono": "999000111"},   # A
        {"email": "elena@vista.com", "telefono": "111222333"},   # B (email de A)
        {"email": "otra@correo.com", "telefono": "111222333"},   # C (teléfono de B)
    ]
    assert agrupar_duplicados(contactos) == [[0, 1, 2]]


def test_email_vacio_no_agrupa_a_desconocidos():
    # Dos contactos sin email no deben fundirse "por compartir el vacío".
    contactos = [
        {"email": "", "telefono": "612345678"},
        {"email": "", "telefono": "699887766"},
    ]
    assert agrupar_duplicados(contactos) == [[0], [1]]


# --- modo estricto (email Y teléfono) ---------------------------------------

def test_estricto_no_agrupa_si_solo_coincide_email():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "612345678"},
        {"email": "ana@techcorp.com", "telefono": "666666666"},
    ]
    # En estricto hacen falta los dos: aquí NO son duplicados.
    assert agrupar_duplicados(contactos, estricto=True) == [[0], [1]]


def test_estricto_agrupa_si_coinciden_los_dos():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "+34 612 34 56 78"},
        {"email": "Ana@TechCorp.com", "telefono": "612345678"},
    ]
    assert agrupar_duplicados(contactos, estricto=True) == [[0, 1]]


# --- deduplicar -------------------------------------------------------------

def test_deduplicar_separa_y_conserva_el_primero():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "+34 612 34 56 78"},
        {"email": "luis@datasoft.com", "telefono": "699887766"},
        {"email": "Ana@TechCorp.com", "telefono": "612 34 56 78"},  # duplicado de Ana
    ]
    unicos, duplicados = deduplicar(contactos)
    assert len(unicos) == 2
    assert len(duplicados) == 1
    assert unicos[0]["email"] == "ana@techcorp.com"  # se conserva el primero


def test_deduplicar_lista_vacia():
    unicos, duplicados = deduplicar([])
    assert unicos == [] and duplicados == []


def test_deduplicar_conserva_orden_de_aparicion():
    contactos = [
        {"email": "ana@techcorp.com", "telefono": "612345678"},
        {"email": "luis@datasoft.com", "telefono": "699887766"},
        {"email": "marta@innova.es", "telefono": "611223344"},
    ]
    unicos, _ = deduplicar(contactos)
    assert [c["email"] for c in unicos] == [
        "ana@techcorp.com", "luis@datasoft.com", "marta@innova.es",
    ]

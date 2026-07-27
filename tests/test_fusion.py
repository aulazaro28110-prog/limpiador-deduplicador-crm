# -*- coding: utf-8 -*-
"""
Tests de la FASE de fusión (registro maestro / golden record) y de la auditoría
(motivo por el que cada duplicado se considera la misma persona).
"""

from deduplicador import (
    fusionar_grupo,
    deduplicar_fusionando,
    motivo_duplicado,
    construir_auditoria,
)


# --- fusionar_grupo ---------------------------------------------------------

def test_fusion_rellena_campos_vacios():
    filas = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "", "empresa": ""},
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678", "empresa": "TechCorp"},
    ]
    maestro = fusionar_grupo(filas)
    assert maestro["telefono"] == "612345678"  # lo aportó la copia
    assert maestro["empresa"] == "TechCorp"


def test_fusion_no_pisa_datos_buenos_del_original():
    filas = [
        {"nombre": "Ana", "email": "ana@bien.com"},
        {"nombre": "Ana", "email": "ana@mal.com"},
    ]
    maestro = fusionar_grupo(filas)
    assert maestro["email"] == "ana@bien.com"  # gana el original


def test_fusion_no_modifica_la_fila_original():
    original = {"nombre": "Ana", "email": "ana@x.com", "telefono": ""}
    filas = [original, {"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678"}]
    fusionar_grupo(filas)
    assert original["telefono"] == ""  # el original sigue intacto


# --- deduplicar_fusionando --------------------------------------------------

def test_deduplicar_fusionando_devuelve_maestro_completo():
    contactos = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "", "empresa": "TechCorp"},
        {"nombre": "Ana G.", "email": "ana@x.com", "telefono": "612345678", "empresa": ""},
    ]
    unicos, duplicados = deduplicar_fusionando(contactos)
    assert len(unicos) == 1
    assert len(duplicados) == 1
    assert unicos[0]["telefono"] == "612345678"
    assert unicos[0]["empresa"] == "TechCorp"


# --- motivo_duplicado -------------------------------------------------------

def test_motivo_email_y_telefono():
    m = {"email": "ana@x.com", "telefono": "612345678"}
    d = {"email": "Ana@X.com", "telefono": "+34 612 34 56 78"}
    assert motivo_duplicado(m, d) == "email y teléfono"


def test_motivo_solo_email():
    m = {"email": "ana@x.com", "telefono": "612345678"}
    d = {"email": "ana@x.com", "telefono": "666666666"}
    assert motivo_duplicado(m, d) == "email"


def test_motivo_solo_telefono():
    m = {"email": "ana@x.com", "telefono": "612345678"}
    d = {"email": "otra@y.com", "telefono": "612345678"}
    assert motivo_duplicado(m, d) == "teléfono"


def test_motivo_enlazado_transitivo():
    # No comparten ni email ni teléfono directamente.
    m = {"email": "ana@x.com", "telefono": "612345678"}
    d = {"email": "otra@y.com", "telefono": "999999999"}
    assert motivo_duplicado(m, d) == "enlazado (transitivo)"


# --- construir_auditoria ----------------------------------------------------

def test_auditoria_lista_los_duplicados_con_motivo():
    contactos = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678", "empresa": "X"},
        {"nombre": "Ana G.", "email": "ana@x.com", "telefono": "666666666", "empresa": "X"},
    ]
    filas = construir_auditoria(contactos)
    assert len(filas) == 1
    assert filas[0]["motivo"] == "email"
    assert filas[0]["maestro_nombre"] == "Ana"
    assert filas[0]["duplicado_nombre"] == "Ana G."


def test_auditoria_vacia_si_no_hay_duplicados():
    contactos = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678"},
        {"nombre": "Luis", "email": "luis@y.com", "telefono": "699887766"},
    ]
    assert construir_auditoria(contactos) == []

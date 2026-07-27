# -*- coding: utf-8 -*-
"""
Tests de la FASE de normalización: dejar email y teléfono en un formato común
para poder compararlos. Ejecutar con: pytest -v
"""

from deduplicador import (
    normalizar_email,
    normalizar_telefono,
    corregir_dominio_email,
    clave_email,
    clave_telefono,
    clave_contacto,
)


# --- normalizar_email -------------------------------------------------------

def test_email_minusculas_y_sin_espacios():
    assert normalizar_email("  Ana@TechCorp.com ") == "ana@techcorp.com"


def test_email_vacio_o_none():
    assert normalizar_email("") == ""
    assert normalizar_email(None) == ""


# --- normalizar_telefono ----------------------------------------------------

def test_telefono_quita_prefijo_34_y_espacios():
    assert normalizar_telefono("+34 612 34 56 78") == "612345678"


def test_telefono_quita_prefijo_0034_y_guiones():
    assert normalizar_telefono("0034-612-345-678") == "612345678"


def test_telefono_quita_parentesis():
    assert normalizar_telefono("(612) 345 678") == "612345678"


def test_telefono_none_no_rompe():
    assert normalizar_telefono(None) == ""


# --- corregir_dominio_email -------------------------------------------------

def test_corregir_dominio_errata():
    assert corregir_dominio_email("sofia@gmial.com") == "sofia@gmail.com"


def test_corregir_dominio_sin_errata_no_cambia():
    assert corregir_dominio_email("ana@techcorp.com") == "ana@techcorp.com"


def test_corregir_dominio_sin_arroba_no_rompe():
    assert corregir_dominio_email("textosinarroba") == "textosinarroba"


# --- claves de contacto -----------------------------------------------------

def test_clave_email_corrige_y_normaliza():
    assert clave_email({"email": " Sofia@Gmial.com "}) == "sofia@gmail.com"


def test_clave_telefono_normaliza():
    assert clave_telefono({"telefono": "+34 600 12 34 56"}) == "600123456"


def test_clave_contacto_devuelve_par():
    contacto = {"email": "Ana@TechCorp.com", "telefono": "+34 612 34 56 78"}
    assert clave_contacto(contacto) == ("ana@techcorp.com", "612345678")


def test_dos_variantes_misma_persona_misma_clave():
    a = {"email": "ana@techcorp.com", "telefono": "+34 612 34 56 78"}
    b = {"email": "Ana@TechCorp.com", "telefono": "612345678"}
    assert clave_contacto(a) == clave_contacto(b)

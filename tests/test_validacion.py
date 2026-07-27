# -*- coding: utf-8 -*-
"""
Tests de la FASE de validación: marcar (que no borrar) filas con datos dudosos.
"""

from deduplicador import validar_email, validar_telefono, es_contacto_valido


# --- validar_email ----------------------------------------------------------

def test_email_validos():
    assert validar_email("ana@gmail.com")
    assert validar_email("juan.perez@empresa.es")
    assert validar_email("  luis@dominio.org  ")  # con espacios alrededor


def test_email_invalidos():
    assert not validar_email("ana gmail.com")     # sin @
    assert not validar_email("ana@@gmail.com")    # dos @
    assert not validar_email("ana@gmailcom")      # dominio sin punto
    assert not validar_email("@gmail.com")        # sin usuario
    assert not validar_email("ana@")              # sin dominio
    assert not validar_email("ana@gmail.c")       # extensión de 1 letra
    assert not validar_email("")                  # vacío


# --- validar_telefono -------------------------------------------------------

def test_telefono_validos():
    assert validar_telefono("612345678")          # 9 dígitos
    assert validar_telefono("+34 612 34 56 78")    # con prefijo y espacios
    assert validar_telefono("0034612345678")       # prefijo 0034


def test_telefono_invalidos():
    assert not validar_telefono("61234")           # demasiado corto
    assert not validar_telefono("6123456ABC")      # con letras
    assert not validar_telefono("")                # vacío


# --- es_contacto_valido -----------------------------------------------------

def test_contacto_valido_completo():
    assert es_contacto_valido({"email": "ana@gmail.com", "telefono": "612345678"})


def test_contacto_invalido_si_falla_uno():
    assert not es_contacto_valido({"email": "ana@gmail.com", "telefono": "abc"})
    assert not es_contacto_valido({"email": "sin-arroba", "telefono": "612345678"})

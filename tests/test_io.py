# -*- coding: utf-8 -*-
"""
Tests de la FASE de entrada/salida y de las métricas:
leer CSV (con autodetección de separador, BOM y columnas que faltan), exportar,
preparar el formato Salesforce y calcular los números del informe.
"""

import pytest

from deduplicador import (
    cargar_contactos,
    exportar_csv,
    exportar_auditoria,
    ErrorColumnas,
    metrica_duplicados,
    minutos_ahorrados,
    desglose_por_motivo,
    top_empresas_con_duplicados,
    separar_nombre,
    telefono_e164,
    construir_auditoria,
)


# --- cargar_contactos -------------------------------------------------------

def test_cargar_csv_basico(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("nombre,email,telefono\nAna,ana@x.com,612345678\n", encoding="utf-8")
    contactos, columnas = cargar_contactos(str(ruta))
    assert len(contactos) == 1
    assert contactos[0]["email"] == "ana@x.com"
    assert "telefono" in columnas


def test_cargar_detecta_punto_y_coma(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("nombre;email;telefono\nAna;ana@x.com;612345678\n", encoding="utf-8")
    contactos, _ = cargar_contactos(str(ruta))
    assert contactos[0]["telefono"] == "612345678"


def test_cargar_tolera_mayusculas_en_columnas(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("Nombre,Email,Telefono\nAna,ana@x.com,612345678\n", encoding="utf-8")
    contactos, columnas = cargar_contactos(str(ruta))
    assert contactos[0]["email"] == "ana@x.com"  # accesible en minúsculas
    assert "email" in columnas


def test_cargar_tolera_bom(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("nombre,email,telefono\nAna,ana@x.com,612345678\n", encoding="utf-8-sig")
    contactos, columnas = cargar_contactos(str(ruta))
    assert "nombre" in columnas  # el BOM no se cuela en el nombre de la 1ª columna


def test_cargar_sin_columnas_obligatorias_lanza_error(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("nombre,correo\nAna,ana@x.com\n", encoding="utf-8")
    with pytest.raises(ErrorColumnas):
        cargar_contactos(str(ruta))


# --- exportar ---------------------------------------------------------------

def test_exportar_csv_ida_y_vuelta(tmp_path):
    contactos = [{"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678"}]
    ruta = tmp_path / "salida.csv"
    exportar_csv(contactos, ["nombre", "email", "telefono"], str(ruta))
    devuelta, _ = cargar_contactos(str(ruta))
    assert devuelta[0]["email"] == "ana@x.com"


def test_exportar_auditoria_escribe_cabecera(tmp_path):
    contactos = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "612345678"},
        {"nombre": "Ana G.", "email": "ana@x.com", "telefono": "666666666"},
    ]
    ruta = tmp_path / "audit.csv"
    exportar_auditoria(construir_auditoria(contactos), str(ruta))
    texto = ruta.read_text(encoding="utf-8")
    assert "motivo" in texto
    assert "email" in texto


# --- métricas ---------------------------------------------------------------

def test_metrica_porcentaje():
    assert metrica_duplicados(16, 8) == 50.0


def test_metrica_base_vacia_no_divide_por_cero():
    assert metrica_duplicados(0, 0) == 0.0


def test_minutos_ahorrados():
    total, por_mil = minutos_ahorrados(1000)
    assert por_mil == 133.3
    assert total == 133.3


def test_desglose_por_motivo_cuenta_bien():
    contactos = [
        {"email": "ana@x.com", "telefono": "612345678", "empresa": "X"},
        {"email": "ana@x.com", "telefono": "666666666", "empresa": "X"},  # email
        {"email": "luis@y.com", "telefono": "699887766", "empresa": "Y"},
        {"email": "otro@z.com", "telefono": "699887766", "empresa": "Y"},  # teléfono
    ]
    cuenta = desglose_por_motivo(contactos)
    assert cuenta["email"] == 1
    assert cuenta["teléfono"] == 1


def test_top_empresas_con_duplicados():
    contactos = [
        {"email": "ana@x.com", "telefono": "612345678", "empresa": "TechCorp"},
        {"email": "ana@x.com", "telefono": "666666666", "empresa": "TechCorp"},
    ]
    top = top_empresas_con_duplicados(contactos)
    assert top[0] == ("TechCorp", 1)


# --- helpers de Salesforce --------------------------------------------------

def test_separar_nombre():
    assert separar_nombre("Ana García López") == ("Ana", "García López")
    assert separar_nombre("Madonna") == ("", "Madonna")
    assert separar_nombre("") == ("", "")


def test_telefono_e164():
    assert telefono_e164("612 34 56 78") == "+34612345678"
    assert telefono_e164("+34 612 34 56 78") == "+34612345678"

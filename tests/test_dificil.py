# -*- coding: utf-8 -*-
"""
Tests DIFÍCILES: casos límite y "trampas" que rompen una solución ingenua.
Si todos estos pasan, la herramienta aguanta datos reales y sucios.
"""

from deduplicador import (
    agrupar_duplicados,
    deduplicar,
    deduplicar_fusionando,
    construir_auditoria,
    fusionar_grupo,
    clave_email,
)


def test_cadena_larga_de_cinco_se_agrupa_entera():
    # Cadena: 0-1 (email), 1-2 (tel), 2-3 (email), 3-4 (tel). Todos la misma persona.
    contactos = [
        {"email": "a@x.com", "telefono": "111111111"},  # 0
        {"email": "a@x.com", "telefono": "222222222"},  # 1  (email de 0)
        {"email": "b@x.com", "telefono": "222222222"},  # 2  (tel de 1)
        {"email": "b@x.com", "telefono": "333333333"},  # 3  (email de 2)
        {"email": "c@x.com", "telefono": "333333333"},  # 4  (tel de 3)
    ]
    assert agrupar_duplicados(contactos) == [[0, 1, 2, 3, 4]]


def test_orden_no_altera_la_agrupacion():
    # Las mismas filas en otro orden deben formar el mismo grupo único.
    contactos = [
        {"email": "c@x.com", "telefono": "333333333"},
        {"email": "a@x.com", "telefono": "111111111"},
        {"email": "b@x.com", "telefono": "222222222"},
        {"email": "a@x.com", "telefono": "222222222"},
        {"email": "b@x.com", "telefono": "333333333"},
    ]
    grupos = agrupar_duplicados(contactos)
    assert len(grupos) == 1
    assert sorted(grupos[0]) == [0, 1, 2, 3, 4]


def test_dos_personas_sin_ningun_dato_no_se_funden():
    # Filas totalmente vacías: no hay forma de saber que son la misma persona.
    contactos = [
        {"email": "", "telefono": ""},
        {"email": "", "telefono": ""},
    ]
    assert agrupar_duplicados(contactos) == [[0], [1]]


def test_errata_de_dominio_cuenta_como_duplicado():
    # 'gmial.com' se corrige a 'gmail.com' antes de comparar.
    contactos = [
        {"email": "sofia@gmail.com", "telefono": "600123456"},
        {"email": "sofia@gmial.com", "telefono": "699999999"},
    ]
    assert agrupar_duplicados(contactos) == [[0, 1]]


def test_maestro_es_siempre_la_primera_aparicion():
    contactos = [
        {"email": "ana@x.com", "telefono": "111", "nombre": "Original"},
        {"email": "ana@x.com", "telefono": "222", "nombre": "Copia 1"},
        {"email": "ana@x.com", "telefono": "333", "nombre": "Copia 2"},
    ]
    unicos, duplicados = deduplicar(contactos)
    assert unicos[0]["nombre"] == "Original"
    assert len(duplicados) == 2


def test_fusion_de_grupo_grande_queda_completo():
    contactos = [
        {"nombre": "Ana", "email": "ana@x.com", "telefono": "", "empresa": ""},
        {"nombre": "", "email": "ana@x.com", "telefono": "612345678", "empresa": ""},
        {"nombre": "", "email": "ana@x.com", "telefono": "", "empresa": "TechCorp"},
    ]
    unicos, _ = deduplicar_fusionando(contactos)
    maestro = unicos[0]
    assert maestro["nombre"] == "Ana"
    assert maestro["telefono"] == "612345678"
    assert maestro["empresa"] == "TechCorp"


def test_auditoria_de_cadena_marca_el_transitivo():
    contactos = [
        {"nombre": "A", "email": "a@x.com", "telefono": "111111111"},
        {"nombre": "B", "email": "a@x.com", "telefono": "222222222"},
        {"nombre": "C", "email": "c@x.com", "telefono": "222222222"},
    ]
    motivos = [f["motivo"] for f in construir_auditoria(contactos)]
    # B comparte email con el maestro A; C no comparte nada directo con A.
    assert "email" in motivos
    assert "enlazado (transitivo)" in motivos


def test_volumen_no_rompe_y_es_rapido():
    # 3.000 filas: 1.500 personas, cada una repetida una vez. Debe quedar en 1.500.
    contactos = []
    for i in range(1500):
        contactos.append({"email": f"user{i}@x.com", "telefono": f"6000{i:05d}"})
        contactos.append({"email": f"USER{i}@x.com", "telefono": f"+34 6000{i:05d}"})
    unicos, duplicados = deduplicar(contactos)
    assert len(unicos) == 1500
    assert len(duplicados) == 1500

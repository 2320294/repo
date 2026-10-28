# Testes unitários com pytest para o motor de cargas e demanda
import pytest
from cargas import dimensionar_cargas
from demanda_qdc import potencia_instalada, proximo_disjuntor

def test_dimensionar_cargas_basico():
    res = dimensionar_cargas("Dormitório", 12.0, 14.0)
    assert res["Qtd Ilum."] == 2
    assert res["TUGs (Qtd)"] == 3
    assert res["Equipamento TUE"] == "Ar Condicionado"

def test_dimensionar_cargas_umida():
    res = dimensionar_cargas("Banheiro", 4.0, 8.0)
    assert res["Equipamento TUE"] == "Chuveiro Elétrico"
    assert res["Pot. Unit. TUE (W)"] == 5500

def test_proximo_disjuntor():
    assert proximo_disjuntor(14.5) == 16
    assert proximo_disjuntor(22.0) == 25
    assert proximo_disjuntor(63.0) == 63

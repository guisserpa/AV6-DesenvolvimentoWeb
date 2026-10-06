"""TAREFA DO ALUNO -- os cinco testes que faltam para os >= 8 do entregavel."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from app.dominio.motor_emergia import calcular_indices


def test_regressao_numerica_contra_a_planilha(fluxos_golden):
    """Compara os seis indices com os valores esperados do inventario de referencia."""
    resultado = calcular_indices(fluxos_golden, Decimal("1000"))
    esperados = {
        "y": Decimal("200.000000"),
        "eyr": Decimal("4.000000"),
        "elr": Decimal("0.739130"),
        "esi": Decimal("5.411765"),
        "eii": Decimal("0.184783"),
        "percentual_r": Decimal("57.500000"),
    }

    tolerancia = Decimal("1E-6")
    for campo, esperado in esperados.items():
        obtido = getattr(resultado, campo)
        assert abs(obtido - esperado) <= tolerancia


def test_quantizacao_unica_no_final():
    """Arredondar EYR e ELR antes da divisao altera o ESI final."""
    seis_casas = Decimal("1E-6")

    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN

        eyr = Decimal("200") / Decimal("50")
        elr = Decimal("85") / Decimal("115")

        arredondando_no_meio = (
            eyr.quantize(seis_casas) / elr.quantize(seis_casas)
        ).quantize(seis_casas)
        arredondando_so_no_final = (eyr / elr).quantize(seis_casas)

    assert arredondando_no_meio == Decimal("5.411768")
    assert arredondando_so_no_final == Decimal("5.411765")
    assert arredondando_no_meio != arredondando_so_no_final


def test_ordem_da_soma_com_magnitudes_divergentes():
    """Documenta o limite de 28 digitos para somas de magnitudes muito diferentes."""
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN

        grande = Decimal("1E20")
        pequeno = Decimal("1E-5")

        # Em 1E20, 28 digitos ainda preservam 1E-5; com dois operandos a soma
        # e comutativa e as duas ordens produzem exatamente o mesmo valor.
        assert grande + pequeno == pequeno + grande
        assert grande + pequeno == Decimal("100000000000000000000.00001")

        # O limite aparece abaixo de 1E-7 nessa magnitude. Somar parcelas de
        # 1E-8 uma a uma ao numero grande perde cada parcela por arredondamento;
        # agrupa-las primeiro acumula 1E-7, que ja e representavel.
        parcelas = [Decimal("1E-8")] * 10
        uma_a_uma = grande
        for parcela in parcelas:
            uma_a_uma += parcela

        agrupadas_primeiro = grande + sum(parcelas, Decimal(0))

    assert uma_a_uma == grande
    assert agrupadas_primeiro == Decimal("100000000000000000000.0000001")
    assert uma_a_uma != agrupadas_primeiro


def test_erro_de_dominio_responde_problem_json(cliente, corpo_golden):
    """Inventario sem fluxo renovavel deve sair como erro de dominio HTTP 422."""
    corpo_golden["fluxos"] = [
        {"recurso": "solo", "categoria": "N", "emergia_sej": "50"},
        {"recurso": "diesel", "categoria": "MN", "emergia_sej": "20"},
    ]

    r = cliente.post("/v1/safras/42/calculos", json=corpo_golden)

    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    corpo = r.json()
    for campo in ("type", "title", "status", "detail", "instance"):
        assert campo in corpo
    assert corpo["status"] == 422
    assert corpo["type"].endswith("/fluxos-insuficientes")


def test_campo_extra_no_corpo_da_requisicao_e_rejeitado(cliente, corpo_golden):
    """Campo desconhecido no DTO principal deve ser rejeitado com 422."""
    corpo_golden["energia_produto_jj"] = "1000"

    r = cliente.post("/v1/safras/42/calculos", json=corpo_golden)

    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert any(
        erro["campo"].endswith("energia_produto_jj")
        for erro in r.json().get("erros", [])
    )

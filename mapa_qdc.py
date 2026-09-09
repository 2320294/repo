import math
import re

TAMANHOS_PADRAO_QDC = (8, 12, 16, 18, 24, 36, 48, 54, 72)
RESERVA_MINIMA_MODULOS = 4
RESERVA_FRACAO = 0.20


def _polos_numero(valor, padrao=1):
    txt = str(valor or "").upper().strip()
    dig = "".join(ch for ch in txt if ch.isdigit())
    try:
        return max(1, int(dig))
    except Exception:
        return max(1, int(padrao))


def _polos_circuito(c):
    if c.get("polos"):
        return _polos_numero(c.get("polos"), 1)

    tensao = float(c.get("tensao", 0) or 0)
    tipo = str(c.get("tipo", "") or "").upper()

    if tipo == "TUE" or tensao > 127.5:
        return 2
    return 1


def _shape_qdc(posicoes):
    posicoes = int(posicoes or 0)
    shapes = {
        8: (1, 8),
        12: (1, 12),
        16: (2, 8),
        18: (2, 9),
        24: (2, 12),
        36: (3, 12),
        48: (4, 12),
        54: (3, 18),
        72: (4, 18),
    }
    if posicoes in shapes:
        return shapes[posicoes]

    if posicoes <= 12:
        return 1, max(1, posicoes)
    if posicoes <= 24:
        return 2, int(math.ceil(posicoes / 2))
    if posicoes <= 48:
        return int(math.ceil(posicoes / 12)), 12
    return int(math.ceil(posicoes / 18)), 18


def _proximo_qdc(necessidade):
    necessidade = max(1, int(necessidade))
    for tam in TAMANHOS_PADRAO_QDC:
        if tam >= necessidade:
            return tam
    return int(math.ceil(necessidade / 12.0) * 12)


def _qtd_dps(resumo_protecao, dg_polos):
    comp = str(
        (resumo_protecao or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    )
    if "3F" in comp:
        return 3
    if "2F" in comp:
        return 2
    if comp.startswith("F") or "F +" in comp:
        return 1
    return max(0, int(dg_polos or 0))


def _condutores_dr(dr, circuitos_por_numero):
    """
    Retorna os condutores que realmente atravessam o IDR com base na
    coluna `fase` dos circuitos já balanceados.

    Exemplos:
      circuitos só em A (127 V)        -> A + N
      circuitos A-B apenas (220 V)     -> A + B
      circuitos em A e B com 127 V     -> A + B + N
      grupo usando A/B/C e 127 V       -> A + B + C + N
    """
    numeros = [
        int(n or 0)
        for n in (dr.get("circuitos", []) or [])
        if int(n or 0) > 0
    ]

    fases = []
    precisa_neutro = False

    for numero in numeros:
        circuito = circuitos_por_numero.get(
            numero
        )

        if not circuito:
            continue

        for token in _fases_do_texto(
            circuito.get(
                "fase",
                ""
            )
        ):
            if (
                token in ("A", "B", "C")
                and token not in fases
            ):
                fases.append(
                    token
                )

        # Circuito monopolar utiliza fase + neutro.
        if _polos_circuito(
            circuito
        ) == 1:
            precisa_neutro = True

    fases = [
        token
        for token in ("A", "B", "C")
        if token in fases
    ]

    condutores = list(
        fases
    )

    if precisa_neutro:
        condutores.append(
            "N"
        )

    return condutores


def _polos_dr(dr, circuitos_por_numero):
    """
    Dimensiona fisicamente o IDR pelos condutores reais do grupo.

    Em padrão DIN residencial:
      - 2 condutores -> IDR 2P;
      - 3 ou 4 condutores -> IDR 4P.
    """
    condutores = _condutores_dr(
        dr,
        circuitos_por_numero
    )

    qtd = len(
        condutores
    )

    if qtd <= 2:
        return 2

    return 4



def _dispositivos_base(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda
):
    """
    Fase 13.6 Rev.31:
    organiza os dispositivos para uma vista frontal convencional:
    proteção geral/IDRs/DPS na fileira superior e disjuntores dos
    circuitos nas fileiras seguintes.
    """
    circuitos = [dict(c) for c in (circuitos or [])]
    resumo_drs = [dict(d) for d in (resumo_drs or [])]
    resumo_protecao = dict(resumo_protecao or {})
    resultado_demanda = dict(resultado_demanda or {})

    por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in circuitos
        if int(c.get("numero", 0) or 0) > 0
    }

    protecoes_gerais = []
    disjuntores_circuitos = []

    dg_a = resultado_demanda.get("disjuntor_geral_a")
    dg_polos = _polos_numero(
        resumo_protecao.get("dg_polos", ""),
        2
    )

    if dg_a:
        protecoes_gerais.append({
            "tipo": "DG",
            "identificador": "DG",
            "descricao": f"Disjuntor geral {dg_polos}P {int(dg_a)} A",
            "modulos": dg_polos,
            "grupo": "GERAL",
            "fase": "",
            "circuitos": "",
            "ambiente": "",
            "corrente_a": int(dg_a),
        })

    qtd_dps = _qtd_dps(
        resumo_protecao,
        dg_polos if dg_a else 0
    )
    fases_dps = ["A", "B", "C"][:qtd_dps]
    for i in range(1, qtd_dps + 1):
        fase_dps = fases_dps[i - 1] if i - 1 < len(fases_dps) else "A"
        protecoes_gerais.append({
            "tipo": "DPS",
            "identificador": f"DPS{i}",
            "descricao": f"DPS 1P - Fase {fase_dps}",
            "modulos": 1,
            "grupo": "GERAL",
            "fase": fase_dps,
            "circuitos": "",
            "ambiente": "",
            "corrente_a": None,
        })

    # IDRs ficam juntos na fileira superior.
    for dr in resumo_drs:
        gid = str(dr.get("dr", "") or "").strip()
        if not gid:
            continue

        numeros = [
            int(n or 0)
            for n in (dr.get("circuitos", []) or [])
            if int(n or 0) > 0
        ]
        itens = [
            por_numero[n]
            for n in numeros
            if n in por_numero
        ]
        if not itens:
            continue

        polos_dr = _polos_dr(
            dr,
            por_numero
        )
        nominal = dr.get("corrente_nominal_a")
        sens = dr.get("sensibilidade_ma")

        descr = f"{gid} {polos_dr}P"
        if nominal:
            descr += f" {int(nominal)} A"
        if sens:
            descr += f" {int(sens)} mA"

        condutores_grupo = _condutores_dr(
            dr,
            por_numero
        )

        fases_grupo = [
            token
            for token in condutores_grupo
            if token in ("A", "B", "C")
        ]

        protecoes_gerais.append({
            "tipo": "IDR",
            "identificador": gid,
            "descricao": descr,
            "modulos": polos_dr,
            "grupo": gid,
            "fase": "/".join(fases_grupo),
            "condutores": condutores_grupo,
            "circuitos": ",".join(f"C{n:02d}" for n in numeros),
            "ambiente": str(dr.get("descricao", "") or ""),
            "corrente_a": int(nominal) if nominal else None,
            "sensibilidade_ma": int(sens) if sens else None,
        })

    # Disjuntores terminais sempre ordenados por número de circuito.
    for c in sorted(
        circuitos,
        key=lambda x: int(x.get("numero", 0) or 0)
    ):
        n = int(c.get("numero", 0) or 0)
        if n <= 0:
            continue

        polos = _polos_circuito(c)
        corrente = int(c.get("disjuntor", 0) or 0)
        fase = str(c.get("fase", "") or "")
        gid = str(c.get("dr", "") or "").strip() or "SEM DR"
        ambiente = str(c.get("ambiente", "") or "")
        tipo = str(c.get("tipo", "") or "")
        potencia = float(c.get("potencia", 0) or 0)

        disjuntores_circuitos.append({
            "tipo": "DJ",
            "identificador": f"C{n:02d}",
            "descricao": f"C{n:02d} {polos}P {corrente} A",
            "modulos": polos,
            "grupo": gid,
            "fase": fase,
            "circuitos": f"C{n:02d}",
            "ambiente": ambiente,
            "tipo_circuito": tipo,
            "potencia_w": potencia,
            "corrente_a": corrente,
            "nova_fileira_antes": False,
        })

    if disjuntores_circuitos:
        # Força o aspecto convencional da referência:
        # dispositivos gerais em cima, circuitos na(s) fileira(s) abaixo.
        disjuntores_circuitos[0]["nova_fileira_antes"] = True

    return protecoes_gerais + disjuntores_circuitos



def _tentar_alocar(dispositivos, posicoes):
    linhas, colunas = _shape_qdc(posicoes)
    slots = [
        {
            "posicao": i + 1,
            "linha": (i // colunas) + 1,
            "coluna": (i % colunas) + 1,
            "identificador": "LIVRE",
            "tipo": "RESERVA",
            "grupo": "RESERVA",
            "fase": "",
        }
        for i in range(linhas * colunas)
    ]

    dispositivos_alocados = []
    cursor = 0

    for disp in dispositivos:
        largura = max(1, int(disp.get("modulos", 1) or 1))

        if (
            disp.get("nova_fileira_antes")
            and cursor % colunas != 0
        ):
            cursor = (
                (cursor // colunas) + 1
            ) * colunas

        linha_atual = cursor // colunas
        coluna_atual = cursor % colunas

        if coluna_atual + largura > colunas:
            cursor = (linha_atual + 1) * colunas

        if cursor + largura > len(slots):
            return None

        inicio = cursor + 1
        fim = cursor + largura

        d = dict(disp)
        d["posicao_inicial"] = inicio
        d["posicao_final"] = fim
        d["linha"] = (cursor // colunas) + 1
        dispositivos_alocados.append(d)

        for k in range(largura):
            idx = cursor + k
            slots[idx].update({
                "identificador": disp.get("identificador", ""),
                "tipo": disp.get("tipo", ""),
                "grupo": disp.get("grupo", ""),
                "fase": disp.get("fase", ""),
            })

        cursor += largura

    return {
        "linhas": linhas,
        "colunas": colunas,
        "slots": slots,
        "dispositivos": dispositivos_alocados,
    }



def gerar_mapa_fisico_qdc(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda,
    qdc_posicoes=None
):
    dispositivos = _dispositivos_base(
        circuitos,
        resumo_drs,
        resumo_protecao,
        resultado_demanda
    )

    modulos_dispositivos = sum(
        int(d.get("modulos", 0) or 0)
        for d in dispositivos
    )
    reserva_min = max(
        RESERVA_MINIMA_MODULOS,
        int(math.ceil(modulos_dispositivos * RESERVA_FRACAO))
    )

    necessidade = modulos_dispositivos + reserva_min
    posicoes = int(qdc_posicoes or 0)

    if posicoes < necessidade:
        posicoes = _proximo_qdc(necessidade)

    # Respeita quebra de linha sem dividir dispositivos.
    while True:
        layout = _tentar_alocar(
            dispositivos,
            posicoes
        )
        if layout is not None:
            break
        posicoes = _proximo_qdc(posicoes + 1)

    slots = layout["slots"]
    livres = sum(
        1
        for s in slots
        if s["tipo"] == "RESERVA"
    )

    resumo_protecao = dict(resumo_protecao or {})

    return {
        "status": "ok",
        "qdc_posicoes": posicoes,
        "linhas": layout["linhas"],
        "colunas": layout["colunas"],
        "modulos_dispositivos": modulos_dispositivos,
        "posicoes_livres": livres,
        "dispositivos": layout["dispositivos"],
        "slots": slots,
        "alimentador_composicao": resumo_protecao.get(
            "alimentador_composicao",
            ""
        ),
        "alimentador_fase_mm2": resumo_protecao.get(
            "alimentador_fase_mm2"
        ),
        "alimentador_neutro_mm2": resumo_protecao.get(
            "alimentador_neutro_mm2"
        ),
        "alimentador_pe_mm2": resumo_protecao.get(
            "alimentador_pe_mm2"
        ),
        "dg_polos": resumo_protecao.get(
            "dg_polos",
            ""
        ),
    }


def dataframe_slots(mapa):
    mapa = dict(mapa or {})
    linhas = int(mapa.get("linhas", 0) or 0)
    colunas = int(mapa.get("colunas", 0) or 0)
    slots = list(mapa.get("slots", []) or [])

    dados = []
    for linha in range(1, linhas + 1):
        row = {"Fileira": f"TRILHO {linha}"}
        for coluna in range(1, colunas + 1):
            slot = next(
                (
                    s
                    for s in slots
                    if int(s.get("linha", 0) or 0) == linha
                    and int(s.get("coluna", 0) or 0) == coluna
                ),
                None
            )
            if not slot:
                texto = "—"
            else:
                texto = str(slot.get("identificador", "LIVRE") or "LIVRE")
                fase = str(slot.get("fase", "") or "").strip()
                if fase and texto != "LIVRE":
                    texto += f" [{fase}]"
            row[f"P{((linha - 1) * colunas + coluna):02d}"] = texto
        dados.append(row)

    return dados


def _rect(msp, x1, y1, x2, y2, layer):
    return msp.add_lwpolyline(
        [
            (x1, y1),
            (x2, y1),
            (x2, y2),
            (x1, y2),
        ],
        close=True,
        dxfattribs={"layer": layer}
    )


def _line(msp, p1, p2, layer):
    return msp.add_line(
        p1,
        p2,
        dxfattribs={"layer": layer}
    )


def _polyline(msp, pontos, layer):
    return msp.add_lwpolyline(
        pontos,
        dxfattribs={"layer": layer}
    )




def _eh_ultimo_ponto_da_fase(x, pontos_fase, tolerancia=1e-6):
    """
    Convenção gráfica da vista frontal:
    o último ponto de uma pista de fase é somente uma mudança de direção.
    Portanto, não recebe círculo preenchido.
    """
    pontos = [
        float(v)
        for v in (pontos_fase or [])
    ]

    if not pontos:
        return False

    return abs(
        float(x)
        - max(pontos)
    ) <= tolerancia


def _desenhar_no_se_derivacao(msp, x, y, token, pontos_fase):
    """
    Desenha nó somente quando a conexão é uma derivação.
    No último ponto da pista a linha apenas vira/desce.
    """
    if not _eh_ultimo_ponto_da_fase(
        x,
        pontos_fase
    ):
        _no_fase_preenchido(
            msp,
            x,
            y,
            token
        )


def _no_fase_preenchido(msp, x, y, token, raio=0.045):
    """
    Nó elétrico de derivação:
    círculo sólido na mesma cor/layer da fase correspondente.
    Usado somente onde existe conexão/ramificação real.
    """
    layer = _layer_por_token(token)
    try:
        msp.add_circle(
            (float(x), float(y)),
            float(raio),
            dxfattribs={"layer": layer}
        )
        hatch = msp.add_hatch(
            color=256,
            dxfattribs={"layer": layer}
        )
        hatch.paths.add_edge_path().add_arc(
            center=(float(x), float(y)),
            radius=float(raio),
            start_angle=0.0,
            end_angle=360.0,
            ccw=True
        )
    except Exception:
        # fallback visual sólido por círculo concêntrico
        try:
            msp.add_circle(
                (float(x), float(y)),
                max(float(raio) * 0.55, 0.01),
                dxfattribs={"layer": layer}
            )
        except Exception:
            pass



def _circle(msp, center, radius, layer):
    return msp.add_circle(
        center,
        radius,
        dxfattribs={"layer": layer}
    )


def _text(msp, texto, x, y, altura, layer):
    try:
        ent = msp.add_text(
            str(texto),
            dxfattribs={
                "layer": layer,
                "height": altura,
            }
        )
        ent.dxf.insert = (x, y)
        return ent
    except Exception:
        return None


def _texto_central(msp, texto, x1, x2, y, altura, layer):
    texto = str(texto or "")
    # Centralização aproximada, estável em TEXT CAD.
    largura_est = len(texto) * altura * 0.58
    x = (x1 + x2) / 2.0 - largura_est / 2.0
    return _text(msp, texto, x, y, altura, layer)


def _fases_do_texto(fase):
    texto = str(fase or "").upper()
    fases = []
    for token in ("A", "B", "C"):
        if token in texto:
            fases.append(token)
    return fases or ["A"]


def _layer_por_token(token):
    token = str(token or "A").upper()
    if token == "N":
        return "PROJ_ELETRICA_QDC_NEUTRO"
    if token == "PE":
        return "PROJ_ELETRICA_QDC_PE"
    if token == "C":
        return "PROJ_ELETRICA_QDC_FASE_C"
    if token == "B":
        return "PROJ_ELETRICA_QDC_FASE_B"
    return "PROJ_ELETRICA_QDC_FASE_A"


def _layer_fase(fase):
    fase = str(fase or "").upper()
    if "C" in fase:
        return "PROJ_ELETRICA_QDC_FASE_C"
    if "B" in fase:
        return "PROJ_ELETRICA_QDC_FASE_B"
    return "PROJ_ELETRICA_QDC_FASE_A"


def _fases_alimentador(mapa):
    composicao = str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()

    if "3F" in composicao:
        return ["A", "B", "C"]
    if "2F" in composicao:
        return ["A", "B"]
    if "F" in composicao:
        return ["A"]
    return []


def _tem_neutro_alimentador(mapa):
    return "N" in str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()


def _tem_pe_alimentador(mapa):
    return "PE" in str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()


def _desenhar_trilho_segmento(msp, x1, x2, y, layer):
    if x2 <= x1:
        return
    _line(msp, (x1, y), (x2, y), layer)
    _line(msp, (x1, y - 0.08), (x2, y - 0.08), layer)

    passo = 0.34
    x = x1 + 0.18
    while x < x2 - 0.18:
        _line(
            msp,
            (x, y - 0.10),
            (min(x + 0.12, x2), y + 0.02),
            layer
        )
        x += passo


def _desenhar_trilho_com_vazios(
    msp,
    x1,
    x2,
    y,
    layer,
    geometrias
):
    """Desenha o trilho somente nas áreas externas aos aparelhos."""
    intervalos = sorted(
        [
            (
                float(g.get("x1", 0)) - 0.04,
                float(g.get("x2", 0)) + 0.04,
            )
            for g in (geometrias or [])
        ]
    )

    cursor = x1
    for a, b in intervalos:
        a = max(x1, a)
        b = min(x2, b)
        if a > cursor:
            _desenhar_trilho_segmento(
                msp,
                cursor,
                a,
                y,
                layer
            )
        cursor = max(cursor, b)

    if cursor < x2:
        _desenhar_trilho_segmento(
            msp,
            cursor,
            x2,
            y,
            layer
        )



def _desenhar_borne(msp, x, y, layer):
    _circle(msp, (x, y), 0.095, layer)
    _line(msp, (x - 0.045, y), (x + 0.045, y), layer)
    _line(msp, (x, y - 0.045), (x, y + 0.045), layer)


def _desenhar_barramento_vertical(
    msp,
    x,
    y_top,
    quantidade,
    layer,
    titulo,
    layer_txt
):
    espac = 0.34
    altura = max(0.9, quantidade * espac + 0.20)
    y_bottom = y_top - altura

    _rect(
        msp,
        x - 0.18,
        y_bottom,
        x + 0.18,
        y_top,
        layer
    )

    for i in range(quantidade):
        y = y_top - 0.18 - i * espac
        _desenhar_borne(
            msp,
            x,
            y,
            layer
        )

    _texto_central(
        msp,
        titulo,
        x - 0.55,
        x + 0.55,
        y_top + 0.25,
        0.12,
        layer_txt
    )

    return {
        "x": x,
        "y_top": y_top,
        "y_bottom": y_bottom,
        "bornes": quantidade,
    }


def _y_borne_barramento(barramento, indice):
    """
    Retorna o Y do borne físico do barramento vertical.
    indice=0 -> 1º borne; indice=1 -> 2º borne; etc.
    Deve permanecer sincronizado com _desenhar_barramento_vertical().
    """
    espac = 0.34
    return (
        float(barramento["y_top"])
        - 0.18
        - max(0, int(indice)) * espac
    )


def _desenhar_dispositivo(
    msp,
    disp,
    x1,
    y1,
    modulo_w,
    altura,
    layer,
    layer_txt
):
    modulos = max(1, int(disp.get("modulos", 1) or 1))
    x2 = x1 + modulo_w * modulos
    y2 = y1 + altura

    _rect(
        msp,
        x1,
        y1,
        x2,
        y2,
        layer
    )

    # Fase 13.6 Rev.31:
    # cada módulo/polo fica visualmente separado dentro do aparelho.
    # Assim 1P, 2P, 3P e 4P têm dimensões e leitura física distintas.
    if modulos > 1:
        for i_sep in range(1, modulos):
            x_sep = x1 + modulo_w * i_sep
            _line(
                msp,
                (x_sep, y1 + 0.08),
                (x_sep, y2 - 0.08),
                layer
            )

    # Bornes superior/inferior por polo/módulo.
    for i in range(modulos):
        cx = x1 + modulo_w * (i + 0.5)
        _desenhar_borne(
            msp,
            cx,
            y2 - 0.18,
            layer
        )
        _desenhar_borne(
            msp,
            cx,
            y1 + 0.18,
            layer
        )

    tipo = str(disp.get("tipo", "") or "")
    ident = str(disp.get("identificador", "") or "")
    corrente = disp.get("corrente_a")

    # Fase 13.6 Rev.31:
    # identificação principal dos dispositivos superiores:
    # DG, DPS e DR/IDR com height fixo 0.105.
    # Disjuntores terminais mantêm o tamanho anterior.
    altura_identificacao = (
        0.105
        if tipo in {"DG", "DPS", "IDR"}
        else 0.12
    )

    _texto_central(
        msp,
        ident,
        x1,
        x2,
        y1 + altura * 0.57,
        altura_identificacao,
        layer_txt
    )

    if corrente:
        _texto_central(
            msp,
            f"{int(corrente)}A",
            x1,
            x2,
            y1 + altura * 0.40,
            0.105,
            layer_txt
        )

    _texto_central(
        msp,
        f"{modulos}P",
        x1,
        x2,
        y2 - 0.35,
        0.060,
        layer_txt
    )

    if tipo == "IDR" and disp.get("sensibilidade_ma"):
        # Fase 13.6 Rev.31:
        # a sensibilidade do DR fica abaixo do símbolo de teste,
        # evitando sobreposição entre "30mA" e o círculo central.
        _texto_central(
            msp,
            f"{int(disp.get('sensibilidade_ma'))}mA",
            x1,
            x2,
            y1 + altura * 0.205,
            0.078,
            layer_txt
        )

    if tipo in {"DG", "DJ"}:
        # Pequena alavanca.
        cx = (x1 + x2) / 2.0
        _rect(
            msp,
            cx - 0.11,
            y1 + altura * 0.29,
            cx + 0.11,
            y1 + altura * 0.36,
            layer
        )

    if tipo == "DPS":
        cx = (x1 + x2) / 2.0
        _rect(
            msp,
            cx - 0.09,
            y1 + altura * 0.30,
            cx + 0.09,
            y1 + altura * 0.36,
            layer
        )

    if tipo == "IDR":
        cx = (x1 + x2) / 2.0
        _circle(
            msp,
            (cx, y1 + altura * 0.33),
            0.075,
            layer
        )
        _text(
            msp,
            "T",
            cx - 0.025,
            y1 + altura * 0.305,
            0.055,
            layer_txt
        )

    return {
        "x1": x1,
        "x2": x2,
        "cx": (x1 + x2) / 2.0,
        "y1": y1,
        "y2": y2,
        "modulos": modulos,
        "tipo": tipo,
        "identificador": ident,
    }


def _x_passagem_lateral_disjuntor(geom, lado="esq", afastamento=0.08):
    """
    Retorna um eixo X de passagem FORA do corpo do disjuntor.
    Usado por condutores que apenas atravessam a região verticalmente,
    sem entrar eletricamente naquele aparelho.
    """
    if str(lado).lower().startswith("d"):
        return float(geom["x2"]) + float(afastamento)
    return float(geom["x1"]) - float(afastamento)


def _centros_polos(geom):
    modulos = max(
        1,
        int(
            geom.get(
                "modulos",
                1
            )
            or 1
        )
    )
    largura = (
        float(geom["x2"])
        - float(geom["x1"])
    )
    passo = largura / modulos
    return [
        float(geom["x1"])
        + passo * (i + 0.5)
        for i in range(modulos)
    ]


def _indice_fase(token):
    token = str(
        token
        or ""
    ).upper()

    return {
        "A": 0,
        "B": 1,
        "C": 2,
    }.get(
        token,
        0
    )


def _mapa_condutores_polos(disp, geom):
    """
    Mapeia cada condutor elétrico a um polo físico único.
    Nunca permite duas fases no mesmo polo.
    """
    centros = _centros_polos(
        geom
    )

    tipo = str(
        disp.get(
            "tipo",
            ""
        )
        or ""
    ).upper()

    if tipo == "DG":
        ordem = [
            "A",
            "B",
            "C",
        ][:len(
            centros
        )]

    elif tipo == "IDR":
        condutores = [
            str(c).upper()
            for c in (
                disp.get(
                    "condutores",
                    []
                )
                or []
            )
        ]

        if len(centros) >= 4:
            # Ordem física convencional e estável.
            ordem = [
                "A",
                "B",
                "C",
                "N",
            ]
        else:
            ordem = list(
                condutores
            )[:len(
                centros
            )]

    else:
        ordem = _fases_do_texto(
            disp.get(
                "fase",
                ""
            )
        )[:len(
            centros
        )]

    mapa = {}

    for idx, condutor in enumerate(
        ordem
    ):
        if idx >= len(
            centros
        ):
            break

        mapa[
            condutor
        ] = centros[
            idx
        ]

    return mapa


def _polo_para_fase(disp, geom, token):
    token = str(
        token
        or ""
    ).upper()

    mapa = _mapa_condutores_polos(
        disp,
        geom
    )

    if token in mapa:
        return mapa[
            token
        ]

    centros = _centros_polos(
        geom
    )

    return centros[
        0
    ]



def _mapa_fases_polos(disp, geom):
    """Associa as fases elétricas reais aos polos físicos do aparelho."""
    fases = _fases_do_texto(
        disp.get(
            "fase",
            ""
        )
    )
    centros = _centros_polos(
        geom
    )

    resultado = []
    for idx, fase in enumerate(fases):
        if idx >= len(centros):
            break
        resultado.append(
            (
                fase,
                centros[idx]
            )
        )
    return resultado


def _quebrar_texto(texto, max_chars=27):
    palavras = str(texto or "").split()
    linhas = []
    atual = ""
    for palavra in palavras:
        teste = palavra if not atual else atual + " " + palavra
        if len(teste) <= max_chars:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas[:3]


def desenhar_mapa_fisico_qdc(
    msp,
    mapa,
    polilinhas_ambientes
):
    """
    Fase 13.6 Rev.31 — QDC executivo no CAD.

    O desenho passa a se aproximar de um diagrama de montagem real:
    trilhos DIN, dispositivos frontais, barramento pente, barramentos
    N/PE, condutores por função/fase e quadro lateral de circuitos.
    """
    mapa = dict(mapa or {})
    if mapa.get("status") != "ok":
        return None

    pontos = []
    for pol in polilinhas_ambientes or []:
        pontos.extend(list(pol or []))

    max_x = max((p[0] for p in pontos), default=0.0)
    max_y = max((p[1] for p in pontos), default=10.0)

    # Unifilar permanece à esquerda; vista frontal nasce à direita.
    x0 = max_x + 25.4
    y0 = max_y

    L = "PROJ_ELETRICA_MAPA_QDC"
    LT = "PROJ_ELETRICA_MAPA_QDC_TEXTO"
    LA = "PROJ_ELETRICA_QDC_FASE_A"
    LB = "PROJ_ELETRICA_QDC_FASE_B"
    LC = "PROJ_ELETRICA_QDC_FASE_C"
    LN = "PROJ_ELETRICA_QDC_NEUTRO"
    LPE = "PROJ_ELETRICA_QDC_PE"
    LP = "PROJ_ELETRICA_QDC_PENTE"

    dispositivos = list(mapa.get("dispositivos", []) or [])
    gerais = [d for d in dispositivos if d.get("tipo") in {"DG", "DPS", "IDR"}]
    circuitos = [d for d in dispositivos if d.get("tipo") == "DJ"]

    # Fase 13.6 Rev.31:
    # a vista frontal mantém a ordem lógica SEM DR, DR1, DR2, DR3...
    # aproveitando continuamente os módulos disponíveis do mesmo trilho.
    def _ordem_grupo_qdc(d):
        grupo = str(d.get("grupo", "") or "SEM DR").strip().upper()
        if grupo == "SEM DR":
            ordem = 0
        else:
            m = re.search(r"(\\d+)", grupo)
            ordem = int(m.group(1)) if m else 999
        # Rev.18: ordem física por fase dentro de cada grupo.
        fases = tuple(_fases_do_texto(d.get("fase", "")))
        assinatura_fase = {
            ("A",): 0, ("B",): 1, ("C",): 2,
            ("A", "B"): 3, ("A", "C"): 4,
            ("B", "C"): 5, ("A", "B", "C"): 6,
        }.get(fases, 99)

        ident = str(d.get("identificador", "") or "")
        m_c = re.search(r"(\\d+)", ident)
        circuito = int(m_c.group(1)) if m_c else 9999
        return (ordem, grupo, assinatura_fase, circuito)

    circuitos = sorted(circuitos, key=_ordem_grupo_qdc)

    colunas = int(mapa.get("colunas", 0) or 0)
    linhas = int(mapa.get("linhas", 0) or 0)

    # Fase 13.6 Rev.31 — padrão modular do QDC.
    # Cada polo ocupa exatamente 0,45 unidade CAD:
    # 1P=0,45 | 2P=0,90 | 3P=1,35 | 4P=1,80.
    # A mesma regra vale para DJ/DG, IDR/DR e DPS.
    modulo_w = 0.45
    disp_h = 1.60
    margem_x = 1.15
    painel_circuitos_w = 10.20
    separacao_painel = 1.60
    modulos_superiores_previstos = sum(
        max(1, int(d.get("modulos", 1) or 1))
        for d in gerais
    )
    area_din_w = max(
        9.6,
        colunas * modulo_w + 2.30,
        modulos_superiores_previstos * modulo_w
        + max(0, len(gerais) - 1) * 0.06
        + 2.60
    )
    largura = (
        area_din_w
        + separacao_painel
        + painel_circuitos_w
        + 1.00
    )

    # Fase 13.6 Rev.31:
    # os circuitos continuam ordenados por grupo elétrico, porém grupos
    # diferentes podem ocupar o mesmo trilho. Só abre um novo trilho quando
    # a capacidade física de módulos do trilho atual terminar.
    trilhos_circuitos = max(
        1,
        int(math.ceil(
            sum(
                max(1, int(d.get("modulos", 1) or 1))
                for d in circuitos
            )
            / max(1, colunas)
        ))
    )
    altura_corpo = 4.40 + trilhos_circuitos * 3.15
    altura = max(11.5, altura_corpo + 2.00)
    ybase = y0 - altura

    # Moldura geral e cabeçalho.
    _rect(
        msp,
        x0,
        ybase,
        x0 + largura,
        y0,
        L
    )

    _text(
        msp,
        "QDC - QUADRO DE DISTRIBUICAO DE CIRCUITOS",
        x0 + 0.55,
        y0 - 0.55,
        0.25,
        LT
    )
    _text(
        msp,
        "VISTA FRONTAL - DIAGRAMA DE MONTAGEM E LIGACOES | FASE 13.6 REV.31",
        x0 + 0.55,
        y0 - 0.92,
        0.11,
        LT
    )

    # Região frontal do quadro.
    qx1 = x0 + 0.55
    qx2 = x0 + area_din_w
    qy_top = y0 - 1.35
    qy_bottom = ybase + 0.75

    _rect(
        msp,
        qx1,
        qy_bottom,
        qx2,
        qy_top,
        L
    )

    # Barramentos PE e N laterais.
    qtd_pe = max(4, len(circuitos) + 1)
    qtd_n = max(
        4,
        sum(
            1
            for d in circuitos
            if int(d.get("modulos", 1) or 1) == 1
        ) + 1
    )

    pe = _desenhar_barramento_vertical(
        msp,
        qx1 + 0.48,
        qy_top - 1.15,
        qtd_pe,
        LPE,
        "PE",
        LT
    )
    neutro = _desenhar_barramento_vertical(
        msp,
        qx2 - 0.48,
        qy_top - 1.15,
        qtd_n,
        LN,
        "N",
        LT
    )

    din_x1 = qx1 + 1.15
    din_x2 = qx2 - 1.15

    # -------------------------
    # Fileira superior: DG/DPS/IDR
    # -------------------------
    top_rail_y = qy_top - 2.25

    # Fase 13.6 Rev.31:
    # a fileira superior é dimensionada pela quantidade real de módulos
    # DG + DPS + IDRs. Nunca descarta o último aparelho por falta de folga.
    total_modulos_gerais = sum(
        max(
            1,
            int(
                d.get(
                    "modulos",
                    1
                )
                or 1
            )
        )
        for d in gerais
    )

    gap_geral = 0.06
    qtd_gaps_gerais = max(
        0,
        len(gerais) - 1
    )

    largura_util_gerais = max(
        1.0,
        (
            din_x2
            - din_x1
            - 0.30
            - qtd_gaps_gerais * gap_geral
        )
    )

    # Não comprimir os dispositivos superiores: a largura física é
    # sempre 0,45 x quantidade de polos.
    modulo_w_geral = modulo_w

    # Fase 13.6 Rev.31 — eixo geométrico único do "miolo" do QDC.
    # Todo o conjunto interno é centralizado entre os barramentos PE e N.
    # A fileira superior e as fileiras inferiores compartilham a mesma
    # lateral esquerda de referência, evitando deslocamento visual.
    centro_miolo_qdc = (pe["x"] + neutro["x"]) / 2.0

    largura_superior_real = (
        total_modulos_gerais * modulo_w_geral
        + max(0, len(gerais) - 1) * gap_geral
    )

    # Calcula a maior largura efetivamente usada por uma fileira inferior.
    larguras_fileiras_inferiores = []
    idx_largura = 0
    while idx_largura < len(circuitos):
        modulos_usados = 0
        qtd_dispositivos_fileira = 0
        largura_fileira = 0.0

        while idx_largura < len(circuitos):
            d_larg = circuitos[idx_largura]
            mod_larg = max(1, int(d_larg.get("modulos", 1) or 1))
            if modulos_usados + mod_larg > colunas:
                break

            if qtd_dispositivos_fileira:
                largura_fileira += 0.10
            largura_fileira += mod_larg * modulo_w

            modulos_usados += mod_larg
            qtd_dispositivos_fileira += 1
            idx_largura += 1

        if qtd_dispositivos_fileira:
            larguras_fileiras_inferiores.append(largura_fileira)
        else:
            break

    largura_miolo_qdc = max(
        [largura_superior_real] + larguras_fileiras_inferiores
    )

    x_miolo_inicio = centro_miolo_qdc - largura_miolo_qdc / 2.0

    x = x_miolo_inicio
    geral_geom = []

    for d in gerais:
        geom = _desenhar_dispositivo(
            msp,
            d,
            x,
            top_rail_y - 0.85,
            modulo_w_geral,
            disp_h,
            L,
            LT
        )
        geral_geom.append(
            (
                d,
                geom
            )
        )
        x = (
            geom["x2"]
            + gap_geral
        )

    _desenhar_trilho_com_vazios(
        msp,
        din_x1,
        din_x2,
        top_rail_y - 0.05,
        L,
        [g for _, g in geral_geom]
    )

    # Todos os dispositivos gerais calculados precisam estar presentes
    # na vista frontal; não existe descarte visual de DR/DPS/DG.
    if len(
        geral_geom
    ) != len(
        gerais
    ):
        raise RuntimeError(
            "Falha ao representar todos os dispositivos gerais do QDC."
        )

    # Entrada elétrica e distribuição superior por fase.
    dg_geoms = [
        (d, g)
        for d, g in geral_geom
        if d.get("tipo") == "DG"
    ]

    # Barramentos de fase separados verticalmente.
    # Todas as derivações "morrem" exatamente na barra da respectiva fase.
    # Fase 13.6 Rev.31:
    # corredores exclusivos para A/B/C. O afastamento é propositalmente
    # maior para impedir que uma derivação vertical coincida visualmente
    # com o barramento horizontal de outra fase.
    ESPACAMENTO_BARRAMENTOS_FASE = 0.30
    # Fase 13.6 Rev.31 — grade vertical equidistante das seis linhas
    # As seis linhas/cabos principais do QDC passam a ocupar níveis paralelos
    # com passo único. Isso evita a sensação de linhas comprimidas em uma
    # região e abertas em outra, mantendo A/B/C alinhadas aos bornes do DG.
    # Fase 13.6 Rev.31:
    # O espaçamento vertical é calculado conforme a quantidade REAL
    # de cabos presentes na entrada. Assim monofásico, bifásico e
    # trifásico mantêm a mesma proporção visual.
    #
    # Fórmula:
    # espaçamento = distância disponível / quantidade de cabos
    #
    # A referência superior é o PE e a inferior é o topo do DG.
    dg_ref_geom = dg_geoms[0][1] if dg_geoms else None
    y_topo_dg = (
        dg_ref_geom["y2"]
        if dg_ref_geom is not None
        else top_rail_y + 0.75
    )

    fases_presentes = _fases_alimentador(mapa)
    tem_neutro_grade = _tem_neutro_alimentador(mapa)
    tem_pe_grade = _tem_pe_alimentador(mapa)

    # Quantidade REAL de cabos da entrada:
    # fases existentes + N (se houver) + PE (se houver).
    qtd_cabos_grade = max(
        1,
        len(fases_presentes)
        + (1 if tem_neutro_grade else 0)
        + (1 if tem_pe_grade else 0)
    )

    # Referência superior = linha PE/N de entrada.
    # Referência inferior = topo físico do DG.
    y_pe_superior = qy_top - 0.62
    distancia_disponivel = max(
        0.60,
        y_pe_superior - y_topo_dg
    )

    # REGRA EXATA SOLICITADA:
    # espaçamento = distância entre cabo PE e topo do DG / nº de cabos
    ESPACAMENTO_VERTICAL_CABOS = (
        distancia_disponivel
        / qtd_cabos_grade
    )

    # PE e N de entrada compartilham o nível superior,
    # seguindo em sentidos opostos.
    niveis_cabos_qdc = {
        "PE": y_pe_superior,
        "N": y_pe_superior,
    }

    # As fases ocupam níveis sucessivos abaixo da linha PE/N.
    for idx, token in enumerate(
        fases_presentes,
        start=1
    ):
        niveis_cabos_qdc[token] = (
            y_pe_superior
            - idx * ESPACAMENTO_VERTICAL_CABOS
        )

    # O neutro de alimentação dos DRs ocupa o próximo nível da grade,
    # também calculado pelo MESMO espaçamento.
    indice_n_idr = (
        len(fases_presentes)
        + 1
    )
    niveis_cabos_qdc["N_IDR"] = (
        y_pe_superior
        - indice_n_idr * ESPACAMENTO_VERTICAL_CABOS
    )

    barramentos_y = {
        token: niveis_cabos_qdc[token]
        for token in fases_presentes
        if token in niveis_cabos_qdc
    }

    # REV.14 — regra dos barramentos laterais:
    # - entrada PE -> 1º borne do barramento PE;
    # - entrada N  -> 1º borne do barramento N, no mesmo alinhamento do PE;
    # - alimentação N dos IDRs -> 2º borne do barramento N;
    # - do 2º borne, N segue à esquerda e depois sobe ao alinhamento calculado;
    # - nó azul apenas nos pontos reais de derivação.

    if dg_geoms:
        dg_disp, dg = dg_geoms[0]

        fases_entrada = _fases_alimentador(
            mapa
        )

        tem_neutro = _tem_neutro_alimentador(
            mapa
        )

        tem_pe = _tem_pe_alimentador(
            mapa
        )

        # ====================================================
        # FASE 13.6 REV.31 — ENTRADA DA REDE
        # ====================================================
        # Convenção visual definida pelo usuário:
        # A | B | C | PE | N
        #
        # A/B/C nascem EXATAMENTE alinhadas aos bornes do DG.
        # PE e N continuam à direita, usando o mesmo passo horizontal
        # dos bornes do DG. Isso elimina cruzamentos/desvios desnecessários
        # logo na entrada do diagrama.
        polos_dg = _centros_polos(dg)

        # Passo real entre polos do DG; fallback apenas para geometria atípica.
        if len(polos_dg) >= 2:
            ESPACAMENTO_ENTRADA = abs(polos_dg[1] - polos_dg[0])
        else:
            ESPACAMENTO_ENTRADA = 0.42

        x_por_condutor = {}
        for idx_fase, token in enumerate(fases_entrada):
            if idx_fase < len(polos_dg):
                x_por_condutor[token] = polos_dg[idx_fase]

        # Após a última fase: primeiro PE e depois N.
        x_ultima_fase = (
            polos_dg[min(len(fases_entrada), len(polos_dg)) - 1]
            if polos_dg and fases_entrada
            else dg["cx"]
        )
        proximo_x = x_ultima_fase + ESPACAMENTO_ENTRADA
        if tem_pe:
            x_por_condutor["PE"] = proximo_x
            proximo_x += ESPACAMENTO_ENTRADA
        if tem_neutro:
            x_por_condutor["N"] = proximo_x

        y_inicio_entrada = qy_top - 0.15
        y_rotulos_entrada = qy_top - 0.38

        # Fases: ligação vertical direta, sem degrau horizontal.
        for idx_fase, token in enumerate(fases_entrada):
            if idx_fase >= len(polos_dg) or token not in x_por_condutor:
                break
            x_fase = x_por_condutor[token]
            _line(
                msp,
                (x_fase, y_inicio_entrada),
                (x_fase, dg["y2"]),
                _layer_por_token(token)
            )
            _text(msp, token, x_fase - 0.03, y_rotulos_entrada, 0.080, LT)

        # PE vem antes do N e segue diretamente ao barramento de proteção.
        if tem_pe:
            x_pe = x_por_condutor["PE"]
            _polyline(
                msp,
                [
                    (x_pe, y_inicio_entrada),
                    (x_pe, niveis_cabos_qdc.get("PE", qy_top - 0.62)),
                    (pe["x"], niveis_cabos_qdc.get("PE", qy_top - 0.62)),
                    (pe["x"], _y_borne_barramento(pe, 0)),
                ],
                LPE
            )
            _text(msp, "PE", x_pe - 0.05, y_rotulos_entrada, 0.080, LT)

        # Fase 13.6 Rev.31:
        # O N de entrada deve espelhar exatamente a geometria do PE:
        # sai da entrada, atinge o MESMO alinhamento horizontal do PE
        # e segue para a direita até o 1º borne do barramento N.
        if tem_neutro:
            x_n = x_por_condutor["N"]

            y_pe_referencia = niveis_cabos_qdc.get(
                "PE",
                qy_top - 0.62
            )

            _polyline(
                msp,
                [
                    (x_n, y_inicio_entrada),
                    (x_n, y_pe_referencia),
                    (neutro["x"], y_pe_referencia),
                    (neutro["x"], _y_borne_barramento(neutro, 0)),
                ],
                LN
            )
            _text(
                msp,
                "N",
                x_n - 0.03,
                y_rotulos_entrada,
                0.080,
                LT
            )

        bitola_fase = mapa.get(
            "alimentador_fase_mm2"
        )

        composicao_txt = str(
            mapa.get(
                "alimentador_composicao",
                ""
            )
            or ""
        )

        rotulo_entrada = (
            "ENTRADA DA REDE"
            + (
                f" | {composicao_txt}"
                if composicao_txt
                else ""
            )
            + (
                f" | FASE {float(bitola_fase):g} mm2"
                if bitola_fase
                else ""
            )
        )

        # Título em linha própria, acima das identificações A/B/C/N/PE.
        _text(
            msp,
            rotulo_entrada,
            din_x1,
            qy_top + 0.02,
            0.080,
            LT
        )

    if geral_geom:
        fases_disponiveis = _fases_alimentador(
            mapa
        )

        # ----------------------------------------------------
        # FASE 13.6 REV.31 — CONVENÇÃO DE NÓS DE DERIVAÇÃO
        # ----------------------------------------------------
        # Primeiro levantamos TODOS os pontos reais ligados a cada fase.
        # Assim o barramento termina exatamente na última ligação:
        # nesse último ponto a linha apenas vira/desce e NÃO recebe bolinha.
        pontos_superiores_por_fase = {
            token: []
            for token in fases_disponiveis
        }

        if dg_geoms:
            dg_disp, dg_geom = dg_geoms[0]
            for token in fases_disponiveis:
                pontos_superiores_por_fase[token].append(
                    _polo_para_fase(
                        dg_disp,
                        dg_geom,
                        token
                    )
                )

        for d, g in geral_geom:
            tipo_d = str(
                d.get(
                    "tipo",
                    ""
                )
                or ""
            ).upper()

            if tipo_d == "DPS":
                token = _fases_do_texto(
                    d.get(
                        "fase"
                    )
                )[0]

                if token in pontos_superiores_por_fase:
                    pontos_superiores_por_fase[token].append(
                        _centros_polos(
                            g
                        )[0]
                    )

            elif tipo_d == "IDR":
                mapa_polos = _mapa_condutores_polos(
                    d,
                    g
                )

                for token in ("A", "B", "C"):
                    if (
                        token in pontos_superiores_por_fase
                        and token in (
                            d.get(
                                "condutores",
                                []
                            )
                            or []
                        )
                        and token in mapa_polos
                    ):
                        pontos_superiores_por_fase[token].append(
                            mapa_polos[
                                token
                            ]
                        )

        # Cada pista de fase termina no último consumidor daquela fase.
        # Não há prolongamento "morto" após a última derivação.
        for token in fases_disponiveis:
            pontos_token = pontos_superiores_por_fase.get(
                token,
                []
            )

            if len(
                pontos_token
            ) >= 2:
                _line(
                    msp,
                    (
                        min(
                            pontos_token
                        ),
                        barramentos_y[token]
                    ),
                    (
                        max(
                            pontos_token
                        ),
                        barramentos_y[token]
                    ),
                    _layer_por_token(
                        token
                    )
                )

        # DG -> barramentos.
        if dg_geoms:
            dg_disp, dg_geom = dg_geoms[0]

            for token in fases_disponiveis:
                x_polo_dg = _polo_para_fase(
                    dg_disp,
                    dg_geom,
                    token
                )

                _line(
                    msp,
                    (
                        x_polo_dg,
                        dg_geom["y2"]
                    ),
                    (
                        x_polo_dg,
                        barramentos_y[token]
                    ),
                    _layer_por_token(
                        token
                    )
                )

                _desenhar_no_se_derivacao(
                    msp,
                    x_polo_dg,
                    barramentos_y[token],
                    token,
                    pontos_superiores_por_fase.get(
                        token,
                        []
                    )
                )

        # DPS: fase -> polo físico do DPS -> PE.
        # Rev.19: o PE dos DPS é representado como um único tronco
        # horizontal. L1/L2... recebem nó apenas quando são derivações
        # reais; o último DPS é apenas a curva final horizontal -> vertical.
        dps_geom_pe = []

        for d, g in geral_geom:
            if d.get("tipo") != "DPS":
                continue

            token = _fases_do_texto(
                d.get(
                    "fase"
                )
            )[0]

            polos_dps = _centros_polos(
                g
            )
            x_polo = polos_dps[0]

            _line(
                msp,
                (
                    x_polo,
                    barramentos_y[token]
                ),
                (
                    x_polo,
                    g["y2"]
                ),
                _layer_por_token(
                    token
                )
            )

            _desenhar_no_se_derivacao(
                msp,
                x_polo,
                barramentos_y[token],
                token,
                pontos_superiores_por_fase.get(
                    token,
                    []
                )
            )

            _texto_central(
                msp,
                f"L{('A','B','C').index(token)+1}",
                g["x1"],
                g["x2"],
                g["y1"] - 0.13,
                0.065,
                LT
            )

            dps_geom_pe.append((d, g))

        if dps_geom_pe:
            y_pe_dps = min(
                g["y1"] - 0.28
                for _, g in dps_geom_pe
            )

            xs_pe_dps = sorted(
                g["cx"]
                for _, g in dps_geom_pe
            )

            x_ultimo_pe_dps = max(xs_pe_dps)

            # Tronco PE termina exatamente no último DPS.
            _line(
                msp,
                (pe["x"], y_pe_dps),
                (x_ultimo_pe_dps, y_pe_dps),
                LPE
            )

            for d_dps, g_dps in dps_geom_pe:
                x_dps = g_dps["cx"]

                _line(
                    msp,
                    (x_dps, g_dps["y1"]),
                    (x_dps, y_pe_dps),
                    LPE
                )

                # Nó somente nas derivações intermediárias.
                # Em trifásico: L1 e L2 recebem bolinha; L3 é a curva final.
                if abs(x_dps - x_ultimo_pe_dps) > 1e-9:
                    _no_fase_preenchido(
                        msp,
                        x_dps,
                        y_pe_dps,
                        "PE"
                    )

        # IDRs: cada fase entra em seu polo físico correspondente.
        for d, g in geral_geom:
            if d.get("tipo") != "IDR":
                continue

            mapa_polos = _mapa_condutores_polos(
                d,
                g
            )

            fases_idr = [
                token
                for token in ("A", "B", "C")
                if token in (
                    d.get(
                        "condutores",
                        []
                    )
                    or []
                )
            ]

            for token in fases_idr:
                if token not in barramentos_y:
                    continue

                xx = mapa_polos.get(
                    token
                )

                if xx is None:
                    continue

                _line(
                    msp,
                    (
                        xx,
                        g["y2"]
                    ),
                    (
                        xx,
                        barramentos_y[token]
                    ),
                    _layer_por_token(
                        token
                    )
                )

                _desenhar_no_se_derivacao(
                    msp,
                    xx,
                    barramentos_y[token],
                    token,
                    pontos_superiores_por_fase.get(
                        token,
                        []
                    )
                )

            # O neutro dos IDRs é montado depois em uma única linha,
            # derivada exclusivamente do 2º borne do barramento N.

    # ========================================================
    # FASE 13.6 REV.31 — NEUTRO DOS IDRs PELO 2º BORNE
    # ========================================================
    # Regras:
    # - N de entrada usa o 1º borne do barramento N.
    # - alimentação N dos IDRs usa o 2º borne do barramento N.
    # - do 2º borne, o cabo segue PRIMEIRO para a esquerda;
    # - depois sobe verticalmente até o nível correto da grade calculada;
    # - nesse nível segue horizontalmente e deriva para os bornes N dos IDRs;
    # - bolinha azul somente onde existe derivação real.
    idrs_com_neutro = []

    for d_idr, g_idr in geral_geom:
        if d_idr.get("tipo") != "IDR":
            continue

        condutores_idr = d_idr.get("condutores", []) or []
        if "N" not in condutores_idr:
            continue

        mapa_polos_idr = _mapa_condutores_polos(
            d_idr,
            g_idr
        )
        if "N" not in mapa_polos_idr:
            continue

        idrs_com_neutro.append(
            (d_idr, g_idr, mapa_polos_idr["N"])
        )

    if idrs_com_neutro:
        y_borne_n_2 = _y_borne_barramento(
            neutro,
            1
        )

        # O alinhamento do N dos IDRs é exatamente o nível N_IDR
        # calculado pela grade dinâmica:
        # (PE -> topo do DG) / quantidade real de cabos.
        y_alinhamento_n_idr = niveis_cabos_qdc[
            "N_IDR"
        ]

        xs_n_idr = sorted(
            x_n_idr
            for _, _, x_n_idr in idrs_com_neutro
        )

        x_idr_mais_direita = max(xs_n_idr)
        x_idr_mais_esquerda = min(xs_n_idr)

        # Pequeno recuo à esquerda do barramento N antes da subida.
        x_recuo_n = (
            neutro["x"]
            - max(
                0.22,
                ESPACAMENTO_VERTICAL_CABOS
            )
        )

        # 2º borne -> esquerda -> sobe até o alinhamento calculado.
        _polyline(
            msp,
            [
                (neutro["x"], y_borne_n_2),
                (x_recuo_n, y_borne_n_2),
                (x_recuo_n, y_alinhamento_n_idr),
            ],
            LN
        )

        # Linha principal do N dos IDRs, no alinhamento correto.
        _line(
            msp,
            (x_recuo_n, y_alinhamento_n_idr),
            (x_idr_mais_esquerda, y_alinhamento_n_idr),
            LN
        )

        # Derivações para os bornes N superiores.
        for d_idr, g_idr, x_n_idr in idrs_com_neutro:
            _line(
                msp,
                (x_n_idr, y_alinhamento_n_idr),
                (x_n_idr, g_idr["y2"]),
                LN
            )

            # Bolinha azul apenas quando o ponto é uma derivação real
            # e a linha principal continua para a esquerda.
            if x_n_idr > x_idr_mais_esquerda + 1e-9:
                _no_fase_preenchido(
                    msp,
                    x_n_idr,
                    y_alinhamento_n_idr,
                    "N"
                )

    # -------------------------
    # Fileiras inferiores: circuitos
    # -------------------------
    y_rail = top_rail_y - 3.15
    idx_circ = 0
    circuitos_geom = []

    # Rev.18: a fileira inferior usa exatamente a mesma lateral
    # esquerda do primeiro dispositivo superior aprovado.
    x_alinhamento_dispositivos = (
        x_miolo_inicio
        if gerais
        else centro_miolo_qdc - largura_miolo_qdc / 2.0
    )

    for trilho in range(trilhos_circuitos):
        x = x_alinhamento_dispositivos
        usados = 0

        grupos_na_fileira = []

        while idx_circ < len(circuitos):
            d = circuitos[idx_circ]
            grupo_d = str(
                d.get("grupo", "") or "SEM DR"
            ).strip().upper()

            # Mantém a sequência SEM DR -> DR1 -> DR2 -> DR3...
            # mas NÃO força mudança de trilho na troca de grupo.
            if grupo_d not in grupos_na_fileira:
                grupos_na_fileira.append(grupo_d)

            mod = max(1, int(d.get("modulos", 1) or 1))

            if usados + mod > colunas:
                break

            geom = _desenhar_dispositivo(
                msp,
                d,
                x,
                y_rail - 0.85,
                modulo_w,
                disp_h,
                L,
                LT
            )
            circuitos_geom.append((d, geom))

            # Rev.22: identificação de condutores fica concentrada
            # na parte inferior do QDC, junto à saída do circuito.
            # Guarda somente a informação elétrica necessária para
            # montar a saída do circuito fora do corpo do disjuntor.
            geom["tem_neutro"] = (
                mod == 1
            )

            x = geom["x2"] + 0.10
            usados += mod
            idx_circ += 1

        desta_fileira_geom = [
            g
            for d, g in circuitos_geom
            if abs(
                g["y1"]
                - (y_rail - 0.85)
            )
            < 0.05
        ]

        _desenhar_trilho_com_vazios(
            msp,
            din_x1,
            din_x2,
            y_rail - 0.05,
            L,
            desta_fileira_geom
        )

        # Fase 13.6 Rev.31 — SAÍDAS DOS CIRCUITOS
        # ------------------------------------------------------------
        # Cada circuito sai pela parte inferior do respectivo disjuntor
        # com condutores verticais retos e identificação alinhada.
        #
        # 1P / 127 V: F + N + PE
        # 2P / 220 V: F + F + PE
        # 3P:         F + F + F + PE
        #
        # As saídas ficam todas na mesma altura dentro da fileira.
        if desta_fileira_geom:
            # Rev.23 — níveis auxiliares definidos localmente para cada
            # fileira. A Rev.22 removeu o antigo bloco de corredores, mas
            # manteve referências a y_corredor_pe/y_corredor_n.
            y_corredor_pe = y_rail - 1.74
            y_corredor_n = y_rail - 1.92
            y_saida_circuito = y_rail - 2.28
            y_identificacao_saida = y_saida_circuito - 0.22

            for d_saida, g_saida in circuitos_geom:
                if abs(
                    g_saida["y1"] - (y_rail - 0.85)
                ) >= 0.05:
                    continue

                fases_saida = _fases_do_texto(
                    d_saida.get("fase", "")
                )
                polos_saida = _centros_polos(g_saida)

                # Fases: entram/saiem pelo borne real, mas a passagem
                # vertical prolongada é deslocada para fora do corpo do DJ.
                # Assim um condutor de outro circuito nunca aparece "por dentro"
                # de um disjuntor apenas porque compartilha o mesmo eixo X.
                xs_fases_saida = []
                for idx_fase_saida, fase_saida in enumerate(fases_saida):
                    x_borne_fase = _polo_para_fase(
                        d_saida,
                        g_saida,
                        fase_saida
                    )
                    xs_fases_saida.append(x_borne_fase)

                    # Rev.27: saída terminal absolutamente simples.
                    # O condutor permanece no mesmo eixo do borne até a
                    # saída inferior do QDC — nenhuma curva intermediária.
                    x_fase_saida = x_borne_fase

                    _line(
                        msp,
                        (x_borne_fase, g_saida["y1"]),
                        (x_borne_fase, y_saida_circuito),
                        _layer_por_token(fase_saida)
                    )

                # PE sempre acompanha o circuito e não passa pelo DJ.
                # Colocado na lateral esquerda do conjunto de condutores.
                x_min_saida = min(
                    xs_fases_saida or [g_saida["cx"]]
                )
                x_max_saida = max(
                    xs_fases_saida or [g_saida["cx"]]
                )

                x_pe_saida = _x_passagem_lateral_disjuntor(
                    g_saida,
                    "esq",
                    0.16
                )

                _line(
                    msp,
                    (x_pe_saida, y_corredor_pe),
                    (x_pe_saida, y_saida_circuito),
                    LPE
                )

                # N apenas nos circuitos monopolares.
                tem_neutro_saida = (
                    len(fases_saida) == 1
                    and int(d_saida.get("modulos", 1) or 1) == 1
                )

                if tem_neutro_saida:
                    # O N já é conduzido pelo bloco do respectivo grupo DR.
                    # Mantemos aqui apenas a referência lateral, fora do DJ.
                    x_n_saida = _x_passagem_lateral_disjuntor(
                        g_saida,
                        "dir",
                        0.12
                    )

                # Identificador único e alinhado abaixo dos condutores.
                ident_saida = str(
                    d_saida.get("identificador", "") or ""
                )

                if len(fases_saida) == 1:
                    composicao_saida = "F  N  PE"
                elif len(fases_saida) == 2:
                    composicao_saida = "F  F  PE"
                elif len(fases_saida) >= 3:
                    composicao_saida = "F  F  F  PE"
                else:
                    composicao_saida = "PE"

                _texto_central(
                    msp,
                    ident_saida,
                    g_saida["x1"],
                    g_saida["x2"],
                    y_identificacao_saida,
                    0.085,
                    LT
                )

                _texto_central(
                    msp,
                    composicao_saida,
                    g_saida["x1"] - 0.10,
                    g_saida["x2"] + 0.10,
                    y_identificacao_saida - 0.14,
                    0.055,
                    LT
                )

        # Barramento dos circuitos segmentado por grupo de proteção.
        if circuitos_geom:
            desta_fileira = [
                (d, g)
                for d, g in circuitos_geom
                if abs(
                    g["y1"]
                    - (y_rail - 0.85)
                )
                < 0.05
            ]

            if desta_fileira:
                yp = (
                    y_rail
                    + 0.90
                )

                grupos_fileira = []
                for d, g in desta_fileira:
                    grupo = str(
                        d.get(
                            "grupo",
                            "SEM DR"
                        )
                        or "SEM DR"
                    )

                    if (
                        not grupos_fileira
                        or grupos_fileira[-1][0]
                        != grupo
                    ):
                        grupos_fileira.append(
                            [
                                grupo,
                                []
                            ]
                        )

                    grupos_fileira[-1][1].append(
                        (
                            d,
                            g
                        )
                    )

                # ====================================================
                # Fase 13.6 Rev.31 — GRADE VERTICAL DINÂMICA DA FILEIRA
                # ====================================================
                # O vão entre a BASE dos dispositivos superiores e o TOPO
                # dos disjuntores desta fileira é dividido em faixas iguais,
                # uma para cada condutor que realmente passa na horizontal.
                #
                # O condutor fica no centro da respectiva faixa:
                #   passo = vão / quantidade_real_de_condutores
                #
                # A ordem vertical é por fase A -> B -> C e, dentro da fase,
                # segue a ordem dos grupos SEM DR -> DR1 -> DR2 -> DR3...
                y_base_fileira_superior = min(
                    g_sup["y1"]
                    for _, g_sup in geral_geom
                ) if geral_geom else (y_rail + 2.30)

                y_topo_fileira_inferior = max(
                    g_inf["y2"]
                    for _, g_inf in desta_fileira
                )

                condutores_horizontais = []
                for grupo_grade, itens_grade in grupos_fileira:
                    fases_grade = []
                    for d_grade, g_grade in itens_grade:
                        for fase_grade in _fases_do_texto(
                            d_grade.get("fase", "")
                        ):
                            if (
                                fase_grade in ("A", "B", "C")
                                and fase_grade not in fases_grade
                            ):
                                fases_grade.append(fase_grade)

                    for fase_grade in ("A", "B", "C"):
                        if fase_grade in fases_grade:
                            condutores_horizontais.append(
                                (grupo_grade, fase_grade)
                            )

                    # Rev.21 — o neutro também ocupa espaço horizontal real
                    # entre os trilhos. Portanto entra na mesma grade e não
                    # pode compartilhar altura com qualquer fase.
                    if any(
                        g_grade.get("tem_neutro")
                        for _, g_grade in itens_grade
                    ):
                        condutores_horizontais.append(
                            (grupo_grade, "N")
                        )

                # Ordena primeiro por fase/função para manter A, B, C e N
                # em níveis independentes e visualmente previsvisíveis.
                # verticais coerentes; a estabilidade da lista preserva a
                # ordem elétrica dos grupos dentro de cada fase.
                ordem_fase_grade = {"A": 0, "B": 1, "C": 2, "N": 3}
                condutores_horizontais = sorted(
                    condutores_horizontais,
                    key=lambda item: ordem_fase_grade.get(item[1], 99)
                )

                qtd_condutores_horizontais = max(
                    1,
                    len(condutores_horizontais)
                )

                vao_vertical_condutores = max(
                    0.10,
                    y_base_fileira_superior
                    - y_topo_fileira_inferior
                )

                passo_vertical_condutores = (
                    vao_vertical_condutores
                    / qtd_condutores_horizontais
                )

                niveis_horizontais = {}
                for indice_condutor, chave_condutor in enumerate(
                    condutores_horizontais
                ):
                    niveis_horizontais[chave_condutor] = (
                        y_base_fileira_superior
                        - (indice_condutor + 0.5)
                        * passo_vertical_condutores
                    )

                # ====================================================
                # Rev.21 — CORREDORES VERTICAIS EXCLUSIVOS
                # ====================================================
                # Cada alimentação que cruza verticalmente o vão entre os
                # trilhos recebe um X exclusivo. O algoritmo evita:
                # - outros corredores verticais;
                # - centros de polos dos dispositivos;
                # - posições de saída N/PE junto aos circuitos.
                x_proibidos_corredor = []

                for _, g_sup in geral_geom:
                    x_proibidos_corredor.extend(
                        _centros_polos(g_sup)
                    )

                for _, g_inf in desta_fileira:
                    x_proibidos_corredor.extend(
                        _centros_polos(g_inf)
                    )
                    x_proibidos_corredor.extend(
                        [
                            g_inf["cx"] - 0.10,
                            g_inf["cx"] + 0.10,
                        ]
                    )

                corredores_verticais_usados = []
                corredor_vertical_por_chave = {}

                def _reservar_corredor_vertical(chave, x_preferido):
                    if chave in corredor_vertical_por_chave:
                        return corredor_vertical_por_chave[chave]

                    limite_esq = x_miolo_inicio + 0.06
                    limite_dir = (
                        x_miolo_inicio
                        + largura_miolo_qdc
                        - 0.06
                    )

                    # procura ao redor do ponto preferido em passos regulares
                    # até achar uma faixa vertical realmente livre.
                    candidatos = [float(x_preferido)]
                    for passo_busca in range(1, 80):
                        delta = passo_busca * 0.07
                        candidatos.append(float(x_preferido) + delta)
                        candidatos.append(float(x_preferido) - delta)

                    escolhido = None
                    for candidato in candidatos:
                        if candidato < limite_esq or candidato > limite_dir:
                            continue

                        ocupado_por_eixo = any(
                            abs(candidato - x_existente) < 0.070
                            for x_existente in (
                                x_proibidos_corredor
                                + corredores_verticais_usados
                            )
                        )

                        # Rev.26: condutor que apenas PASSA pela fileira
                        # não pode cruzar o interior de nenhum disjuntor.
                        ocupado_por_disjuntor = any(
                            float(g_bloq["x1"]) - 0.08
                            <= candidato
                            <= float(g_bloq["x2"]) + 0.08
                            for _, g_bloq in desta_fileira
                        )

                        if (
                            not ocupado_por_eixo
                            and not ocupado_por_disjuntor
                        ):
                            escolhido = candidato
                            break

                    if escolhido is None:
                        # fallback determinístico: distribui no miolo sem
                        # reutilizar o mesmo X.
                        passo_fallback = max(
                            0.07,
                            largura_miolo_qdc
                            / max(
                                2,
                                len(condutores_horizontais) + 1
                            )
                        )
                        escolhido = (
                            limite_esq
                            + (len(corredores_verticais_usados) + 1)
                            * passo_fallback
                        )

                    corredor_vertical_por_chave[chave] = escolhido
                    corredores_verticais_usados.append(escolhido)
                    return escolhido

                dr_disp_geom_por_grupo = {
                    str(
                        d.get(
                            "grupo",
                            ""
                        )
                        or ""
                    ):
                    (
                        d,
                        g
                    )
                    for d, g in geral_geom
                    if d.get(
                        "tipo"
                    )
                    == "IDR"
                }

                dr_geom_por_grupo = {
                    grupo_idr: par_idr[1]
                    for grupo_idr, par_idr
                    in dr_disp_geom_por_grupo.items()
                }

                for grupo, itens_grupo in grupos_fileira:
                    x1p = itens_grupo[0][1]["x1"]
                    x2p = itens_grupo[-1][1]["x2"]

                    # --------------------------------------------------
                    # NEUTRO DO GRUPO
                    # --------------------------------------------------
                    # Somente circuitos monopolares utilizam neutro.
                    # Se houver IDR, o neutro obrigatoriamente entra no
                    # IDR e SAI do IDR antes de alimentar esses circuitos.
                    itens_com_neutro = [
                        (
                            d_item,
                            g_item
                        )
                        for d_item, g_item
                        in itens_grupo
                        if g_item.get(
                            "tem_neutro"
                        )
                    ]

                    if itens_com_neutro:
                        y_n_grupo = niveis_horizontais.get(
                            (grupo, "N"),
                            y_corredor_n
                        )

                        x_n_primeiro = _x_passagem_lateral_disjuntor(
                            itens_com_neutro[0][1],
                            "dir",
                            0.12
                        )

                        x_n_ultimo = _x_passagem_lateral_disjuntor(
                            itens_com_neutro[-1][1],
                            "dir",
                            0.12
                        )

                        # Segmento de neutro exclusivo deste grupo.
                        _line(
                            msp,
                            (
                                min(
                                    x_n_primeiro,
                                    x_n_ultimo
                                ),
                                y_n_grupo
                            ),
                            (
                                max(
                                    x_n_primeiro,
                                    x_n_ultimo
                                ),
                                y_n_grupo
                            ),
                            LN
                        )

                        # Derivações N para os circuitos do grupo.
                        # A passagem fica fora do corpo do disjuntor e cada
                        # ponto onde a horizontal continua recebe bolinha azul.
                        xs_neutro_grupo = [
                            _x_passagem_lateral_disjuntor(
                                g_n,
                                "dir",
                                0.12
                            )
                            for d_n, g_n in itens_com_neutro
                        ]

                        if xs_neutro_grupo:
                            x_terminal_neutro = max(xs_neutro_grupo)

                        for d_n, g_n in itens_com_neutro:
                            x_n_saida = _x_passagem_lateral_disjuntor(
                                g_n,
                                "dir",
                                0.12
                            )

                            _line(
                                msp,
                                (
                                    x_n_saida,
                                    y_n_grupo
                                ),
                                (
                                    x_n_saida,
                                    y_saida_circuito
                                ),
                                LN
                            )

                            # Nó azul somente em derivação real.
                            # O último ponto é apenas a curva final.
                            if (
                                xs_neutro_grupo
                                and abs(
                                    x_n_saida
                                    - x_terminal_neutro
                                ) > 1e-9
                            ):
                                _no_fase_preenchido(
                                    msp,
                                    x_n_saida,
                                    y_n_grupo,
                                    "N"
                                )

                        par_idr = dr_disp_geom_por_grupo.get(
                            grupo
                        )

                        if par_idr is not None:
                            disp_idr, geom_idr = par_idr

                            mapa_polos_idr = _mapa_condutores_polos(
                                disp_idr,
                                geom_idr
                            )

                            x_n_idr = mapa_polos_idr.get(
                                "N"
                            )

                            # Se o grupo usa neutro, o IDR precisa possuir
                            # polo N disponível. O motor da Rev.13 já garante
                            # IDR 2P/4P conforme os condutores do grupo.
                            if x_n_idr is not None:
                                # Rev.22 — N do IDR também sai reto.
                                # Nenhum deslocamento lateral logo abaixo do DR.
                                _polyline(
                                    msp,
                                    [
                                        (
                                            x_n_idr,
                                            geom_idr["y1"]
                                        ),
                                        (
                                            x_n_idr,
                                            y_n_grupo
                                        ),
                                        (
                                            x_n_primeiro,
                                            y_n_grupo
                                        ),
                                    ],
                                    LN
                                )
                        else:
                            # Grupo SEM DR: neutro vem diretamente do
                            # barramento principal N.
                            _polyline(
                                msp,
                                [
                                    (
                                        neutro["x"],
                                        neutro["y_bottom"]
                                    ),
                                    (
                                        neutro["x"],
                                        y_n_grupo
                                    ),
                                    (
                                        x_n_primeiro,
                                        y_n_grupo
                                    ),
                                ],
                                LN
                            )

                    # Fase 13.6 Rev.31:
                    # barramento pente somente faz sentido quando alimenta
                    # dois ou mais disjuntores do mesmo grupo.
                    usar_pente = (
                        len(
                            itens_grupo
                        )
                        >= 2
                    )

                    # Rev.21 — representação gráfica dos pentes
                    # temporariamente removida para limpar o miolo do QDC.
                    # A variável usar_pente continua indicando somente que
                    # o grupo possui distribuição para múltiplos disjuntores.

                    # Fases realmente usadas neste grupo.
                    fases_grupo = []
                    for d_item, g_item in itens_grupo:
                        for fase_item in _fases_do_texto(
                            d_item.get(
                                "fase",
                                ""
                            )
                        ):
                            if fase_item not in fases_grupo:
                                fases_grupo.append(
                                    fase_item
                                )

                    fases_grupo = [
                        fase
                        for fase in (
                            "A",
                            "B",
                            "C"
                        )
                        if fase in fases_grupo
                    ]

                    # Cada fase ganha uma pista própria, paralela ao pente.
                    # REV.2: o pente mecânico e as pistas A/B/C possuem
                    # afastamento vertical próprio. Isto evita sobreposição
                    # gráfica entre PENTE, fases e textos dos circuitos.
                    # A pista termina exatamente no último disjuntor que usa
                    # aquela fase; o último ponto será apenas uma curva.
                    # Separação gráfica mínima entre todos os elementos:
                    # PENTE -> A -> B -> C.
                    # Evita coincidência de linha, texto e nós de derivação.
                    # Rev.20: cada condutor horizontal recebe um nível
                    # exclusivo calculado a partir do vão físico disponível.
                    # Mantemos estas constantes apenas como fallback para
                    # situações degeneradas sem geometria suficiente.
                    AFASTAMENTO_PENTE_FASE = 0.30
                    AFASTAMENTO_ENTRE_FASES = ESPACAMENTO_BARRAMENTOS_FASE
                    y_fase_grupo = {}
                    pontos_pente_por_fase = {}

                    for fase_grupo in fases_grupo:
                        yy_fase = niveis_horizontais.get(
                            (grupo, fase_grupo),
                            yp + AFASTAMENTO_PENTE_FASE
                        )
                        y_fase_grupo[
                            fase_grupo
                        ] = yy_fase

                        pontos_fase = []

                        for d_item, g_item in itens_grupo:
                            if fase_grupo in _fases_do_texto(
                                d_item.get(
                                    "fase",
                                    ""
                                )
                            ):
                                x_ponto_fase = _polo_para_fase(
                                    d_item,
                                    g_item,
                                    fase_grupo
                                )

                                # Rev.31 — ajuste EXATAMENTE no final pedido:
                                # DR3 / fase A / C01.
                                # A pista horizontal termina 0,105 à esquerda
                                # do borne do C01, portanto a curva para vertical
                                # não coincide com a entrada do disjuntor.
                                if (
                                    str(grupo).strip().upper() == "DR3"
                                    and str(fase_grupo).strip().upper() == "A"
                                    and str(
                                        d_item.get("identificador", "")
                                        or ""
                                    ).strip().upper() == "C01"
                                ):
                                    x_ponto_fase -= 0.105

                                pontos_fase.append(x_ponto_fase)

                        pontos_fase = sorted(set(pontos_fase))
                        pontos_pente_por_fase[
                            fase_grupo
                        ] = pontos_fase

                        if (
                            pontos_fase
                            and usar_pente
                        ):
                            # Rev.20: a pista existe SOMENTE entre os
                            # polos extremos efetivamente atendidos.
                            # Não há prolongamento antes/depois da curva.
                            x_inicio_pista = min(pontos_fase)
                            x_fim_pista = max(pontos_fase)

                            _line(
                                msp,
                                (
                                    x_inicio_pista,
                                    yy_fase
                                ),
                                (
                                    x_fim_pista,
                                    yy_fase
                                ),
                                _layer_por_token(
                                    fase_grupo
                                )
                            )

                    # Cada disjuntor recebe cada fase em um polo diferente.
                    # Em grupo unitário, a conexão será feita diretamente
                    # da fonte ao polo; portanto não criamos descida a partir
                    # de uma pista horizontal inexistente.
                    if usar_pente:
                        for d_item, g_item in itens_grupo:
                            polos_circuito = _centros_polos(
                                g_item
                            )
                            fases_circuito = _fases_do_texto(
                                d_item.get(
                                    "fase",
                                    ""
                                )
                            )

                            for fase_item in fases_circuito:
                                yy_fase = y_fase_grupo.get(
                                    fase_item,
                                    yp + AFASTAMENTO_PENTE_FASE
                                )

                                x_polo = _polo_para_fase(
                                    d_item,
                                    g_item,
                                    fase_item
                                )

                                eh_final_dr3_a_c01 = (
                                    str(grupo).strip().upper() == "DR3"
                                    and str(fase_item).strip().upper() == "A"
                                    and str(
                                        d_item.get("identificador", "")
                                        or ""
                                    ).strip().upper() == "C01"
                                )

                                if eh_final_dr3_a_c01:
                                    x_descida = x_polo - 0.105
                                    y_aproximacao_borne = g_item["y2"] + 0.08

                                    # A curva horizontal -> vertical ocorre no
                                    # eixo deslocado. Só perto do C01 voltamos
                                    # ao eixo real do borne, sem sobreposição.
                                    _polyline(
                                        msp,
                                        [
                                            (x_descida, yy_fase),
                                            (x_descida, y_aproximacao_borne),
                                            (x_polo, y_aproximacao_borne),
                                            (x_polo, g_item["y2"]),
                                        ],
                                        _layer_por_token(fase_item)
                                    )
                                else:
                                    _line(
                                        msp,
                                        (
                                            x_polo,
                                            yy_fase
                                        ),
                                        (
                                            x_polo,
                                            g_item["y2"]
                                        ),
                                        _layer_por_token(
                                            fase_item
                                        )
                                    )
                                # O nó é decidido somente depois de
                                # conhecermos de qual lado chega a fonte.
                                # Isso evita bolinhas no ponto terminal.

                    # Fonte do grupo.
                    fonte_disp = None
                    # Fonte do grupo.
                    fonte_disp = None
                    fonte_geom = dr_geom_por_grupo.get(
                        grupo
                    )

                    if fonte_geom is not None:
                        for d_geral, g_geral in geral_geom:
                            if g_geral is fonte_geom:
                                fonte_disp = d_geral
                                break

                    if (
                        fonte_geom is None
                        and str(
                            grupo
                        ).upper()
                        == "SEM DR"
                        and dg_geoms
                    ):
                        fonte_disp, fonte_geom = dg_geoms[0]

                    if fonte_geom and fonte_disp:
                        polos_fonte = _centros_polos(
                            fonte_geom
                        )

                        if fonte_disp.get("tipo") == "IDR":
                            fases_fonte = [
                                token
                                for token in ("A", "B", "C")
                                if token in (
                                    fonte_disp.get(
                                        "condutores",
                                        []
                                    )
                                    or []
                                )
                            ]
                        else:
                            fases_fonte = _fases_do_texto(
                                fonte_disp.get(
                                    "fase",
                                    ""
                                )
                            )

                        if fonte_disp.get("tipo") == "DG":
                            fases_fonte = _fases_alimentador(
                                mapa
                            )

                        if usar_pente:
                            # Dois ou mais disjuntores:
                            # fonte -> pista específica A/B/C -> derivações.
                            for idx_fase, fase_item in enumerate(
                                fases_fonte
                            ):
                                if fase_item not in y_fase_grupo:
                                    continue

                                x_origem = _polo_para_fase(
                                    fonte_disp,
                                    fonte_geom,
                                    fase_item
                                )
                                yy_destino = y_fase_grupo[
                                    fase_item
                                ]

                                pontos_destino_fase = sorted(
                                    set(
                                        pontos_pente_por_fase.get(
                                            fase_item,
                                            []
                                        )
                                    )
                                )

                                if not pontos_destino_fase:
                                    continue

                                # Rev.20: a alimentação entra pelo extremo
                                # da pista mais próximo da fonte. A pista não
                                # ultrapassa nenhum dos polos extremos.
                                x_min_fase = min(pontos_destino_fase)
                                x_max_fase = max(pontos_destino_fase)

                                if abs(x_origem - x_min_fase) <= abs(
                                    x_origem - x_max_fase
                                ):
                                    x_destino_fase = x_min_fase
                                    x_terminal_final = x_max_fase
                                else:
                                    x_destino_fase = x_max_fase
                                    x_terminal_final = x_min_fase

                                # Rev.31 — saída do DR3 preservada.
                                # O ajuste de 0,105 não acontece mais aqui.
                                # Ele é aplicado somente no ponto final da fase A
                                # que desce para o C01.
                                _polyline(
                                    msp,
                                    [
                                        (x_origem, fonte_geom["y1"]),
                                        (x_origem, yy_destino),
                                        (x_destino_fase, yy_destino),
                                    ],
                                    _layer_por_token(fase_item)
                                )

                                # Nós somente onde a pista realmente
                                # deriva para um disjuntor e continua adiante.
                                # O extremo oposto à entrada é a última curva:
                                # horizontal -> vertical, portanto sem nó.
                                for x_no in pontos_destino_fase:
                                    if abs(
                                        x_no - x_terminal_final
                                    ) <= 1e-9:
                                        continue

                                    _no_fase_preenchido(
                                        msp,
                                        x_no,
                                        yy_destino,
                                        fase_item
                                    )

                        else:
                            # Um único disjuntor:
                            # SEM PENTE e SEM pista horizontal.
                            # Cada fase sai do polo correspondente da fonte e
                            # chega diretamente ao polo correspondente do DJ.
                            d_unico, g_unico = itens_grupo[0]
                            fases_destino = _fases_do_texto(
                                d_unico.get(
                                    "fase",
                                    ""
                                )
                            )

                            for idx_fase, fase_item in enumerate(
                                fases_destino
                            ):
                                if fase_item not in fases_fonte:
                                    continue

                                x_origem = _polo_para_fase(
                                    fonte_disp,
                                    fonte_geom,
                                    fase_item
                                )
                                x_destino = _polo_para_fase(
                                    d_unico,
                                    g_unico,
                                    fase_item
                                )

                                # Rev.20: mesmo para grupo com um único
                                # disjuntor, a horizontal ocupa sua faixa
                                # exclusiva na grade dinâmica.
                                y_corredor_direto = niveis_horizontais.get(
                                    (grupo, fase_item),
                                    yp
                                    + AFASTAMENTO_PENTE_FASE
                                    + idx_fase
                                    * AFASTAMENTO_ENTRE_FASES
                                )

                                # Rev.27 — grupo unitário:
                                # saída vertical do borne, uma horizontal e
                                # entrada vertical no disjuntor de destino.
                                _polyline(
                                    msp,
                                    [
                                        (x_origem, fonte_geom["y1"]),
                                        (x_origem, y_corredor_direto),
                                        (x_destino, y_corredor_direto),
                                        (x_destino, g_unico["y2"]),
                                    ],
                                    _layer_por_token(fase_item)
                                )

        y_rail -= 3.15

    # -------------------------
    # Painel lateral
    # -------------------------
    # A tabela deve nascer numa coluna independente da área DIN.
    # Não usar qx2 como referência: qx2 representa o limite gráfico
    # do diagrama e, em quadros largos, fazia a tabela sobrepor o QDC.
    px1 = (
        x0
        + margem_x
        + area_din_w
        + separacao_painel
    )
    px2 = x0 + largura - 0.45
    py_top = qy_top

    _rect(
        msp,
        px1,
        ybase + 0.75,
        px2,
        py_top,
        L
    )

    _text(
        msp,
        "LISTA DE CIRCUITOS",
        px1 + 0.25,
        py_top - 0.38,
        0.16,
        LT
    )

    # Tabela executiva:
    # Circuito | Fase | Disj. | Ambientes
    #
    # Fase 13.6 Rev.31:
    # cada célula é desenhada como um retângulo independente.
    # Evita linhas horizontais longas escapando para dentro do diagrama.
    tabela_x1 = px1 + 0.35
    tabela_largura = min(
        9.20,
        max(
            7.80,
            px2 - tabela_x1 - 0.35
        )
    )
    tabela_x2 = tabela_x1 + tabela_largura
    tabela_y_top = py_top - 0.72

    col_circuito = 1.05
    col_fase = 0.85
    col_dj = 1.10
    col_ambientes = (
        tabela_largura
        - col_circuito
        - col_fase
        - col_dj
    )

    x_c1 = tabela_x1
    x_c2 = x_c1 + col_circuito
    x_c3 = x_c2 + col_fase
    x_c4 = x_c3 + col_dj
    x_c5 = tabela_x2

    altura_cab = 0.42
    altura_linha_base = 0.38

    linhas_tabela = []

    for d in circuitos:
        ident = str(
            d.get(
                "identificador",
                ""
            )
            or ""
        )

        # Fonte de verdade das fases: resultado de balancear_circuitos().
        fase_c = str(
            d.get(
                "fase",
                ""
            )
            or ""
        ).strip()

        dj_c = int(
            d.get(
                "corrente_a",
                0
            )
            or 0
        )

        ambientes_txt = str(
            d.get(
                "ambiente",
                ""
            )
            or ""
        ).strip()

        # Usa largura visual da coluna Ambientes para definir a quebra.
        max_chars_amb = max(
            22,
            int(
                col_ambientes
                / 0.066
                / 0.58
            )
        )

        linhas_ambientes = _quebrar_texto(
            ambientes_txt or "-",
            max_chars_amb
        )

        if not linhas_ambientes:
            linhas_ambientes = ["-"]

        altura_linha = max(
            altura_linha_base,
            0.18
            + len(
                linhas_ambientes
            )
            * 0.17
        )

        linhas_tabela.append({
            "identificador": ident,
            "fase": fase_c or "-",
            "disjuntor": f"{dj_c} A",
            "ambientes": linhas_ambientes,
            "altura": altura_linha,
        })

    # Cabeçalho: quatro células independentes.
    y_top = tabela_y_top
    y_bottom = y_top - altura_cab

    cabecalhos = [
        (x_c1, x_c2, "Circuito"),
        (x_c2, x_c3, "Fase"),
        (x_c3, x_c4, "Disj."),
        (x_c4, x_c5, "Ambientes"),
    ]

    for xa, xb, titulo_coluna in cabecalhos:
        _rect(
            msp,
            xa,
            y_bottom,
            xb,
            y_top,
            L
        )
        _text(
            msp,
            titulo_coluna,
            xa + 0.08,
            y_top - 0.27,
            0.075,
            LT
        )

    yy_top = y_bottom

    # Linhas: cada uma composta de quatro retângulos.
    for item in linhas_tabela:
        altura_linha = item["altura"]
        yy_bottom = yy_top - altura_linha

        celulas = [
            (
                x_c1,
                x_c2,
                [item["identificador"]],
                0.072
            ),
            (
                x_c2,
                x_c3,
                [item["fase"]],
                0.072
            ),
            (
                x_c3,
                x_c4,
                [item["disjuntor"]],
                0.072
            ),
            (
                x_c4,
                x_c5,
                item["ambientes"],
                0.066
            ),
        ]

        for xa, xb, textos, altura_texto in celulas:
            _rect(
                msp,
                xa,
                yy_bottom,
                xb,
                yy_top,
                L
            )

            y_txt = yy_top - 0.24

            for texto_celula in textos:
                _text(
                    msp,
                    texto_celula,
                    xa + 0.08,
                    y_txt,
                    altura_texto,
                    LT
                )
                y_txt -= 0.17

        yy_top = yy_bottom

    tabela_y_bottom = yy_top

    # Legenda.
    leg_y = max(
        ybase + 2.30,
        tabela_y_bottom - 0.38
    )
    _text(
        msp,
        "LEGENDA",
        px1 + 0.25,
        leg_y,
        0.15,
        LT
    )

    legendas = []

    fases_reais = _fases_alimentador(
        mapa
    )

    if "A" in fases_reais:
        legendas.append(
            (
                "Fase A",
                LA
            )
        )

    if "B" in fases_reais:
        legendas.append(
            (
                "Fase B",
                LB
            )
        )

    if "C" in fases_reais:
        legendas.append(
            (
                "Fase C",
                LC
            )
        )

    if _tem_neutro_alimentador(
        mapa
    ):
        legendas.append(
            (
                "Neutro (N)",
                LN
            )
        )

    if _tem_pe_alimentador(
        mapa
    ):
        legendas.append(
            (
                "Protecao / Terra (PE)",
                LPE
            )
        )

    yleg = leg_y - 0.35
    for texto, layer in legendas:
        _line(
            msp,
            (px1 + 0.25, yleg + 0.04),
            (px1 + 0.95, yleg + 0.04),
            layer
        )
        _text(
            msp,
            texto,
            px1 + 1.10,
            yleg,
            0.08,
            LT
        )
        yleg -= 0.27

    # Dados do quadro no rodapé lateral.
    dados_y = ybase + 1.60
    _text(
        msp,
        "DADOS DO QUADRO",
        px1 + 0.25,
        dados_y + 0.85,
        0.15,
        LT
    )
    qtd_idr = sum(1 for d in gerais if d.get("tipo") == "IDR")
    qtd_dps_desenho = sum(1 for d in gerais if d.get("tipo") == "DPS")

    dados = [
        f"Posicoes: {int(mapa.get('qdc_posicoes', 0) or 0)}",
        f"Modulos ocupados: {int(mapa.get('modulos_dispositivos', 0) or 0)}",
        f"Posicoes livres: {int(mapa.get('posicoes_livres', 0) or 0)}",
        f"Fileiras DIN: {int(mapa.get('linhas', 0) or 0)}",
        f"IDRs: {qtd_idr}",
        f"DPS: {qtd_dps_desenho}",
    ]
    yy_d = dados_y + 0.50
    for linha in dados:
        _text(
            msp,
            linha,
            px1 + 0.25,
            yy_d,
            0.083,
            LT
        )
        yy_d -= 0.22

    return {
        "origem": (x0, ybase),
        "largura": largura,
        "altura": altura,
        "qdc_posicoes": mapa.get("qdc_posicoes"),
        "linhas": linhas,
        "colunas": colunas,
        "tipo_desenho": "vista_frontal_executiva",
    }

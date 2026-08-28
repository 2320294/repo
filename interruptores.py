
import os
import tempfile
import ezdxf
import streamlit as st

from dxf_io import ler_elementos
from soleiras_geometria import distancia_ponto_segmento

TOLERANCIA_SOLEIRA_AMBIENTE = 0.03


def _nome_ambiente_da_poligonal(poly, textos):
    xs=[p[0] for p in poly]
    ys=[p[1] for p in poly]
    return next(
        (
            t["nome"] for t in textos
            if min(xs)-0.5 <= t["x"] <= max(xs)+0.5
            and min(ys)-0.5 <= t["y"] <= max(ys)+0.5
        ),
        None
    )


def _segmentos(poly):
    return [(poly[i], poly[(i+1)%len(poly)]) for i in range(len(poly))] if len(poly)>=2 else []


def _vertices_soleira(s):
    out=[]
    for p in (s.get("vertices") or []):
        q=(float(p[0]),float(p[1]))
        if q not in out: out.append(q)
    return out


def _soleira_toca_ambiente(s, poly):
    verts=_vertices_soleira(s)
    segs=_segmentos(poly)
    if not verts or not segs:
        return False
    return min(
        distancia_ponto_segmento(v,a,b)
        for v in verts
        for a,b in segs
    ) <= TOLERANCIA_SOLEIRA_AMBIENTE


def contar_portas_por_ambiente(dxf_bytes):
    if not dxf_bytes:
        return {}

    caminho=None
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=".dxf") as tmp:
            tmp.write(dxf_bytes)
            caminho=tmp.name

        doc=ezdxf.readfile(caminho)
        elementos=ler_elementos(doc.modelspace())
        polilinhas=elementos["polilinhas"]
        textos=elementos["textos"]
        soleiras=elementos["soleiras_raw"]

        ambientes=[]
        usados={}
        for poly in polilinhas:
            nome=_nome_ambiente_da_poligonal(poly,textos)
            if not nome:
                continue
            if nome in usados:
                usados[nome]+=1
                nome_final=f"{nome} {usados[nome]}"
            else:
                usados[nome]=1
                nome_final=nome
            ambientes.append((nome_final,poly))

        contagem={nome:0 for nome,_ in ambientes}
        for s in soleiras:
            for nome,poly in ambientes:
                if _soleira_toca_ambiente(s,poly):
                    contagem[nome]+=1

        return contagem
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)


def renderizar_interruptores(dados_ambientes, config_salva, dxf_bytes=None):
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores")

    contagem=contar_portas_por_ambiente(dxf_bytes)
    nomes=sorted([r["Ambiente"] for r in dados_ambientes], key=str.casefold)

    config={}
    multiplos=[]

    for amb in nomes:
        qtd_portas=contagem.get(amb,0)

        if qtd_portas <= 0:
            config[amb]={
                "quantidade":0,
                "portas_detectadas":0,
                "automatico":True
            }
        elif qtd_portas == 1:
            # Uma única porta: 1 interruptor automático.
            config[amb]={
                "quantidade":1,
                "portas_detectadas":1,
                "automatico":True
            }
        else:
            multiplos.append(amb)

    if not multiplos:
        st.info(
            "Nenhum ambiente possui duas ou mais portas. "
            "Ambientes com uma única porta recebem 1 interruptor automaticamente."
        )
        return config

    st.markdown(
        "Somente ambientes com **duas ou mais portas** aparecem abaixo. "
        "Escolha quantos interruptores deseja em cada ambiente."
    )

    c1,c2=st.columns(2,gap="large")

    for i,amb in enumerate(multiplos):
        qtd_portas=contagem[amb]
        coluna=c1 if i%2==0 else c2

        salvo=1
        if isinstance(config_salva,dict):
            cfg_antigo=config_salva.get(amb,{})
            if isinstance(cfg_antigo,dict):
                salvo=int(cfg_antigo.get("quantidade",1))
        salvo=max(1,min(qtd_portas,salvo))

        opcoes=list(range(1,qtd_portas+1))

        with coluna:
            with st.expander(f"🔘 {amb} — {qtd_portas} portas", expanded=True):
                qtd=st.selectbox(
                    "Quantidade de interruptores:",
                    opcoes,
                    index=opcoes.index(salvo),
                    key=f"int_qtd_{amb}"
                )

                config[amb]={
                    "quantidade":qtd,
                    "portas_detectadas":qtd_portas,
                    "automatico":False
                }

                if qtd == 1:
                    st.caption("Somente uma porta receberá interruptor.")
                else:
                    st.caption(
                        f"{qtd} portas distintas receberão interruptor, "
                        "um em cada porta."
                    )

    return config

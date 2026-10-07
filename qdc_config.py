
SEPARADOR_QDC = "||PAREDE:"


def codificar_qdc(
    ambiente,
    parede_numero=None,
    trecho_numero=None,
    t0=None,
    t1=None
):
    ambiente = str(
        ambiente or ""
    ).strip()

    if not ambiente:
        return ""

    if parede_numero is None:
        return ambiente

    texto = (
        f"{ambiente}"
        f"{SEPARADOR_QDC}"
        f"{int(parede_numero)}"
    )

    if trecho_numero is not None:
        texto += (
            f"||TRECHO:"
            f"{int(trecho_numero)}"
        )

    if (
        t0 is not None
        and t1 is not None
    ):
        texto += (
            f"||T0:{float(t0):.8f}"
            f"||T1:{float(t1):.8f}"
        )

    return texto


def decodificar_qdc_completo(
    valor
):
    texto = str(
        valor or ""
    ).strip()

    if SEPARADOR_QDC not in texto:
        return {
            "ambiente":
                texto,
            "parede_numero":
                None,
            "trecho_numero":
                None,
            "t0":
                None,
            "t1":
                None
        }

    partes = texto.split(
        "||"
    )

    dados = {
        "ambiente":
            partes[0].strip(),
        "parede_numero":
            None,
        "trecho_numero":
            None,
        "t0":
            None,
        "t1":
            None
    }

    for parte in partes[1:]:
        if ":" not in parte:
            continue

        chave, valor_item = parte.split(
            ":",
            1
        )

        chave = chave.strip().upper()
        valor_item = valor_item.strip()

        try:
            if chave == "PAREDE":
                dados[
                    "parede_numero"
                ] = int(
                    valor_item
                )

            elif chave == "TRECHO":
                dados[
                    "trecho_numero"
                ] = int(
                    valor_item
                )

            elif chave == "T0":
                dados[
                    "t0"
                ] = float(
                    valor_item
                )

            elif chave == "T1":
                dados[
                    "t1"
                ] = float(
                    valor_item
                )

        except Exception:
            continue

    return dados


def decodificar_qdc(
    valor
):
    dados = decodificar_qdc_completo(
        valor
    )

    return (
        dados["ambiente"],
        dados["parede_numero"]
    )


def ambiente_qdc(
    valor
):
    return decodificar_qdc_completo(
        valor
    )["ambiente"]


def descricao_qdc(
    valor
):
    dados = decodificar_qdc_completo(
        valor
    )

    ambiente = dados[
        "ambiente"
    ]

    parede = dados[
        "parede_numero"
    ]

    trecho = dados[
        "trecho_numero"
    ]

    if parede is None:
        return ambiente

    if trecho is None:
        return (
            f"{ambiente} — "
            f"Parede {parede}"
        )

    letra = chr(
        ord("A")
        + max(
            0,
            trecho - 1
        )
    )

    return (
        f"{ambiente} — "
        f"Parede {parede}{letra}"
    )


SEPARADOR_QDC = "||PAREDE:"


def codificar_qdc(
    ambiente,
    parede_numero=None
):
    ambiente = str(
        ambiente or ""
    ).strip()

    if not ambiente:
        return ""

    if parede_numero is None:
        return ambiente

    return (
        f"{ambiente}"
        f"{SEPARADOR_QDC}"
        f"{int(parede_numero)}"
    )


def decodificar_qdc(
    valor
):
    texto = str(
        valor or ""
    ).strip()

    if SEPARADOR_QDC not in texto:
        return (
            texto,
            None
        )

    ambiente, parede = texto.split(
        SEPARADOR_QDC,
        1
    )

    try:
        parede_numero = int(
            parede.strip()
        )
    except Exception:
        parede_numero = None

    return (
        ambiente.strip(),
        parede_numero
    )


def ambiente_qdc(
    valor
):
    return decodificar_qdc(
        valor
    )[0]


def descricao_qdc(
    valor
):
    ambiente, parede = (
        decodificar_qdc(
            valor
        )
    )

    if parede is None:
        return ambiente

    return (
        f"{ambiente} — "
        f"Parede {parede}"
    )

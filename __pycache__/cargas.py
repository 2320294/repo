import math


def dimensionar_cargas(nome, area, perimetro):
    if area <= 0 or perimetro <= 0:
        return {
            "Qtd Ilum.": 0,
            "Pot. Unit. Ilum (VA)": 0,
            "Carga Ilum. (VA)": 0,
            "TUGs (Qtd)": 0,
            "Pot. Unit. TUG (VA)": 0,
            "Carga TUGs (VA)": 0,
            "Equipamento TUE": "-",
            "Qtd TUE": 0,
            "Pot. Unit. TUE (VA)": 0,
            "Carga TUE (VA)": 0
        }

    qtd_ilum = 1 if area <= 10 else math.ceil(area / 10)
    carga_ilum = 100 if area <= 6 else 100 + (((area - 6) // 4) * 60)

    nome_lower = nome.lower().strip()
    nome_words = nome_lower.replace("-", " ").split()

    is_umida = (
        any(
            x in nome_lower
            for x in [
                "coz", "serv", "banh", "lav",
                "sanit", "área", "area"
            ]
        )
        or any(
            w in nome_words
            for w in ["as", "wc", "bwc"]
        )
    )

    is_corredor = any(
        x in nome_lower
        for x in [
            "hall", "corredor",
            "circulação", "circulacao"
        ]
    )

    if is_umida:
        qtd_tugs = math.ceil(perimetro / 3.5)
        carga_tugs = (
            qtd_tugs * 600
            if qtd_tugs <= 3
            else (3 * 600) + ((qtd_tugs - 3) * 100)
        )

    elif is_corredor:
        comprimento_estimado = (perimetro / 2) - 1

        if comprimento_estimado <= 3:
            qtd_tugs = 1
        else:
            qtd_tugs = max(
                1,
                math.ceil(comprimento_estimado / 3)
            )

        carga_tugs = qtd_tugs * 100

    else:
        qtd_tugs = math.ceil(perimetro / 5)
        carga_tugs = qtd_tugs * 100

    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0

    if (
        any(
            x in nome_lower
            for x in ["banh", "sanit"]
        )
        or any(
            w in nome_words
            for w in ["wc", "bwc"]
        )
    ):
        tue_nome = "Chuveiro Elétrico"
        qtd_tue = 1
        carga_tue = 5500

    elif "coz" in nome_lower:
        tue_nome = "Micro-ondas/Forno"
        qtd_tue = 1
        carga_tue = 2000

    elif any(
        x in nome_lower
        for x in ["quarto", "dorm", "suite"]
    ):
        tue_nome = "Ar-Condicionado"
        qtd_tue = 1
        carga_tue = 1200

    elif (
        any(
            x in nome_lower
            for x in ["serv", "lavand"]
        )
        or "as" in nome_words
    ):
        tue_nome = "Máquina de Lavar"
        qtd_tue = 1
        carga_tue = 1000

    return {
        "Qtd Ilum.": qtd_ilum,
        "Pot. Unit. Ilum (VA)":
            round(carga_ilum / qtd_ilum)
            if qtd_ilum > 0
            else 0,
        "Carga Ilum. (VA)": carga_ilum,

        "TUGs (Qtd)": qtd_tugs,
        "Pot. Unit. TUG (VA)":
            600 if is_umida else 100,
        "Carga TUGs (VA)": carga_tugs,

        "Equipamento TUE": tue_nome,
        "Qtd TUE": qtd_tue,
        "Pot. Unit. TUE (VA)":
            round(
                carga_tue / max(1, qtd_tue)
            ),
        "Carga TUE (VA)": carga_tue
    }

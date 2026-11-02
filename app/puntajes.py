"""Cálculo de puntajes e índices según la clave del Paso 1 (versión v03).

- Q1: términos de seguridad marcados (S1 a S15) / 15. Los términos generales (G) son control.
- Q2: opción correcta = 1; otra = 0.
- K1 a K10: acierto = 1; error o "No sé" = 0. Los "No sé" se cuentan aparte.
- Likert (A) y frecuencia (B): 1 a 5, se llevan a 0–1 con (valor − 1) / 4. Invertidos: 6 − valor.
- A6 y B4 son descriptivos: no suman.
- IC = promedio de Q1, Q2 y K1..K10 (12 puntajes de 0 a 1) × 100.
- IA = promedio de A1..A9 sin A6 × 100. IB = promedio de B1..B10 sin B4 × 100.
- ICC = 0,3·IC + 0,2·IA + 0,5·IB (Kruger y Kearney, 2006). Bueno ≥ 80, medio 60–79, bajo < 60.
- Subescalas Reconocer, Enfrentar y Mitigar: promedio de sus ítems (0 a 1) × 100.
"""

RECONOCER = ["Q2", "K1", "K9", "K10", "A5"]
ENFRENTAR = ["B1", "B5", "B9"]
MITIGAR = ["K6", "K7", "B2", "B3", "B7", "B8"]
TERMINOS_SEGURIDAD = {f"S{i}" for i in range(1, 16)}


def _promedio(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def _escala(valor, invertido):
    v = int(valor)
    if invertido:
        v = 6 - v
    return (v - 1) / 4


def nivel(icc):
    if icc is None:
        return ""
    if icc >= 80:
        return "bueno"
    if icc >= 60:
        return "medio"
    return "bajo"


def puntajes_de(respuestas_por_item, items):
    """respuestas_por_item: {codigo_item: [codigos de opción]}. items: {codigo: Item}."""
    p = {}  # puntaje 0–1 de cada ítem que suma
    q1 = set(respuestas_por_item.get("Q1", []))
    q1_seguridad = len(q1 & TERMINOS_SEGURIDAD)
    p["Q1"] = q1_seguridad / 15
    k_no_se = 0
    for codigo, item in items.items():
        elegidas = respuestas_por_item.get(codigo, [])
        if codigo == "Q1" or not item.suma_al_indice or not elegidas:
            continue
        valor = elegidas[0]
        if item.respuesta_correcta is not None:
            p[codigo] = 1.0 if valor == item.respuesta_correcta else 0.0
            if valor == "NS":
                k_no_se += 1
        elif item.tipo_respuesta in ("likert", "frecuencia"):
            p[codigo] = _escala(valor, item.invertido)

    def indice(codigos):
        prom = _promedio([p.get(c) for c in codigos])
        return None if prom is None else round(prom * 100, 1)

    ic = indice(["Q1", "Q2"] + [f"K{i}" for i in range(1, 11)])
    ia = indice([f"A{i}" for i in range(1, 10) if f"A{i}" in items and items[f"A{i}"].suma_al_indice])
    ib = indice([f"B{i}" for i in range(1, 11) if f"B{i}" in items and items[f"B{i}"].suma_al_indice])
    icc = None if None in (ic, ia, ib) else round(0.3 * ic + 0.2 * ia + 0.5 * ib, 1)
    return {
        "Q1_terminos_seguridad": q1_seguridad,
        "Q1_puntaje": round(p["Q1"], 3),
        "Q2_puntaje": int(p.get("Q2", 0)),
        "K_aciertos": int(sum(p.get(f"K{i}", 0) for i in range(1, 11))),
        "K_no_se": k_no_se,
        "IC": ic,
        "IA": ia,
        "IB": ib,
        "ICC": icc,
        "nivel_ICC": nivel(icc),
        "Reconocer": indice(RECONOCER),
        "Enfrentar": indice(ENFRENTAR),
        "Mitigar": indice(MITIGAR),
    }

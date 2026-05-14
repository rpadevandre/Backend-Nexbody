"""Sugerencias de comidas alineadas al país (ISO 3166-1 alpha-2)."""
from __future__ import annotations

from typing import TypedDict


class _RegionPack(TypedDict, total=False):
    breakfast: str
    merienda: str
    plates: dict[str, str]


def _default_plates() -> dict[str, str]:
    return {
        "omnivoro": (
            "Proteína animal magra + vegetales variados + carb moderado (arroz, papa, pasta integral)."
        ),
        "vegetariano": (
            "Huevo o lácteos o legumbres en cada plato principal + cereales integrales + ensalada."
        ),
        "vegano": (
            "Legumbres + tofu/tempeh + cereales + frutos secos moderados + B12 suplementada si hace falta."
        ),
        "sin_gluten": (
            "Carnes/pescados naturales + tubérculos/arroz sin TACC + vegetales; leer etiquetas."
        ),
        "otro": "Priorizar proteína en cada comida + verduras + grasa saludable según tolerancia.",
    }


def _default_breakfast() -> str:
    return (
        "Opciones: yogur griego + avena + frutos rojos; o huevos revueltos + pan integral + fruta; "
        "café o té sin azúcar de más."
    )


def _default_merienda() -> str:
    return "Fruta + puñado de frutos secos o lácteo; o batido proteico si entrenás después."


# Paquetes por país: desayuno, merienda y (opcional) platos por estilo que sobrescriben el default.
REGION_HINTS: dict[str, _RegionPack] = {
    "AR": {
        "breakfast": (
            "Mate (sin azúcar) o café con leche + tostadas integrales con queso untable o ricota; "
            "yogur + avena y fruta; huevos revueltos con verdura."
        ),
        "merienda": (
            "Yogur + fruta; pan integral con palta; mix de frutos secos; licuado proteico si entrenás después."
        ),
        "plates": {
            "omnivoro": (
                "Carne magra a la plancha o pollo + ensalada grande + papa al horno o arroz; "
                "milanesa al horno con puré liviano o ensalada; pescado con verduras al vapor."
            ),
        },
    },
    "UY": {
        "breakfast": (
            "Café con leche + bizcochos integrales o tostadas con jamón cocido magro; yogur con cereal integral y fruta."
        ),
        "merienda": "Yogur + fruta; sandwich integral con fiambre magro; frutos secos.",
        "plates": {
            "omnivoro": (
                "Asado magro (vacío, pollo) + ensalada mixta + ensalada rusa en porción moderada; "
                "pescado a la plancha + verduras."
            ),
        },
    },
    "MX": {
        "breakfast": (
            "Huevos a la mexicana con tortillas de maíz integral; avena con leche y plátano; licuado verde sin azúcar extra."
        ),
        "merienda": (
            "Fruta + cacahuates tostados (puñado); elote desgranado sin exceso de crema; yogur con granola."
        ),
        "plates": {
            "omnivoro": (
                "Pollo o carne magra + frijoles de olla + arroz integral + ensalada; tacos blandas con proteína y verdura; "
                "sopa de verdura + plato principal moderado."
            ),
        },
    },
    "CO": {
        "breakfast": "Arepa integral con huevo y aguacate; avena con leche; fruta fresca.",
        "merienda": "Fruta tropical + yogur; handful nueces; café negro o té.",
        "plates": {
            "omnivoro": (
                "Pollo o pescado a la plancha + arroz integral + ensalada + legumbres (lentejas); "
                "menos frito y salsas muy cargadas."
            ),
        },
    },
    "ES": {
        "breakfast": (
            "Pan integral con AOVE + tomate o aguacate; yogur con frutos secos; café con leche desnatada."
        ),
        "merienda": "Fruta + frutos secos; bocadillo integral con pavo o atún; horchata pequeña si te gusta.",
        "plates": {
            "omnivoro": (
                "Pescado a la plancha + ensalada mediterránea + patata al horno; pollo + verduras salteadas; "
                "legumbres guisadas en porción medida."
            ),
        },
    },
    "CL": {
        "breakfast": "Pan integral con palta y huevo; avena con leche; té o café.",
        "merienda": "Fruta + yogur; mix frutos secos; barrita proteica si entrenás.",
        "plates": {
            "omnivoro": (
                "Pollo o pescado + ensalada chilena (tomate, cebolla suave) + arroz o papa cocida; "
                "menos sal en mesa."
            ),
        },
    },
    "PE": {
        "breakfast": "Pan integral con huevo; avena; papaya o plátano; café.",
        "merienda": "Fruta + yogur; cancha (maíz) en porción pequeña si te gusta; infusión.",
        "plates": {
            "omnivoro": (
                "Pollo o pescado + menestra de lentejas o garbanzos + arroz integral en porción moderada + ensalada."
            ),
        },
    },
    "BR": {
        "breakfast": (
            "Pão integral com ovo e queijo magro; aveia com fruta; café preto ou café com leite desnatado."
        ),
        "merienda": "Fruta + castanhas ou iogurte; vitamina com whey se treinar.",
        "plates": {
            "omnivoro": (
                "Frango grelhado ou peixe + arroz integral + feijão em porção moderada + salada crua; "
                "evitar frituras e óleo em excesso."
            ),
        },
    },
    "US": {
        "breakfast": (
            "Oatmeal with berries and eggs; Greek yogurt parfait; whole-grain toast with nut butter; black coffee."
        ),
        "merienda": "Apple + nuts; protein shake; cottage cheese and fruit.",
        "plates": {
            "omnivoro": (
                "Grilled chicken or fish + mixed greens + baked potato or brown rice; "
                "lean beef with veggies; watch sauces and dressings."
            ),
        },
    },
    "CA": {
        "breakfast": (
            "Oatmeal with maple syrup (little) and berries; eggs with whole-grain toast; Greek yogurt."
        ),
        "merienda": "Fruit + nuts; protein smoothie; cheese stick with veggies.",
        "plates": {
            "omnivoro": (
                "Grilled salmon or chicken + quinoa or rice + salad; turkey chili with beans and vegetables."
            ),
        },
    },
    "GB": {
        "breakfast": "Wholemeal toast + eggs; porridge with fruit; beans on toast (portion-controlled).",
        "merienda": "Fruit + yogurt; handful nuts; tea with milk optional.",
        "plates": {
            "omnivoro": (
                "Roast lean meat or grilled fish + steamed veg + potato (not heavy gravy); "
                "chicken stir-fry with brown rice."
            ),
        },
    },
    "FR": {
        "breakfast": (
            "Pain complet + fromage blanc ou yaourt; café noir; éviter trop de viennoiseries au quotidien."
        ),
        "merienda": "Yaourt + fruit; poignée de noix; infusion.",
        "plates": {
            "omnivoro": (
                "Poisson ou volaille grillé + légumes vapeur + petite portion féculents; salade en entrée; huile d’olive modérée."
            ),
        },
    },
    "DE": {
        "breakfast": (
            "Vollkornbrot mit Magerquark oder Ei; Haferflocken mit Obst; Kaffee oder Tee."
        ),
        "merienda": "Obst + Joghurt; Handvoll Nüsse; Proteinriegel nach Training.",
        "plates": {
            "omnivoro": (
                "Gegrilltes Hähnchen oder Fisch + Salzkartoffeln oder Reis + großer Salat; weniger paniertes Fleisch."
            ),
        },
    },
    "IT": {
        "breakfast": (
            "Caffè e biscotti integrali moderati; yogurt greco con frutta e noci; pane integrale con ricotta magra."
        ),
        "merienda": "Frutta + mandorle; yogurt; spremuta.",
        "plates": {
            "omnivoro": (
                "Pasta integrale con sugo di verdure e carne magra (porzione misurata); pesce al forno + contorno di verdure; "
                "olio EVO con moderazione."
            ),
        },
    },
    "IN": {
        "breakfast": (
            "Besan chilla or moong dal dosa (less oil); idli with sambar (veg protein); masala oats; chai with less sugar."
        ),
        "merienda": "Fruit + handful roasted chana; buttermilk (chaas); nuts.",
        "plates": {
            "omnivoro": (
                "Grilled chicken or fish + dal + small portion brown rice or roti + sabzi; "
                "choose grilled/tandoor over creamy curries."
            ),
            "vegetariano": (
                "Dal + sabzi + roti integral en cantidad medida + ensalada; paneer a la plancha con menos crema; "
                "legumbres en cada comida principal."
            ),
            "vegano": (
                "Dal + tofu sofrito + arroz integral + verduras; legumbres variadas; frutos secos moderados."
            ),
        },
    },
    "JP": {
        "breakfast": (
            "Sopa miso + huevo + natto + arroz (1 tazón); pan integral + yogur; moderar carbohidratos refinados."
        ),
        "merienda": "Yogur + frutos secos; batido proteico; pieza de fruta.",
        "plates": {
            "omnivoro": (
                "Pescado a la plancha + verduras cocidas + arroz en porción moderada; yakitori sin exceso de piel; "
                "fritos solo ocasionalmente."
            ),
        },
    },
    "CN": {
        "breakfast": (
            "Gachas de avena + huevo + leche de soja sin azúcar; bao integral en porción moderada; evitar fritos diarios."
        ),
        "merienda": "Fruta + puñado de frutos secos; yogur sin azúcar añadido.",
        "plates": {
            "omnivoro": (
                "Pescado al vapor o pechuga + verduras variadas + arroz integral en cantidad moderada; "
                "salteados con poco aceite; sopas sin exceso de grasa flotante."
            ),
        },
    },
    "AU": {
        "breakfast": (
            "Wholegrain toast + eggs and avocado; Greek yogurt + fruit; flat white with less syrup."
        ),
        "merienda": "Fruit + nuts; protein shake; rice cakes with tuna.",
        "plates": {
            "omnivoro": (
                "Grilled barramundi or chicken + salad + sweet potato; lean beef stir-fry with veg and rice."
            ),
        },
    },
    "VE": {
        "breakfast": "Arepa integral con queso bajo en grasa y huevo; avena; café negro.",
        "merienda": "Fruta + yogur; pepitas (puñado); té.",
        "plates": {
            "omnivoro": (
                "Pollo o carne magra a la plancha + caraotas negras en porción + arroz integral + ensalada."
            ),
        },
    },
    "EC": {
        "breakfast": "Bolón de verde en porción moderada o pan integral + huevo; fruta; café.",
        "merienda": "Fruta + nueces; yogurt.",
        "plates": {
            "omnivoro": (
                "Pollo o pescado + menestra + arroz integral en porción medida + ensalada; menos frito."
            ),
        },
    },
    "PT": {
        "breakfast": (
            "Pão integral com queijo magro; aveia com fruta; café com leite desnatado."
        ),
        "merienda": "Iogurte + fruta; punhado de frutos secos.",
        "plates": {
            "omnivoro": (
                "Peixe grelhado ou frango + batata cozida ou arroz integral + salada; sopa de legumes como entrada."
            ),
        },
    },
}


def meal_hints_for_country(country_code: str | None) -> tuple[str, str, dict[str, str]]:
    """Devuelve (desayuno, merienda, mapa de platos por diet_style)."""
    code = (country_code or "").strip().upper()
    if code in ("", "OT", "XX"):
        code = "XX"
    pack = REGION_HINTS.get(code)
    base_plates = _default_plates()
    if not pack:
        return _default_breakfast(), _default_merienda(), base_plates
    plates = {**base_plates, **pack.get("plates", {})}
    return (
        pack.get("breakfast", _default_breakfast()),
        pack.get("merienda", _default_merienda()),
        plates,
    )


def country_label_es(code: str | None) -> str:
    """Etiqueta corta para meta/UI (español)."""
    code = (code or "").strip().upper()
    if code in ("", "XX", "OT"):
        return "General / sin país específico"
    labels = {
        "AR": "Argentina",
        "AU": "Australia",
        "BO": "Bolivia",
        "BR": "Brasil",
        "CA": "Canadá",
        "CL": "Chile",
        "CN": "China",
        "CO": "Colombia",
        "KR": "Corea del Sur",
        "CR": "Costa Rica",
        "EC": "Ecuador",
        "EG": "Egipto",
        "SV": "El Salvador",
        "AE": "Emiratos Árabes Unidos",
        "ES": "España",
        "US": "Estados Unidos",
        "FR": "Francia",
        "GT": "Guatemala",
        "HN": "Honduras",
        "NL": "Países Bajos",
        "IN": "India",
        "ID": "Indonesia",
        "IT": "Italia",
        "JP": "Japón",
        "MA": "Marruecos",
        "MX": "México",
        "NI": "Nicaragua",
        "NZ": "Nueva Zelanda",
        "NO": "Noruega",
        "PA": "Panamá",
        "PY": "Paraguay",
        "PE": "Perú",
        "PL": "Polonia",
        "PT": "Portugal",
        "PR": "Puerto Rico",
        "GB": "Reino Unido",
        "DO": "República Dominicana",
        "ZA": "Sudáfrica",
        "SE": "Suecia",
        "CH": "Suiza",
        "UY": "Uruguay",
        "VE": "Venezuela",
        "DE": "Alemania",
    }
    return labels.get(code, f"País ({code})")

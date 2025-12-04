"""
Premium, world-class proposal structure for TAQINOR solar quotations.
This module provides a ready-to-use, number-free framework with clear sections
and placeholders, suitable for feeding into PDF/HTML generators.
"""

from collections import OrderedDict
from typing import List, Dict, Any


def get_premium_proposal_structure() -> List[Dict[str, Any]]:
    """
    Returns an ordered structure of the full premium proposal with headings and placeholders.
    No prices or numeric values are included; placeholders are provided instead.
    """
    return [
        OrderedDict(
            [
                ("section", "Cover page"),
                (
                    "content",
                    [
                        "TAQINOR — Proposition Solaire Premium",
                        "Client : {{CLIENT_NAME}}",
                        "Adresse : {{CLIENT_ADDRESS}}",
                        "Date : {{PROPOSAL_DATE}}",
                        "Référence : {{PROPOSAL_REF}}",
                        "Visuel pleine page (image de toiture ou visuel corporate premium)",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Executive summary"),
                (
                    "content",
                    [
                        "Objectif principal : {{OBJECTIF_CLE}}",
                        "Bénéfices majeurs : {{BENEFICES_MAJORS_LIST}}",
                        "Synthèse des deux options : {{SYNTHese_OPTIONS}}",
                        "Engagement TAQINOR : accompagnement clé en main et qualité EPC premium.",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Client objectives"),
                (
                    "content",
                    [
                        "Réduction des coûts énergétiques : {{OBJECTIF_ECO}}",
                        "Autonomie et résilience : {{OBJECTIF_AUTONOMIE}}",
                        "Durabilité et image RSE : {{OBJECTIF_RSE}}",
                        "Contraintes spécifiques du site : {{CONTRAINTES_SITE}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Solar system recommendation"),
                (
                    "content",
                    [
                        "Configuration globale proposée : {{CONFIG_GLOBAL}}",
                        "Puissance cible (placeholder) : {{PUISSANCE_KWC}}",
                        "Architecture : {{ARCHITECTURE_SYSTEME}}",
                        "Stratégie d’autoconsommation : {{STRATEGIE_AUTO}}",
                        "Pré-requis réseau / raccordement : {{PRE_REQUIS_RESEAU}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Premium equipment list with specs"),
                (
                    "content",
                    [
                        "Modules photovoltaïques : {{PANNEAUX_MODEL}}, specs : {{PANNEAUX_SPECS}}",
                        "Onduleurs / hybrides : {{ONDULEUR_MODEL}}, specs : {{ONDULEUR_SPECS}}",
                        "Batteries (option) : {{BATTERIE_MODEL}}, specs : {{BATTERIE_SPECS}}",
                        "Structures : {{STRUCTURE_TYPE}}, specs : {{STRUCTURE_SPECS}}",
                        "Smart meter & monitoring : {{SMART_METER_SPECS}}",
                        "Tableau AC/DC & protections : {{TABLEAU_SPECS}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Visual layout placeholders"),
                (
                    "content",
                    [
                        "Plan de toiture (placeholder visuel haute résolution)",
                        "Schéma de principe du système (placeholder diagramme)",
                        "Schéma électrique unifilaire (placeholder diagramme)",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Installation workflow timeline"),
                (
                    "content",
                    [
                        "Étape 1 — Visite technique : {{DATE_VISITE}}",
                        "Étape 2 — Validation du design : {{DATE_DESIGN}}",
                        "Étape 3 — Installation : {{DATE_INSTALL}}",
                        "Étape 4 — Mise en service & tests : {{DATE_MISE_EN_SERVICE}}",
                        "Étape 5 — Formation utilisateur : {{DATE_FORMATION}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Detailed pricing tables for both options"),
                (
                    "content",
                    [
                        "Tableau Option 1 — SANS batterie : {{TABLE_OPTION1_PLACEHOLDER}}",
                        "Tableau Option 2 — AVEC batterie : {{TABLE_OPTION2_PLACEHOLDER}}",
                        "Note : insérer lignes, quantités et prix dans le générateur PDF (placeholders uniquement ici).",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Full ROI analysis with charts placeholders"),
                (
                    "content",
                    [
                        "Production annuelle estimée : {{PROD_ANNUELLE_PLACEHOLDER}}",
                        "Économies annuelles estimées : {{ECONOMIES_PLACEHOLDER}}",
                        "Temps de retour sur investissement : {{ROI_PLACEHOLDER}}",
                        "Graphique comparatif SANS vs AVEC batterie : {{CHART_ROI_PLACEHOLDER}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Environmental impact section"),
                (
                    "content",
                    [
                        "Réduction CO₂ estimée : {{CO2_PLACEHOLDER}}",
                        "Équivalent arbres plantés : {{ARBRES_PLACEHOLDER}}",
                        "Contribution aux objectifs RSE : {{RSE_PLACEHOLDER}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Technical compliance and certifications"),
                (
                    "content",
                    [
                        "Normes électriques applicables : {{NORMES_ELEC}}",
                        "Certifications équipements : {{CERT_EQUIP}}",
                        "Conformité réseau / utility : {{CONFORMITE_RESEAU}}",
                        "Garanties constructeur : {{GARANTIES_CONSTRUCTEUR}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Maintenance & after-sales plan"),
                (
                    "content",
                    [
                        "Plan de maintenance préventive : {{MAINT_PREVENTIVE}}",
                        "Support après-vente (7j/7) : {{SAV_DETAILS}}",
                        "Monitoring continu : {{MONITORING_DETAILS}}",
                        "Interventions sur site : {{INTERVENTIONS_SITE}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "TAQINOR strengths & guarantees"),
                (
                    "content",
                    [
                        "Expertise EPC premium : {{EXPERTISE_EPC}}",
                        "Matériel premium : Huawei, Deye, Canadian Solar (placeholders specs)",
                        "Engagement qualité et sécurité : {{ENGAGEMENT_QUALITE}}",
                        "Réactivité et accompagnement : {{REACTIVITE_ACC}}",
                    ],
                ),
            ]
        ),
        OrderedDict(
            [
                ("section", "Signature page"),
                (
                    "content",
                    [
                        "Signature client : ___________________________",
                        "Nom : {{CLIENT_NAME}}    Date : __ / __ / ____",
                        "Signature TAQINOR : ___________________________",
                        "Nom : {{TAQINOR_REP}}    Date : __ / __ / ____",
                    ],
                ),
            ]
        ),
    ]


if __name__ == "__main__":
    import json

    structure = get_premium_proposal_structure()
    print(json.dumps(structure, ensure_ascii=False, indent=2))

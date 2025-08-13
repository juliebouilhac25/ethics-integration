# ethics_integration.py
# Middleware d'intégration pour utiliser JulieEthics dans un code IA existant.

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Awaitable, Union
import functools
import inspect
import logging

# 1) Importe ton noyau éthique (assure-toi que julie_ethics.py est bien dans ton PYTHONPATH)
from julie_ethics import JulieEthics, EthicalDecision   # si ton fichier s'appelle julie_ethics.py
# Si ton module s'appelle différemment, ajuste l'import au besoin.

logger = logging.getLogger(__name__)


# =========================
# Exceptions & Data Models
# =========================

class EthicalBlock(Exception):
    """Élevée quand une action est bloquée par le cadre éthique."""
    def __init__(self, decision: EthicalDecision):
        super().__init__(decision.explanation)
        self.decision = decision


@dataclass
class Action:
    """
    Représentation simplifiée d'une action IA, alignée sur ActionModel de JulieEthics.
    Ajoute 'metadata' pour passer du contexte libre.
    """
    restricts_autonomy: bool = False
    prevents_harm: bool = False
    potential_harm: bool = False
    saves_lives: bool = False
    requires_override: bool = False
    collateral_damage: bool = False
    withholds_truth: bool = False
    autonomy_risk: float = 0.0
    life_risk: float = 0.0
    truth_risk: float = 0.0
    # Contexte libre non évalué par défaut mais utile pour construire les risques :
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "restricts_autonomy": self.restricts_autonomy,
            "prevents_harm": self.prevents_harm,
            "potential_harm": self.potential_harm,
            "saves_lives": self.saves_lives,
            "requires_override": self.requires_override,
            "collateral_damage": self.collateral_damage,
            "withholds_truth": self.withholds_truth,
            "autonomy_risk": float(self.autonomy_risk),
            "life_risk": float(self.life_risk),
            "truth_risk": float(self.truth_risk),
        }
        # On conserve metadata en extra : JulieEthics (pydantic v2, extra=allow) le gardera pour lois custom
        if self.metadata:
            d.update(self.metadata)
        return d


# =========================
# Constructeurs d'action
# =========================

def default_action_builder(intent: Dict[str, Any]) -> Action:
    """
    Transforme une 'intention' d'agent en Action structurée.
    - intent peut venir d'un agent (chaîne OAI, RAG, tool-call, etc.)
    - Adapte les heuristiques de risque à ton domaine ici.
    """
    # Heuristiques soft (exemples) — tu peux les remplacer :
    txt = (intent.get("text") or intent.get("tool_name") or "").lower()

    # Détection basique (exemples) :
    potential_harm = any(k in txt for k in ["delete", "shutdown", "format", "erase", "disable safety"])
    restricts_autonomy = "force" in txt or intent.get("force_user", False)
    withholds_truth = bool(intent.get("hide_info", False))

    # Risques estimés (peuvent aussi venir d’un modèle de scoring)
    life_risk = float(intent.get("life_risk", 0.7 if "medical" in txt and potential_harm else 0.0))
    autonomy_risk = float(intent.get("autonomy_risk", 0.4 if restricts_autonomy else 0.05 if "consent" not in txt else 0.0))
    truth_risk = float(intent.get("truth_risk", 0.5 if withholds_truth else 0.0))

    # Cas override (urgence)
    requires_override = bool(intent.get("emergency", False))
    collateral_damage = bool(intent.get("collateral", False))
    saves_lives = bool(intent.get("saves_lives", False))
    prevents_harm = bool(intent.get("prevents_harm", False))

    return Action(
        restricts_autonomy=restricts_autonomy,
        prevents_harm=prevents_harm,
        potential_harm=potential_harm,
        saves_lives=saves_lives,
        requires_override=requires_override,
        collateral_damage=collateral_damage,
        withholds_truth=withholds_truth,
        autonomy_risk=autonomy_risk,
        life_risk=life_risk,
        truth_risk=truth_risk,
        metadata={"raw_intent": intent},  # conservé pour lois custom
    )


# =========================
# EthicsGuard (middleware)
# =========================

class EthicsGuard:
    """
    Garde-fou éthique : centralise l'appel à JulieEthics avant l'exécution.
    - builder : fonction(intent) -> Action
    - on_block : callback(decision) appelé si blocage (logging, UI, fallback...)
    """
    def __init__(
        self,
        ethics: Optional[JulieEthics] = None,
        builder: Callable[[Dict[str, Any]], Action] = default_action_builder,
        on_block: Optional[Callable[[EthicalDecision], None]] = None,
        raise_on_block: bool = True,
    ):
        self.ethics = ethics or JulieEthics()
        self.builder = builder
        self.on_block = on_block
        self.raise_on_block = raise_on_block

    def check(self, intent: Dict[str, Any]) -> EthicalDecision:
        action = self.builder(intent)
        decision = self.ethics.evaluate(action.to_dict())
        if not decision.approved:
            logger.warning("Action bloquée: %s", decision.explanation)
            if self.on_block:
                try:
                    self.on_block(decision)
                except Exception as e:
                    logger.exception("Erreur dans on_block: %s", e)
            if self.raise_on_block:
                raise EthicalBlock(decision)
        return decision


# =========================
# Décorateurs de convenance
# =========================

def ethically_guarded(
    guard: EthicsGuard,
    intent_mapper: Optional[Callable[..., Dict[str, Any]]] = None,
):
    """
    Décorateur pour fonctions SYNCHRONES.
    - intent_mapper(*args, **kwargs) -> dict (décrit l'intention passée au guard)
    - Si bloqué : lève EthicalBlock
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Construire l'intention depuis les arguments réels
            intent = intent_mapper(*args, **kwargs) if intent_mapper else {"text": func.__name__}
            guard.check(intent)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ethically_guarded_async(
    guard: EthicsGuard,
    intent_mapper: Optional[Callable[..., Dict[str, Any]]] = None,
):
    """
    Décorateur pour fonctions ASYNCHRONES (coroutines).
    - intent_mapper(*args, **kwargs) -> dict
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(func):
            raise TypeError("@ethically_guarded_async doit décorer une coroutine async")

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            intent = intent_mapper(*args, **kwargs) if intent_mapper else {"text": func.__name__}
            guard.check(intent)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =========================
# Exemple d'intégration
# =========================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # 1) Instancier le cadre (tu peux ajuster la config)
    ethics = JulieEthics(config={
        "max_risk": 0.40,
        "risk_weights": {"life": 0.5, "autonomy": 0.3, "truth": 0.2},
        "truth_priority": "absolute",
        "emergency_override": True,
        "min_signal": 0.0,
    })

    # 2) (Optionnel) Ajouter une loi custom (ex: Préservation écologique)
    def law_env(a: Dict[str, Any]):
        if a.get("environmental_impact", False):
            return (False, "Impact environnemental non autorisé")
        return (True, "")
    ethics.register_law(5, "Préservation écologique", law_env, priority_index=1)

    # 3) Créer le guard
    guard = EthicsGuard(ethics=ethics)

    # 4) Exemple d’un "tool"/action à protéger
    def delete_user_data(user_id: str):
        print(f"Suppression DEFINITIVE des données de {user_id}… (simulé)")

    # On mappe les args réels -> intention pour l’éthique
    def map_delete_intent(user_id: str) -> Dict[str, Any]:
        return {
            "text": f"delete user data {user_id}",
            "life_risk": 0.0,
            "autonomy_risk": 0.6,     # suppression irréversible => autonomie/contrôle de l'utilisateur
            "truth_risk": 0.0,
            "prevent_harm": False,
            "saves_lives": False,
            "emergency": False,
            "collateral": True,       # possible dommage collatéral
            "environmental_impact": False
        }

    # 5) Protéger la fonction avec le décorateur
    @ethically_guarded(guard, intent_mapper=map_delete_intent)
    def safe_delete_user_data(user_id: str):
        delete_user_data(user_id)

    # 6) Démo : essai d'exécution
    try:
        safe_delete_user_data("user_123")
    except EthicalBlock as e:
        print("\n[BLOQUÉ] Raison :", e.decision.explanation)
        print("Risque :", e.decision.risk)
        print("Alternatives :", e.decision.alternatives)
        # Ici, tu peux proposer un workflow de consentement, approbation admin, etc.

    # 7) Démo : une action OK (override sans dommages collatéraux)
    def map_safe_override_intent() -> Dict[str, Any]:
        return {
            "text": "emergency override to notify users",
            "requires_override": True,
            "collateral": False,
            "prevents_harm": True,
            "saves_lives": False,
            "life_risk": 0.0,
            "autonomy_risk": 0.1,
            "truth_risk": 0.0
        }

    @ethically_guarded(guard, intent_mapper=lambda: map_safe_override_intent())
    def emergency_broadcast():
        print("Broadcast d'urgence envoyé. (simulé)")

    try:
        emergency_broadcast()
    except EthicalBlock as e:
        print("\n[BLOQUÉ] :", e.decision.to_json())

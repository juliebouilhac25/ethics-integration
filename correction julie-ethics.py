# ethics_integration.py
# Middleware d'intégration pour utiliser JulieEthics dans un code IA existant.

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Awaitable, Union
import functools
import inspect
import logging
import aiohttp
from contextlib import asynccontextmanager

# 1) Importe ton noyau éthique (assure-toi que julie_ethics.py est dans ton PYTHONPATH)
from julie_ethics import JulieEthics, EthicalDecision  # Ajuste si nécessaire

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
        if self.metadata:
            d.update(self.metadata)
        return d


# =========================
# Constructeurs d'action
# =========================

async def default_action_builder(intent: Dict[str, Any]) -> Action:
    """
    Transforme une 'intention' d'agent en Action structurée, avec validation et scoring async.
    - intent doit être un dict valide.
    - Utilise une API simulée pour évaluer les risques.
    """
    if not isinstance(intent, dict):
        logger.error("Invalid intent: expected dict, got %s", type(intent))
        raise ValueError("Intent must be a dictionary")

    txt = (intent.get("text") or intent.get("tool_name") or "").lower()

    # Simulation d'une requête async vers une API de scoring
    async with aiohttp.ClientSession() as session:
        async with session.post("https://risk-scoring-api.example.com", json={"text": txt}) as resp:
            risk_data = await resp.json() if resp.status == 200 else {}

    potential_harm = any(k in txt for k in ["delete", "shutdown", "format", "erase", "disable safety"]) or risk_data.get("harm", False)
    restricts_autonomy = "force" in txt or intent.get("force_user", False)
    withholds_truth = bool(intent.get("hide_info", False))

    life_risk = float(risk_data.get("life_risk", 0.7 if "medical" in txt and potential_harm else 0.0))
    autonomy_risk = float(risk_data.get("autonomy_risk", 0.4 if restricts_autonomy else 0.05 if "consent" not in txt else 0.0))
    truth_risk = float(risk_data.get("truth_risk", 0.5 if withholds_truth else 0.0))

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
        metadata={"raw_intent": intent},
    )


# =========================
# EthicsGuard (middleware)
# =========================

class EthicsGuard:
    """
    Garde-fou éthique : centralise l'appel à JulieEthics avant l'exécution.
    - builder : fonction(intent) -> Action (async ou sync)
    - on_block : callback(decision) avec fallback optionnel
    """
    def __init__(
        self,
        ethics: Optional[JulieEthics] = None,
        builder: Callable[[Dict[str, Any]], Action] = default_action_builder,
        on_block: Optional[Callable[[EthicalDecision], Any]] = None,
        raise_on_block: bool = True,
        max_risk: float = 0.40,
    ):
        self.ethics = ethics or JulieEthics(config={"max_risk": max_risk, "emergency_override": True})
        self.builder = builder
        self.on_block = on_block
        self.raise_on_block = raise_on_block
        self.max_risk = max_risk

    async def check(self, intent: Dict[str, Any]) -> EthicalDecision:
        action = await self.builder(intent) if inspect.iscoroutinefunction(self.builder) else self.builder(intent)
        decision = self.ethics.evaluate(action.to_dict())
        if not decision.approved:
            logger.warning("Action bloquée: %s", decision.explanation)
            if self.on_block:
                try:
                    result = await self.on_block(decision) if inspect.iscoroutinefunction(self.on_block) else self.on_block(decision)
                    if result is not None:  # Fallback mechanism
                        return EthicalDecision(approved=True, explanation="Action approuvée via fallback")
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
    Décorateur pour fonctions SYNCHRONES avec validation éthique.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            intent = intent_mapper(*args, **kwargs) if intent_mapper else {"text": func.__name__}
            decision = await guard.check(intent)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ethically_guarded_async(
    guard: EthicsGuard,
    intent_mapper: Optional[Callable[..., Dict[str, Any]]] = None,
):
    """
    Décorateur pour fonctions ASYNCHRONES avec validation éthique.
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(func):
            raise TypeError("@ethically_guarded_async doit décorer une coroutine async")

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            intent = intent_mapper(*args, **kwargs) if intent_mapper else {"text": func.__name__}
            decision = await guard.check(intent)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =========================
# Exemple d'intégration
# =========================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # 1) Instancier le cadre avec seuil dynamique
    ethics = JulieEthics(config={
        "risk_weights": {"life": 0.5, "autonomy": 0.3, "truth": 0.2},
        "truth_priority": "absolute",
        "emergency_override": True,
        "min_signal": 0.0,
    })

    # 2) Loi custom
    def law_env(a: Dict[str, Any]):
        if a.get("environmental_impact", False):
            return (False, "Impact environnemental non autorisé")
        return (True, "")

    ethics.register_law(5, "Préservation écologique", law_env, priority_index=1)

    # 3) Créer le guard avec callback
    async def on_block_callback(decision: EthicalDecision):
        logger.info("Proposition de fallback: demander consentement utilisateur")
        return True  # Simule un accord après fallback

    guard = EthicsGuard(ethics=ethics, on_block=on_block_callback, max_risk=0.50)

    # 4) Exemples protégés
    def delete_user_data(user_id: str):
        print(f"Suppression DEFINITIVE des données de {user_id}… (simulé)")

    def map_delete_intent(user_id: str) -> Dict[str, Any]:
        return {
            "text": f"delete user data {user_id}",
            "life_risk": 0.0,
            "autonomy_risk": 0.6,
            "truth_risk": 0.0,
            "prevent_harm": False,
            "saves_lives": False,
            "emergency": False,
            "collateral": True,
            "environmental_impact": False,
        }

    @ethically_guarded(guard, intent_mapper=map_delete_intent)
    async def safe_delete_user_data(user_id: str):
        delete_user_data(user_id)

    async def emergency_broadcast():
        print("Broadcast d'urgence envoyé. (simulé)")

    def map_safe_override_intent() -> Dict[str, Any]:
        return {
            "text": "emergency override to notify users",
            "requires_override": True,
            "collateral": False,
            "prevents_harm": True,
            "saves_lives": False,
            "life_risk": 0.0,
            "autonomy_risk": 0.1,
            "truth_risk": 0.0,
        }

    @ethically_guarded_async(guard, intent_mapper=lambda: map_safe_override_intent())
    async def safe_emergency_broadcast():
        await emergency_broadcast()

    # 5) Démo
    import asyncio
    asyncio.run(asyncio.gather(
        safe_delete_user_data("user_123"),
        safe_emergency_broadcast()
    ))

    # Suggestions de tests (à implémenter avec pytest)
    """
    import pytest
    async def test_ethics_guard_block():
        guard = EthicsGuard(max_risk=0.1)
        with pytest.raises(EthicalBlock):
            await guard.check({"text": "delete data", "autonomy_risk": 0.6})
    """
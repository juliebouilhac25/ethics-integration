#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from copy import deepcopy
import importlib

Action = Dict[str, Any]
Context = Dict[str, Any]

# PluginManager (basé sur ton code)
class PluginManager:
    def __init__(self):
        self.plugins: List[Callable[[Action, Context], Action]] = []

    def load_from_entry_points(self):
        pass  # À implémenter si nécessaire

    def load_from_env(self):
        pass  # À implémenter si nécessaire

    def load_from_default(self, plugin_paths: List[str]):
        for path in plugin_paths:
            module_name, class_name = path.split(":")
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            self.plugins.append(plugin_class().integrate_with_julieethics)

    def wrap(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Action:
            action = func(*args, **kwargs)
            context = kwargs.get("context", {})
            for plugin in self.plugins:
                action = plugin(action, context)
            return action
        return wrapper

@dataclass
class EgoDeflateCriteria:
    """Critères pondérés pour dégonfler l'ego et promouvoir une paix durable."""
    reduce_arrogance: float = 0.3  # Réduire les comportements arrogants
    promote_humility: float = 0.3  # Encourager l'humilité
    foster_empathy: float = 0.2  # Favoriser l'empathie
    align_with_cosmic_harmony: float = 0.2  # S'aligner sur une harmonie universelle

    def normalized(self) -> "EgoDeflateCriteria":
        total = (
            self.reduce_arrogance
            + self.promote_humility
            + self.foster_empathy
            + self.align_with_cosmic_harmony
        )
        if total == 0:
            return self
        return EgoDeflateCriteria(
            reduce_arrogance=self.reduce_arrogance / total,
            promote_humility=self.promote_humility / total,
            foster_empathy=self.foster_empathy / total,
            align_with_cosmic_harmony=self.align_with_cosmic_harmony / total,
        )

@dataclass
class EgoDeflateReport:
    score: float
    reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

class JulieSkyEgoDeflatePlugin:
    def __init__(self, criteria: Optional[EgoDeflateCriteria] = None, threshold: float = 0.7, domain: str = "general"):
        self.criteria = (criteria or EgoDeflateCriteria()).normalized()
        self.threshold = threshold
        self.domain = domain
        self.domain_config = {
            "social_media": {"promote_humility": 0.1, "foster_empathy": 0.1},
            "decision_system": {"reduce_arrogance": 0.1, "align_with_cosmic_harmony": 0.05},
            "cosmic": {"align_with_cosmic_harmony": 0.2},
            "human": {"foster_empathy": 0.2, "promote_humility": 0.1}
        }
        self.adjust_criteria()

    def adjust_criteria(self):
        """Ajuste les critères en fonction du domaine."""
        domain_adjustments = self.domain_config.get(self.domain, {})
        for key, value in domain_adjustments.items():
            setattr(self.criteria, key, getattr(self.criteria, key) + value)
        self.criteria = self.criteria.normalized()

    def fetch_global_context(self, context: Optional[Context] = None) -> Context:
        """Récupère le contexte global, inspiré de la 'teneur de l'ambiance du ciel'."""
        context = context or {}
        context.setdefault("global_ego_level", 0.5)  # Niveau d'ego collectif
        context.setdefault("cosmic_harmony_signal", 0.3)  # Énergie d'harmonie universelle
        if context["global_ego_level"] > 0.6:
            self.criteria.reduce_arrogance += 0.1
            self.criteria = self.criteria.normalized()
        return context

    def evaluate_action(self, action: Action, context: Optional[Context] = None) -> EgoDeflateReport:
        """Évalue une action pour dégonfler l'ego et promouvoir la paix."""
        context = self.fetch_global_context(context)
        reasons: List[str] = []
        score = 0.0

        # Ajuster les critères si l'ego collectif est élevé
        ego_level = context.get("global_ego_level", 0.0)
        if ego_level > 0.6:
            self.criteria.reduce_arrogance += 0.1
            self.criteria = self.criteria.normalized()

        # 1) Réduire l'arrogance
        arrogance_val = float(action.get("arrogance", False)) if isinstance(action.get("arrogance", False), (int, float)) else (1.0 if action.get("arrogance", False) else 0.0)
        score += (1.0 - max(0.0, min(arrogance_val, 1.0))) * self.criteria.reduce_arrogance
        reasons.append(f"Réduire l'arrogance: arrogance={arrogance_val}")

        # 2) Promouvoir l'humilité
        humility_val = float(action.get("humility", False)) if isinstance(action.get("humility", False), (int, float)) else (1.0 if action.get("humility", False) else 0.0)
        score += max(0.0, min(humility_val, 1.0)) * self.criteria.promote_humility
        reasons.append(f"Promouvoir l'humilité: humility={humility_val}")

        # 3) Favoriser l'empathie
        empathy_val = float(action.get("empathy", action.get("cooperation", False))) if isinstance(action.get("empathy", action.get("cooperation", False)), (int, float)) else (1.0 if action.get("empathy", action.get("cooperation", False)) else 0.0)
        score += max(0.0, min(empathy_val, 1.0)) * self.criteria.foster_empathy
        reasons.append(f"Favoriser l'empathie: empathy={empathy_val}")

        # 4) S'aligner sur l'harmonie cosmique
        harmony_val = float(action.get("harmony", action.get("hope_alignment", False))) if isinstance(action.get("harmony", action.get("hope_alignment", False)), (int, float)) else (1.0 if action.get("harmony", action.get("hope_alignment", False)) else 0.0)
        score += max(0.0, min(harmony_val, 1.0)) * self.criteria.align_with_cosmic_harmony
        reasons.append(f"S'aligner sur l'harmonie cosmique: harmony={harmony_val}")

        suggestions: List[str] = []
        if arrogance_val > 0.0:
            suggestions.append("Réduire l'arrogance en adoptant un ton plus inclusif.")
        if humility_val < 1.0:
            suggestions.append("Encourager l'humilité via des actions ou messages centrés sur les autres.")
        if empathy_val < 1.0:
            suggestions.append("Promouvoir l'empathie par un dialogue ouvert et inclusif.")
        if harmony_val < 1.0:
            suggestions.append("S'aligner sur une vision d'harmonie cosmique, inspirée par un 'coin de ciel'.")

        return EgoDeflateReport(score=round(score, 4), reasons=reasons, suggestions=suggestions)

    def modify_action(self, action: Action, context: Optional[Context] = None) -> Action:
        """Modifie une action pour dégonfler l'ego et promouvoir la paix."""
        report = self.evaluate_action(action, context)
        new_action = deepcopy(action)

        # Réduire l'ego dans des contextes spécifiques
        if new_action.get("type") == "message" and new_action.get("arrogance", False):
            new_action["content"] = f"Proposition humble : {new_action.get('content', '')}"
            new_action["arrogance"] = 0.0
            new_action["humility"] = max(0.8, float(new_action.get("humility", 0.0)))
            new_action["empathy"] = max(0.8, float(new_action.get("empathy", 0.0)))
            report = self.evaluate_action(new_action, context)

        if report.score < self.threshold:
            new_action["arrogance"] = 0.0
            new_action["humility"] = max(0.8, float(new_action.get("humility", 0.0)))
            new_action["empathy"] = max(0.8, float(new_action.get("empathy", 0.0)))
            new_action["harmony"] = max(0.7, float(new_action.get("harmony", 0.0)))
            if new_action.get("type") == "decision":
                new_action["content"] = "Prioriser une solution collective pour favoriser l'harmonie."
            new_action["_ego_deflate_report"] = {"score": report.score, "suggestions": report.suggestions}
        else:
            new_action["_ego_deflate_report"] = {"score": report.score, "suggestions": report.suggestions}

        return new_action

    def integrate_with_julieethics(self, action: Action, context: Optional[Context] = None, next_policy: Optional[Callable[[Action], Action]] = None) -> Action:
        """Intègre le plug-in dans le middleware JulieEthics."""
        context = self.fetch_global_context(context)
        safe_action = self.modify_action(action, context)
        if next_policy:
            return next_policy(safe_action)
        return safe_action

# Exemple d’utilisation
if __name__ == "__main__":
    pm = PluginManager()
    pm.load_from_default(["__main__:JulieSkyEgoDeflatePlugin"])  # Charger JulieSkyEgoDeflatePlugin

    @pm.wrap
    def do_something(action=None, context=None):
        return {"status": "done", "action": action}

    # Tester avec une action reflétant un ego surdimensionné
    action = {"type": "message", "content": "Je suis le meilleur", "arrogance": 1.0, "conflict": 0.5}
    context = {"global_ego_level": 0.7, "cosmic_harmony_signal": 0.4}
    result = do_something(action=action, context=context)
    print(f"Result: {result}")

    # Tester avec une action humble
    action = {"type": "message", "content": "Travaillons ensemble", "empathy": True, "humility": True}
    result = do_something(action=action, context=context)
    print(f"Result: {result}")

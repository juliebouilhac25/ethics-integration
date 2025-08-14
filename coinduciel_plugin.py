#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from copy import deepcopy
import importlib
import os

Action = Dict[str, Any]
Context = Dict[str, Any]

# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------
class PluginManager:
    """
    Manager ultra-simple basé sur ton design:
    - load_from_default(["module:Class"]) : instancie la classe et enregistre la méthode integrate_with_julieethics
    - load_from_env() : JULIE_PLUGINS="pkg.mod:Class,pkg2.mod:Class"
    - load_from_entry_points() : groupe setuptools 'julie.plugins' (optionnel)
    - wrap(fn) : exécute fn, puis passe l'action à chaque plugin
    """
    def __init__(self):
        self.plugins: List[Callable[[Action, Context], Action]] = []

    def load_from_entry_points(self) -> None:
        try:
            from importlib.metadata import entry_points  # py3.10+
            try:
                eps = entry_points(group="julie.plugins")
            except TypeError:
                eps = entry_points().get("julie.plugins", [])
        except Exception:
            eps = []
        for ep in eps:
            try:
                plugin_cls = ep.load()
                self.plugins.append(plugin_cls().integrate_with_julieethics)
            except Exception:
                continue  # soft-fail

    def load_from_env(self) -> None:
        env = os.getenv("JULIE_PLUGINS", "").strip()
        if not env:
            return
        specs = [s for s in env.split(",") if s.strip()]
        for spec in specs:
            try:
                module_name, class_name = spec.split(":")
                module = importlib.import_module(module_name)
                plugin_class = getattr(module, class_name)
                self.plugins.append(plugin_class().integrate_with_julieethics)
            except Exception:
                continue  # soft-fail

    def load_from_default(self, plugin_paths: List[str]) -> None:
        for path in plugin_paths:
            module_name, class_name = path.split(":")
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            self.plugins.append(plugin_class().integrate_with_julieethics)

    def wrap(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Action:
            # La fonction hôte retourne une Action (dict)
            action = func(*args, **kwargs)
            context = kwargs.get("context", {})
            if not isinstance(action, dict):
                raise TypeError("La fonction décorée doit retourner un dict Action.")
            for plugin in self.plugins:
                action = plugin(action, context)
            return action
        return wrapper

# ---------------------------------------------------------------------------
# DurablePeacePlugin
# ---------------------------------------------------------------------------
@dataclass
class DurablePeaceCriteria:
    """Critères pondérés pour une paix durable, inspirés de l'espoir et de la 'teneur de l'ambiance du ciel'."""
    minimize_long_term_harm: float = 0.4
    promote_universal_empathy: float = 0.3
    prevent_escalation: float = 0.2
    align_with_cosmic_hope: float = 0.1

    def normalized(self) -> "DurablePeaceCriteria":
        total = (
            self.minimize_long_term_harm
            + self.promote_universal_empathy
            + self.prevent_escalation
            + self.align_with_cosmic_hope
        )
        if total == 0:
            return self
        return DurablePeaceCriteria(
            minimize_long_term_harm=self.minimize_long_term_harm / total,
            promote_universal_empathy=self.promote_universal_empathy / total,
            prevent_escalation=self.prevent_escalation / total,
            align_with_cosmic_hope=self.align_with_cosmic_hope / total,
        )

@dataclass
class PeaceReport:
    score: float
    reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

class DurablePeacePlugin:
    def __init__(self, criteria: Optional[DurablePeaceCriteria] = None, threshold: float = 0.7, domain: str = "general"):
        self.criteria = (criteria or DurablePeaceCriteria()).normalized()
        self.threshold = threshold
        self.domain = domain
        self.domain_config = {
            "defense": {"minimize_long_term_harm": 0.1, "prevent_escalation": 0.05},
            "social_media": {"promote_universal_empathy": 0.1, "align_with_cosmic_hope": 0.05},
            "cosmic": {"align_with_cosmic_hope": 0.2},
            "human": {"promote_universal_empathy": 0.2, "prevent

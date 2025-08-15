"""
Plugin Manager — ethics_integration

Objectifs:
- Chargement de plugins par chemin *dotted path* (ex: "pkg.module:ClassName").
- Découverte optionnelle via *entry points* (pyproject.toml).
- Priorisation, activation/désactivation et chaînage des plugins.
- Rapport d'exécution (_plugin_report) avec temps, erreurs et trace du pipeline.
- API simple et typée pour s'intégrer partout.

Usage minimal
-------------
from ethics_integration.plugin_manager import PluginManager, PluginConfig

pm = PluginManager()
pm.load_from_default([
    PluginConfig(
        path="ethics_integration.plugins.autonomy_collective:AutonomyCollectivePlugin",
        priority=10,
        kwargs={"some_flag": True},
    )
])

result = pm.process_action(
    action={"type": "decision", "selfishness": 1.0},
    context={"collaboration_level": 0.3},
)
print(result["_plugin_report"])  # pipeline et timings

Entry points (optionnel)
------------------------
Dans pyproject.toml:
[project.entry-points."ethics_integration.plugins"]
"autonomy_collective" = "ethics_integration.plugins.autonomy_collective:AutonomyCollectivePlugin"

Puis dans le code:
pm.load_from_entry_points()  # groupe par défaut: "ethics_integration.plugins"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from importlib.metadata import entry_points, EntryPoint
from typing import Any, Dict, List, Protocol, Optional, Callable, runtime_checkable
import logging
import time
import copy

__all__ = [
    "Plugin",
    "PluginConfig",
    "PluginManager",
    "PluginLoadError",
]


class PluginLoadError(Exception):
    """Erreur de chargement d'un plugin (mauvais chemin, classe invalide, etc.)."""


@runtime_checkable
class Plugin(Protocol):
    """Contrat minimal pour un plugin.

    Un plugin doit fournir au moins:
      - name: str (nom lisible)
      - priority: int (utilisé pour l'ordre d'exécution)
      - enabled: bool (permet de désactiver sans désinstaller)
      - process(action, context) -> dict

    Optionnels (s'ils existent, ils seront appelés):
      - before(action, context) -> None
      - after(result, context) -> None
    """

    name: str
    priority: int
    enabled: bool

    def process(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        ...  # pragma: no cover


@dataclass
class PluginConfig:
    """Configuration d'un plugin à charger dynamiquement."""

    path: str  # ex: "pkg.module:ClassName" ou "pkg.module" (détection auto)
    priority: int = 0
    enabled: bool = True
    kwargs: Dict[str, Any] = field(default_factory=dict)


def _resolve_symbol(module_path: str, attr: Optional[str]) -> Any:
    """Importe un module et retourne l'attribut approprié.

    Si attr est None, tente:
      1) attribut "Plugin"
      2) premier attribut se terminant par "Plugin"
      3) l'objet module lui-même (si *callable* et retourne un plugin)
    """
    mod = import_module(module_path)
    if attr:
        if not hasattr(mod, attr):
            raise PluginLoadError(f"L'attribut '{attr}' est introuvable dans '{module_path}'.")
        return getattr(mod, attr)

    # 1) 'Plugin'
    if hasattr(mod, "Plugin"):
        return getattr(mod, "Plugin")

    # 2) premier symbole se terminant par 'Plugin'
    for name in dir(mod):
        if name.endswith("Plugin"):
            return getattr(mod, name)

    # 3) module callable
    return mod


def _instantiate_plugin(symbol: Any, cfg: PluginConfig) -> Plugin:
    """Instancie un plugin à partir d'un symbole (classe/callable/objet).

    - Si c'est une classe: on l'instancie avec **kwargs.
    - Si c'est un callable: on l'appelle avec **kwargs et on s'attend à un objet Plugin.
    - Si c'est déjà un objet: on l'utilise tel quel.
    """
    obj: Any
    if isinstance(symbol, type):
        obj = symbol(**cfg.kwargs)
    elif callable(symbol):
        obj = symbol(**cfg.kwargs)
    else:
        obj = symbol

    # Normalisation des champs attendus
    if not hasattr(obj, "name"):
        obj.name = getattr(obj, "__class__", type("Anon", (), {})).__name__  # type: ignore[attr-defined]
    if not hasattr(obj, "priority"):
        obj.priority = cfg.priority  # type: ignore[attr-defined]
    else:
        # priorité du cfg > priorité interne du plugin
        try:
            if int(cfg.priority) != int(getattr(obj, "priority")):
                obj.priority = cfg.priority  # type: ignore[attr-defined]
        except Exception:
            obj.priority = cfg.priority  # type: ignore[attr-defined]

    if not hasattr(obj, "enabled"):
        obj.enabled = cfg.enabled  # type: ignore[attr-defined]
    else:
        try:
            obj.enabled = bool(cfg.enabled)  # type: ignore[attr-defined]
        except Exception:
            obj.enabled = True  # type: ignore[attr-defined]

    # Validation minimale du protocole
    if not hasattr(obj, "process") or not callable(getattr(obj, "process")):
        raise PluginLoadError(
            f"Le symbole chargé ('{obj}') ne fournit pas une méthode 'process(action, context)'."
        )

    return obj  # type: ignore[return-value]


class PluginManager:
    """Gestionnaire de plugins éthique: chargement, ordre, exécution et rapport.

    Paramètres
    ---------
    strict: si True, relance les exceptions des plugins; sinon, log et continue.
    logger: logger optionnel; sinon utilise 'ethics_integration.plugin_manager'.
    """

    def __init__(self, *, strict: bool = False, logger: Optional[logging.Logger] = None) -> None:
        self.strict = strict
        self.logger = logger or logging.getLogger("ethics_integration.plugin_manager")
        self._plugins: List[Plugin] = []

    # ------------------------ Chargement ---------------------------------- #
    def load_from_default(self, configs: List[PluginConfig]) -> None:
        """Charge une liste de PluginConfig (chemins dotted path)."""
        for cfg in configs:
            self._load_and_register(cfg)

    def load_from_entry_points(self, group: str = "ethics_integration.plugins") -> None:
        """Découvre et charge les plugins via entry points (pyproject.toml)."""
        try:
            eps: List[EntryPoint]
            try:
                # Python 3.12+
                eps = list(entry_points(group=group))  # type: ignore[arg-type]
            except TypeError:
                # Python 3.10/3.11
                eps = list(entry_points().get(group, []))  # type: ignore[assignment]
        except Exception as e:
            raise PluginLoadError(f"Impossible de récupérer les entry points du groupe '{group}': {e}")

        for ep in eps:
            symbol = ep.load()
            plugin = _instantiate_plugin(symbol, PluginConfig(path=ep.value))
            self.register(plugin)

    def _load_and_register(self, cfg: PluginConfig) -> None:
        module_path, attr = _split_dotted_path(cfg.path)
        try:
            symbol = _resolve_symbol(module_path, attr)
            plugin = _instantiate_plugin(symbol, cfg)
        except Exception as e:
            msg = f"Échec chargement plugin '{cfg.path}': {e}"
            if self.strict:
                raise PluginLoadError(msg) from e
            self.logger.exception(msg)
            return
        self.register(plugin)

    def register(self, plugin: Plugin) -> None:
        """Enregistre un plugin en respectant l'ordre de priorité (descendant)."""
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: getattr(p, "priority", 0), reverse=True)

    # ------------------------ Exécution ----------------------------------- #
    def process_action(self, action: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fait passer 'action' à travers le pipeline de plugins activés.

        Retourne l'action transformée, en ajoutant un champ '_plugin_report' décrivant:
          - pipeline: ordre d'exécution (nom/priorité)
          - steps: temps d'exécution, changement détecté, erreur éventuelle
        """
        context = context or {}
        current = copy.deepcopy(action)
        report = {
            "pipeline": [
                {"name": getattr(p, "name", p.__class__.__name__), "priority": getattr(p, "priority", 0)}
                for p in self._plugins if getattr(p, "enabled", True)
            ],
            "steps": [],
        }

        for plugin in self._plugins:
            if not getattr(plugin, "enabled", True):
                continue

            name = getattr(plugin, "name", plugin.__class__.__name__)
            start = time.perf_counter()

            try:
                # Hook optionnel 'before'
                before_hook = getattr(plugin, "before", None)
                if callable(before_hook):
                    before_hook(current, context)

                out = plugin.process(current, context)
                changed = out is not current and out != current
                current = out if isinstance(out, dict) else current

                # Hook optionnel 'after'
                after_hook = getattr(plugin, "after", None)
                if callable(after_hook):
                    after_hook(current, context)

                step = {
                    "plugin": name,
                    "time_ms": round((time.perf_counter() - start) * 1000, 3),
                    "changed": bool(changed),
                    "error": None,
                }
            except Exception as e:
                msg = f"Plugin '{name}' a levé une exception: {e}"
                if self.strict:
                    raise
                self.logger.exception(msg)
                step = {
                    "plugin": name,
                    "time_ms": round((time.perf_counter() - start) * 1000, 3),
                    "changed": False,
                    "error": str(e),
                }
            report["steps"].append(step)

        current.setdefault("_plugin_report", report)
        return current

    # ------------------------ Utilitaires --------------------------------- #
    def list_plugins(self) -> List[Dict[str, Any]]:
        """Donne un aperçu des plugins enregistrés (pour debug/UI)."""
        return [
            {
                "name": getattr(p, "name", p.__class__.__name__),
                "priority": getattr(p, "priority", 0),
                "enabled": getattr(p, "enabled", True),
                "module": p.__class__.__module__,
                "class": p.__class__.__name__,
            }
            for p in self._plugins
        ]

    def enable(self, name: str, *, enabled: bool = True) -> bool:
        """Active/désactive un plugin par son nom. Retourne True si trouvé."""
        for p in self._plugins:
            if getattr(p, "name", p.__class__.__name__) == name:
                setattr(p, "enabled", enabled)
                return True
        return False

    def clear(self) -> None:
        """Désenregistre tous les plugins (reset)."""
        self._plugins.clear()


# ---------------------------- Helpers ------------------------------------- #

def _split_dotted_path(path: str) -> tuple[str, Optional[str]]:
    """Ex: "pkg.module:ClassName" -> ("pkg.module", "ClassName").
         "pkg.module" -> ("pkg.module", None)
    """
    if ":" in path:
        m, a = path.split(":", 1)
        return m.strip(), a.strip() or None
    return path.strip(), None

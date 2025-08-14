# --- auto_loader.py ---
from __future__ import annotations
import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# 1) Contrat minimal attendu pour un plugin
@runtime_checkable
class EthicsPlugin(Protocol):
    name: str  # ex: "GratitudePlugin"
    priority: int  # plus petit = plus prioritaire (0 > 10)
    enabled: bool  # True/False

    def process(self, action: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

# 2) Valeurs par défaut si le plugin n’en fournit pas
def _get_attr(obj: Any, attr: str, default: Any) -> Any:
    return getattr(obj, attr, default)

# 3) Découverte dynamique des classes plugins dans un paquet
def discover_plugins(package_name: str = "julieethics") -> List[type]:
    """
    Cherche toutes les classes dans le paquet `package_name` dont le nom contient 'plugin'
    (insensible à la casse) et qui respectent (au moins) le Protocol EthicsPlugin.
    """
    discovered = []
    try:
        pkg = importlib.import_module(package_name)
    except Exception as e:
        print(f"[ethics] Impossible d'importer le paquet '{package_name}': {e}")
        return discovered

    # Parcourt tous les modules du paquet
    for finder, mod_name, is_pkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        # Heuristique: ne charger que les modules dont le nom contient 'plugin'
        if "plugin" not in mod_name.lower():
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"[ethics] Ignoré (échec import) {mod_name}: {e}")
            continue

        # Récupère les classes publiques du module
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            # Doit être défini dans ce module (évite les imports re-exportés)
            if cls.__module__ != mod.__name__:
                continue

            # Heuristique de nommage: *Plugin*
            if "plugin" not in cls.__name__.lower():
                continue

            # Vérifie le contrat (Protocol) de façon souple
            if not hasattr(cls, "process"):
                continue

            discovered.append(cls)

    return discovered

# 4) Instanciation + normalisation (priority, enabled, name)
def instantiate_plugins(plugin_classes: List[type]) -> List[EthicsPlugin]:
    instances: List[EthicsPlugin] = []
    for cls in plugin_classes:
        try:
            inst = cls()  # suppose un __init__ sans argument
            # Normalise les attributs si absents
            if not hasattr(inst, "name"):
                inst.name = cls.__name__
            if not hasattr(inst, "priority"):
                inst.priority = 100  # défaut: faible priorité
            if not hasattr(inst, "enabled"):
                inst.enabled = True
            # Vérifie le Protocol a minima
            if not isinstance(inst, EthicsPlugin):  # runtime_checkable
                print(f"[ethics] Ignoré (ne respecte pas le protocole) {cls.__name__}")
                continue
            instances.append(inst)
        except Exception as e:
            print(f"[ethics] Ignoré (échec instanciation) {cls.__name__}: {e}")
    return instances

# 5) Pipeline d’application
@dataclass
class PluginPipeline:
    plugins: List[EthicsPlugin]

    def process(self, action: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = dict(action)  # copie défensive
        for p in self.plugins:
            if not _get_attr(p, "enabled", True):
                continue
            try:
                result = p.process(result, context or {})
            except Exception as e:
                print(f"[ethics] Plugin '{_get_attr(p, 'name', p.__class__.__name__)}' ignoré (erreur runtime): {e}")
                continue
        return result

# 6) Fonction utilitaire unique demandée : tout rendre « fonctionnel »
def make_all_plugins_functional(package_name: str = "julieethics",
                                extra_plugins: Optional[List[EthicsPlugin]] = None) -> PluginPipeline:
    """
    - Découvre tous les plugins dans `package_name`
    - Instancie
    - Fusionne avec d'éventuels `extra_plugins`
    - Trie par priorité (ascendant)
    - Retourne un pipeline prêt à l’emploi: pipeline.process(action, context)
    """
    discovered = discover_plugins(package_name)
    instances = instantiate_plugins(discovered)

    if extra_plugins:
        for p in extra_plugins:
            # normalise les attributs au passage
            if not hasattr(p, "name"):
                p.name = p.__class__.__name__
            if not hasattr(p, "priority"):
                p.priority = 100
            if not hasattr(p, "enabled"):
                p.enabled = True
            instances.append(p)

    # Tri par priorité (0 = plus prioritaire)
    instances.sort(key=lambda p: _get_attr(p, "priority", 100))

    names = ", ".join(_get_attr(p, "name", p.__class__.__name__) for p in instances)
    print(f"[ethics] Plugins actifs ({len(instances)}): {names}")
    return PluginPipeline(plugins=instances)

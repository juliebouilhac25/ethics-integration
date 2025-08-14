# ethics-integration
Middleware pour intégrer JulieEthics dans des système IA
Middleware for integration of julieethics in AI environnement

---

# Ethics Integration

**Ethics Integration** est un middleware en Python conçu pour intégrer facilement les lois et plugins éthiques (*JulieEthics*) dans des systèmes d’intelligence artificielle.

L’objectif est de fournir une structure flexible où différentes dimensions éthiques (santé, autonomie collective, gratitude, équilibre, etc.) peuvent être ajoutées sous forme de **plugins**.

---

## 🚀 Installation

Clonez ce dépôt :

```bash
git clone https://github.com/juliebouilhac25/ethics-integration.git
cd ethics-integration
```

Installez les dépendances :

```bash
pip install -r requirements.txt
```

---

## ⚙️ Utilisation

Exemple simple pour charger un plugin et traiter une action :

```python
from julieethics.plugin_manager import PluginManager, PluginConfig
from julieethics.autonomy_collective_plugin import AutonomyCollectivePlugin

# Créer un gestionnaire de plugins
pm = PluginManager()

# Charger un plugin avec priorité
pm.load_from_default([PluginConfig(path="__main__:AutonomyCollectivePlugin", priority=1)])

# Exemple d'action
action = {"type": "decision", "content": "Prendre une décision individuelle", "selfishness": 1.0}

# Traiter l'action avec contexte
result = pm.process_action(action, context={"collaboration_level": 0.3})

print(result)
```

---

## 📦 Plugins disponibles

* **AutonomyCollectivePlugin** : réduit l’égoïsme et valorise la collaboration.
* **HealthyBalancePlugin** : favorise l’équilibre santé.
* **GratitudePlugin** : intègre la reconnaissance dans les décisions.
* **ShareWealthPlugin** : encourage le partage des ressources.

*(d’autres à venir…)*

---

## 📌 Roadmap

* [ ] Ajouter un système de configuration plus souple.
* [ ] Rédiger une documentation complète par plugin.
* [ ] Publier une première release stable.
* [ ] Ajouter des tests unitaires étendus.

---

## 🤝 Contribution

Toute suggestion est la bienvenue ! Vous pouvez ouvrir une *issue* ou proposer une *pull request*.

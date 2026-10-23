# LISA – Linguistic Intelligence for Surveillance & Analysis

**LISA** est une application avancée conçue pour analyser le contenu textuel avant qu’il ne soit envoyé à un modèle de langage (LLM), afin de détecter et prévenir les prompts malveillants. Elle combine intelligence linguistique et techniques d’analyse pour protéger les utilisateurs et les systèmes d’IA.


## Fonctionnalités

* **Analyse linguistique avancée** : LISA inspecte la structure, le style et le contexte des textes pour détecter des patterns suspects.
* **Détection de prompts malveillants** : Identification automatique des tentatives de manipulation, d’injection ou de contenu dangereux.
* **Surveillance en temps réel** : Analyse les textes avant envoi à un LLM pour éviter les risques.

## Déploiement Helm

Le chart se trouve dans [deploy/helm/lisa](./deploy/helm/lisa). Son organisation
reprend le [modèle de this-is-tobi/helm-charts](https://github.com/this-is-tobi/helm-charts/tree/main/template),
avec une factorisation propre à LiSA pour limiter la duplication entre composants.

Le [guide du chart](./deploy/helm/lisa/README.md) explique les valeurs communes,
les overrides par composant, l'installation et l'ajout d'un service.

## Configuration des tests des services

Les sept services partagent [services/pytest.ini](./services/pytest.ini) via un
lien symbolique dans chaque dossier. Modifier ce fichier commun suffit pour
changer leurs options pytest. Les dépendances restent propres à chaque service :
suivre son README pour les installer, puis lancer `pytest` depuis son dossier,
pas depuis la racine du dépôt. Les tests du backend et du package worker gardent
leur configuration distincte.

Le checkout doit préserver les liens symboliques ; sous Windows, cela peut
nécessiter le mode développeur et l'option Git `core.symlinks=true` avant le
checkout.

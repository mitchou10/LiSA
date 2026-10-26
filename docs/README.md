# Page d'analyse pas à pas

La page **Analyse** guide l'utilisateur en quatre étapes : quoi analyser, comment l'analyser, suivre la progression, puis lire les résultats (avec flou et export facultatifs). Le fil d'Ariane en haut de page montre où l'on en est et permet de revenir à une étape déjà passée.

Code : [`frontend/src/pages/AnalysisPage.jsx`](../frontend/src/pages/AnalysisPage.jsx) et [`frontend/src/components/analysis/wizard/`](../frontend/src/components/analysis/wizard/).

## 1. Source : un texte ou un fichier

Deux cartes au choix. La carte sélectionnée s'ouvre et affiche sa zone de saisie.

**Un texte** : on colle ou on saisit le texte (compteur de caractères). Un saut de page (`\f`) coupe le texte en pages.

![Source : texte](screenshots/01-source-texte.png)

**Un fichier** : glisser-déposer ou parcourir. PDF, PNG, JPG, TIFF, BMP, WebP, plusieurs fichiers possibles, chacun retirable.

![Source : fichier](screenshots/02-source-fichier.png)

*Continuer* reste grisé tant qu'il n'y a rien à analyser.

## 2. Analyse : standard, projet existant ou nouveau projet

Trois cartes, la première est recommandée.

**Analyse standard** : informations personnelles et contrôles de sécurité par défaut. Rien à configurer.

![Analyse standard](screenshots/03-analyse-standard.png)

**Un projet existant** : on choisit un projet, puis on active ou désactive chaque définition (entités, relations, classifications, contrôles de sécurité) sous forme de pastilles. Tout ce qui est activé dans le projet est coché au départ.

![Projet existant](screenshots/04-analyse-projet.png)

**En créer un maintenant** : un nom et les labels à chercher (pastilles prêtes à l'emploi, plus un champ pour en ajouter). Le projet et ses entités sont créés au lancement, et réutilisés si on revient en arrière puis relance sans rien changer.

![Création d'un projet à la volée](screenshots/05-analyse-creer.png)

Les **options** sont en bas : anonymiser (rien de lisible en base) et, pour les fichiers, flouter les captures de pages et classer aussi les images.

## 3. Progression

Une barre globale et une ligne par tâche (parsing, entités, relations, classifications, sécurité, images, anonymisation) avec son statut, sa progression et sa durée. Dès que le run est terminé, on passe seul aux résultats. En cas d'erreur, un bouton *Réessayer* apparaît.

![Progression](screenshots/06-progression.png)

## 4. Résultats

Une seule vue, pensée pour qu'il n'y ait rien à apprendre.

**En haut**, une ligne de résumé : pages, entités trouvées, alertes de sécurité, durée. Une bannière rouge apparaît sur les pages où une alerte de sécurité a été levée.

**À gauche**, le document page par page (image ou texte, avec les entités surlignées). **À droite**, ce qui a été trouvé sur la page. Chaque entité est cochée au départ : *cochée = masquée à l'export*. On décoche ce qui doit rester lisible ; *tout* / *rien* agissent sur la page courante. Survoler une ligne ou un surlignage allume l'autre.

![Résultats : document, entités et export](screenshots/07-resultats.png)

**En dessous**, l'export, facultatif : on choisit quoi flouter (les entités cochées, toute la page ou rien), puis on télécharge en **PNG** (page affichée), **ZIP** (une image par page) ou **PDF** (toutes les pages). « Garder les cadres et les labels » dessine les boîtes avec leur label. Si rien n'est coché, l'interface prévient que les pages seront exportées sans modification. On peut aussi ne rien exporter et cliquer sur *Nouvelle analyse*.

![Sélection des entités à flouter](screenshots/08-export-selection.png)

**Tout en bas**, une section repliée *Détail par tâche* donne le résultat brut de chaque tâche (parsing, entités, relations, classifications, sécurité, images), pour qui veut aller plus loin.

![Détail par tâche](screenshots/09-detail-taches.png)

Pour un **texte**, il n'y a pas de capture de page, donc pas de flou à l'export : on garde les surbrillances et le bouton *Masquer le texte*.

![Résultats d'un texte](screenshots/10-resultats-texte.png)

## Travailler sans backend (mocks)

Avec `VITE_USE_MOCKS=true` dans `frontend/.env.local`, tous les appels de l'API sont simulés en mémoire par [`frontend/src/lib/mockBackend.js`](../frontend/src/lib/mockBackend.js) : projets et définitions, runs et tâches (la progression suit l'horloge), captures de pages et export. Un document d'exemple de deux pages (contrat, annexe avec une tentative d'injection) sert de fichier analysé ; les textes saisis sont analysés par des expressions régulières (e-mail, téléphone, IBAN, date, nom). L'export simulé renvoie la page en SVG avec les entités choisies masquées, quel que soit le format demandé.

```bash
cd frontend
npm run dev        # http://localhost:5173, connecté en admin (VITE_BYPASS_AUTH=true)
```

Mettre `VITE_USE_MOCKS=false` (ou retirer la ligne) pour utiliser le vrai backend.

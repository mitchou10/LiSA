from transformers import pipeline
from worker.models.base import BaseInferenceModel

# TODO: gérer la taille de l'input pour ne pas dépasser la limite du modèle (512 tokens pour bart-large-mnli par exemple)
# faire un mean ou bien utiliser un max sur l'ensemble des résultats


class ZeroShotModel(BaseInferenceModel[str, dict]):
    def __init__(self, candidate_labels: list[str]):
        super().__init__("zero-shot-classification")
        self.classifier = pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )
        self.candidate_labels = candidate_labels

    def predict(self, input_data: str) -> dict:
        return self.classifier(
            input_data, candidate_labels=self.candidate_labels, multi_label=True
        )

    def batch_predict(self, input_data_list: list[str]) -> list[dict]:
        return self.classifier(
            input_data_list,
            candidate_labels=self.candidate_labels,
            multi_label=True,
        )


if __name__ == "__main__":
    # Charger le pipeline Zero-Shot
    # Tes catégories (labels)
    labels = ["santé", "finance", "éducation", "cybersécurité"]
    classifier = ZeroShotModel(candidate_labels=labels)

    # Exemple de document
    texte = """
    L’IA générative est de plus en plus utilisée dans le domaine de la santé
    pour assister les médecins et améliorer le diagnostic.
    """

    # Classification zero-shot
    resultat = classifier.predict(texte)
    print(resultat)
    print("Texte :", texte)
    print("\nClassification :")
    for label, score in zip(resultat["labels"], resultat["scores"]):
        print(f"- {label}: {score:.2f}")

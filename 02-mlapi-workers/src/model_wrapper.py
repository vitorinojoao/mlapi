"""model_wrapper"""

import joblib


class ModelWrapper:
    """Object to load and encapsulate an ML model"""

    def __init__(self, model_filepath):
        try:
            self.model = joblib.load(model_filepath)

        except Exception as e:
            raise OSError(
                "Could not load the ML model from the specified filepath"
            ) from e

        if callable(getattr(self.model, "predict", None)):
            self.model_predict = self.model.predict

        elif callable(self.model):
            self.model_predict = self.model

        else:
            raise TypeError(
                "The loaded ML model is not callable and does not have a 'predict' function"
            )

        self.info_features = getattr(self.model, "n_features_in_", "Hidden features")
        self.info_feature_names = list(getattr(self.model, "feature_names_in_", []))

        self.info_classes = getattr(self.model, "n_classes_", "Hidden classes")
        self.info_class_names = list(getattr(self.model, "classes_", []))

    def info(self):
        """Obtain information about the ML model"""

        return (
            self.model.__class__.__name__,
            self.info_features,
            self.info_feature_names,
            self.info_classes,
            self.info_class_names,
        )

    def predict(self, X):
        """Obtain predictions of the ML model"""

        return self.model_predict(X)

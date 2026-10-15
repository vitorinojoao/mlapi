"""model_wrapper"""

import joblib


class ModelWrapper:
    """Object that loads and encapsulates an ML model"""

    def __init__(self, model_filepath):
        try:
            self.model = joblib.load(model_filepath)

        except Exception as e:
            raise OSError("Could not load the ML model from the specified file.") from e

        if callable(getattr(self.model, "predict", None)):
            self.model_predict = self.model.predict

        elif callable(self.model):
            self.model_predict = self.model

        else:
            raise TypeError(
                "Loaded ML model is not callable"
                + " and does not have a 'predict' function."
            )

        self.info_features = getattr(self.model, "n_features_in_", "Hidden features")
        self.info_classes = getattr(self.model, "classes_", "Hidden classes")

    def info(self):
        """Obtain information about an ML model"""

        return self.model.__class__.__name__, self.info_features, self.info_classes

    def predict(self, X):
        """Obtain the predictions of an ML model"""

        return self.model_predict(X)

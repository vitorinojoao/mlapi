import joblib as jb

from mlapi.singleton import Singleton


class ModelWrapper(Singleton):
    """
    Singleton object to encapsulate an ML model.
    """

    def single_init(self, model_filepath):
        """Overridden method to perform a single initialization."""

        try:
            self.model = jb.load(model_filepath)
        except:
            raise OSError("Could not load the ML model.")

    def info(self):
        """Obtain information about an ML model"""

        return self.model.__class__.__name__, self.model.classes_

    def predict(self, X):
        """Obtain the predictions of an ML model"""

        return self.model.predict(X)

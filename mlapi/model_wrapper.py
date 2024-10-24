# MLAPI Template by vitorinojoao

import joblib as jb


class ModelWrapper:
    """
    Object to encapsulate an ML model.
    """

    def __init__(
        self,
        model_filepath,
    ):
        try:
            self.model = jb.load(model_filepath)
        except Exception as e:
            raise OSError("Could not load the ML model from the specified file.") from e

    def info(self):
        """Obtain information about an ML model"""

        return self.model.__class__.__name__, self.model.classes_

    def predict(self, X):
        """Obtain the predictions of an ML model"""

        return self.model.predict(X)


# End of MLAPI Template by vitorinojoao

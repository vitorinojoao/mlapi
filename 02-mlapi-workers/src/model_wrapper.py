"""model_wrapper"""

import joblib
import numpy as np


class ModelWrapper:
    """Object to load and encapsulate an ML model"""

    def __init__(self, model_filepath, class_names=None):
        try:
            self.model = joblib.load(model_filepath)

        except Exception as e:
            raise OSError("Could not load a model from the provided filepath") from e

        if callable(getattr(self.model, "predict", None)):
            self.predict_fn = self.model.predict
            self.predict_name = "by function"

        elif callable(self.model):
            self.predict_fn = self.model
            self.predict_name = "by call"

        else:
            raise TypeError(
                "The loaded model is not supported yet"
                + ". It must be callable or have a 'predict' function"
            )

        ## ----------------------------------------

        if class_names is None:
            self.n_classes = str(getattr(self.model, "n_classes_", "Hidden classes"))
            self.class_names = [
                str(name) for name in getattr(self.model, "classes_", [])
            ]

        else:
            try:
                class_names = [str(name) for name in class_names]

            except Exception as e:
                raise TypeError(
                    "The provided class names list must contain str labels"
                ) from e

            size = len(class_names)

            if int(getattr(self.model, "n_classes_", size)) != size:
                raise ValueError(
                    "The provided class names list must have the same size"
                    + " as the output of the loaded model"
                )

            self.n_classes = str(size)
            self.class_names = class_names

        ## ----------------------------------------

        self.n_features = str(getattr(self.model, "n_features_in_", "Hidden features"))
        self.feature_names = [
            str(name) for name in getattr(self.model, "feature_names_in_", [])
        ]

        ## ----------------------------------------

    def info(self):
        """Obtain information about the ML model"""

        return {
            "model": self.model.__class__.__name__,
            "predict": self.predict_name,
            "n_classes": self.n_classes,
            "class_names": self.class_names,
            "n_features": self.n_features,
            "feature_names": self.feature_names,
        }

    def predict(self, X):
        """Obtain output predictions of the ML model"""

        return self.predict_fn(X)

    def postprocess_class_scores(self, y, n_samples):
        """
        Postprocess binary or multi-class confidence scores.
        For each sample, return class with highest score (or corresponding str label).
        """

        y = np.array(y, copy=False)

        if y.ndim == 0:
            y = y.reshape(-1)

        elif y.ndim > 2 or (y.ndim == 2 and y.shape[0] != n_samples):
            raise TypeError("The model predictions do not have a valid format.")

        ## ----------------------------------------

        if y.ndim != 1:
            if y.shape[1] != 1:
                ## Multiple samples with 2D multiple class scores
                y = y.argmax(axis=1)
                ## Example:
                ## [ [0.6,0.4], [0.51,0.49], [0.3,0.7] ]  ->  [ 0, 0, 1 ]

            elif np.any((y[:, 0] > 0) & (y[:, 0] < 1)):
                ## Multiple samples with 2D binary class score
                y = (y[:, 0] > 0.5).astype(int)
                ## Example:
                ## [ [0.4], [0.5], [0.7] ]  ->  [ 0, 0, 1 ]

            else:
                ## Multiple samples with a 2D class number
                y = y.astype(int).ravel()
                ## Example:
                ## [ [0.0], [0.0], [1.0] ]  ->  [ 0, 0, 1 ]

        elif n_samples == 1 and y.shape[0] != 1:
            ## Single sample with 1D multiple class scores
            y = y.argmax(axis=0)
            ## Example:
            ## [ 0.51, 0.49 ]  ->  [ 0 ]

        elif np.any((y > 0) & (y < 1)):
            ## Multiple samples or single sample with a 1D binary class score
            y = (y > 0.5).astype(int)
            ## Example:
            ## [ 0.4, 0.5, 0.7 ]  ->  [ 0, 0, 1 ]
            ## [ 0.5 ]            ->  [ 0 ]
            ## [ 0.51 ]           ->  [ 1 ]

        else:
            ## Multiple samples or single sample with a 1D class number
            y = y.astype(int).ravel()
            ## Example:
            ## [ 0.0, 0.0, 1.0 ]  ->  [ 0, 0, 1 ]
            ## [ 0.0 ]            ->  [ 0 ]
            ## [ 1.0 ]            ->  [ 1 ]

        ## ----------------------------------------

        if self.class_names:
            return [self.class_names[i] if i in self.class_names else str(i) for i in y]

        return y.tolist()

    def postprocess_anomaly_scores(self, y, n_samples):
        """
        Postprocess inlier/outlier scores in 1/-1 format.
        For each sample, return 0/1 format (or corresponding str label).
        """

        y = np.array(y, copy=False)

        if y.ndim == 0:
            y = y.reshape(-1)

        elif y.ndim > 2 or (y.ndim == 2 and y.shape[0] != n_samples):
            raise TypeError("The model predictions do not have a valid format.")

        ## ----------------------------------------

        if y.ndim != 1:
            ## Multiple samples with 2D anomaly number
            y = (y[:, 0] < 0).astype(int)
            ## Example:
            ## [ [1.0], [1.0], [-1.0] ]  ->  [ 0, 0, 1 ]
            ## [ [0.1], [0.0], [-0.1] ]  ->  [ 0, 0, 1 ]

        else:
            ## Multiple samples or single sample with 1D anomaly number
            y = (y < 0).astype(int)
            ## Example:
            ## [ 1.0, 1.0, -1.0 ]  ->  [ 0, 0, 1 ]
            ## [ 0.1, 0.0, -0.1 ]  ->  [ 0, 0, 1 ]
            ## [ -1.0 ]            ->  [ 1 ]
            ## [ -0.1 ]            ->  [ 1 ]

        ## ----------------------------------------

        if self.class_names:
            return [self.class_names[i] if i in self.class_names else str(i) for i in y]

        return y.tolist()

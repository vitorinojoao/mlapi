import time
import numpy as np

from mlapi.singleton import Singleton


class DataPostprocessor(Singleton):
    """
    Singleton object to postprocess the predictions of an ML model
    so they become a suitable JSON response to a request.
    """

    def single_init(
        self,
        convert_class_scores,
        convert_anomaly_scores,
        logging_level,
        logging_filepath,
    ):
        """Overridden method to perform a single initialization."""

        # Whether the predictions are confidence scores
        # that should be converted to labels
        # (output the label of the class with the highest score)
        self.convert_class_scores = convert_class_scores

        # Whether the predictions are anomaly scores
        # that should be converted to labels
        # (output inliers/outliers from 1/-1 format to 0/1 format)
        self.convert_anomaly_scores = convert_anomaly_scores

        # Logging levels:
        # 0 - Disabled
        # 1 - Simple
        # 2 - Detailed
        self.logging_level = logging_level

        if self.logging_level > 0:
            self.logging_filepath = logging_filepath

            try:
                with open(self.logging_filepath, "a") as f:
                    f.write(
                        "\n" + str(int(time.time())) + "\t|Starting up the server...\n"
                    )
            except Exception:
                raise OSError("Could not write in the specified logging file.")

    def postprocess(self, y, n_samples, client=None):
        """Postprocess the predictions of an ML model."""

        if self.convert_class_scores:
            # Convert confidence score output to labels
            res = class_output_fn(y, n_samples)

        elif self.convert_anomaly_scores:
            # Convert anomaly score output to labels
            res = anomaly_output_fn(y, n_samples)

        else:
            # Leave output as scores
            res = np.array(y, copy=False)

        # Optionally create a log entry
        if self.logging_level > 0:
            if client is None:
                client = "Client"

            logg = f"{str(int(time.time()))}\t|{client}\t|{str(n_samples)} predictions"

            if self.logging_level > 1:
                labels, counts = np.unique(res, return_counts=True)
                logg += "".join(
                    f"\t|{str(c)} of class '{str(l)}'" for c, l in zip(counts, labels)
                )

            try:
                with open(self.logging_filepath, "a") as f:
                    f.write(logg + "\n")
            except Exception:
                pass

        return res.tolist()


def class_output_fn(y, n_samples, class_labels=None):
    """
    Convert class scores to a 1D array of class labels.
    Output the label of the class with the highest score.
    """

    y = np.array(y, copy=False)

    if y.ndim == 0:
        y = y.reshape(-1)

    if (y.ndim == 2 and y.shape[0] != n_samples) or y.ndim > 2:
        raise TypeError("The predictions do not have a valid format.")

    if y.ndim != 1:
        if y.shape[1] != 1:
            # Multiple samples with 2D multiple class scores
            y = y.argmax(axis=1)
            # For instance:
            # [ [0.6,0.4], [0.51,0.49], [0.3,0.7] ]  ->  [ 0, 0, 1 ]

        elif np.any((y[:, 0] > 0) & (y[:, 0] < 1)):
            # Multiple samples with 2D binary class score
            y = (y[:, 0] > 0.5).astype(int)
            # For instance:
            # [ [0.4], [0.5], [0.7] ]  ->  [ 0, 0, 1 ]

        else:
            # Multiple samples with a 2D class number
            y = y.astype(int).ravel()
            # For instance:
            # [ [0.0], [0.0], [1.0] ]  ->  [ 0, 0, 1 ]

    elif n_samples == 1 and y.shape[0] != 1:
        # Single sample with 1D multiple class scores
        y = y.argmax(axis=0)
        # For instance:
        # [ 0.51, 0.49 ]  ->  [ 0 ]

    elif np.any((y > 0) & (y < 1)):
        # Multiple samples or single sample with a 1D binary class score
        y = (y > 0.5).astype(int)
        # For instance:
        # [ 0.4, 0.5, 0.7 ]  ->  [ 0, 0, 1 ]
        # [ 0.5 ]            ->  [ 0 ]
        # [ 0.51 ]           ->  [ 1 ]

    else:
        # Multiple samples or single sample with a 1D class number
        y = y.astype(int).ravel()
        # For instance:
        # [ 0.0, 0.0, 1.0 ]  ->  [ 0, 0, 1 ]
        # [ 0.0 ]            ->  [ 0 ]
        # [ 1.0 ]            ->  [ 1 ]

    if class_labels is not None:
        # Optional conversion to predefined class labels
        for i in range(y.size):
            y[i] = class_labels[y[i]]

    return y


def anomaly_output_fn(y, n_samples, class_labels=None):
    """
    Convert anomaly scores to a 1D numpy array.
    Output inliers/outliers from 1/-1 format to 0/1 format.
    """

    y = np.array(y, copy=False)

    if y.ndim == 0:
        y = y.reshape(-1)

    if (y.ndim == 2 and y.shape[0] != n_samples) or y.ndim > 2:
        raise TypeError("The predictions do not have a valid format.")

    if y.ndim != 1:
        # Multiple samples with 2D anomaly number
        y = (y[:, 0] < 0).astype(int)
        # For instance:
        # [ [1.0], [1.0], [-1.0] ]  ->  [ 0, 0, 1 ]
        # [ [0.1], [0.0], [-0.1] ]  ->  [ 0, 0, 1 ]

    else:
        # Multiple samples or single sample with 1D anomaly number
        y = (y < 0).astype(int)
        # For instance:
        # [ 1.0, 1.0, -1.0 ]  ->  [ 0, 0, 1 ]
        # [ 0.1, 0.0, -0.1 ]  ->  [ 0, 0, 1 ]
        # [ -1.0 ]            ->  [ 1 ]
        # [ -0.1 ]            ->  [ 1 ]

    if class_labels is not None:
        # Optional conversion to predefined class labels
        for i in range(y.size):
            y[i] = class_labels[y[i]]

    return y

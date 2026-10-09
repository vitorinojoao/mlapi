# MLAPI Template by vitorinojoao

import csv
import logging
import numpy as np


class DataPreprocessor:
    """
    Object to preprocess the content of a request
    so it becomes suitable input data for an ML model.
    """

    def __init__(
        self,
        logging_level,
        encoding_filepath=None,
    ):
        # Nested dictionaries containing the encoding of each category
        # of each categorical feature, according to its column position:
        # {  int column: { string category: int encoding }  }
        self.encoding_table = {}

        # Logging levels:
        # 0 - Disabled
        # 10 - Debug
        # 20 - Info
        # 30 - Warning
        # 40 - Error
        # 50 - Critical
        logging_level = int(logging_level)
        self.logging_level = logging_level if logging_level > 0 else 100

        # For instance, for the first and second features, in columns 0 and 1:
        # {  0: { 'TCP': 0, 'UDP': 1, 'OTHER': 2 },
        #    1: { 'REJ': 0, 'RSTR': 1, 'SF': 2, 'S0': 3, 'OTHER': 4 }  }
        if encoding_filepath is not None:
            try:
                with open(encoding_filepath, "r") as f:
                    # Check the csv file header
                    header = f.readline().rstrip("\n").split(",")

                    if (
                        "column" not in header
                        or "category" not in header
                        or "encoding" not in header
                    ):
                        raise TypeError(
                            "The categorical encoding file must have a header specifying"
                            + " 'column', 'category', and 'encoding'."
                        )

                    # Obtain the csv positions of the encodings
                    # Not related to the column positions that will be used
                    csv_positions = (
                        header.index("column"),
                        header.index("category"),
                        header.index("encoding"),
                    )

                    # Load the encoding of each category
                    csvreader = csv.reader(f, delimiter=",", quotechar='"')

                    for row in csvreader:
                        col = int(row[csv_positions[0]])
                        cat = row[csv_positions[1]].lower()
                        enc = int(row[csv_positions[2]])

                        if col in self.encoding_table:
                            self.encoding_table[col][cat] = enc
                        else:
                            self.encoding_table[col] = {cat: enc}

            except TypeError as e:
                raise e

            except Exception as e:
                raise OSError("Could not load the specified categorical encoding file.") from e

    def preprocess(self, content):
        """Preprocess the input data for an ML model"""

        if content is None:
            raise ValueError("The content must not be empty.")

        if not isinstance(content, list) or len(content) == 0:
            raise ValueError(
                "The content must be a list of lists, representing"
                + " a 2D array in the (n_samples, n_features) shape."
            )

        # Convert each category of each categorical feature
        if self.encoding_table:
            res = np.array(
                [
                    [
                        (
                            # Use encoding
                            self.encoding_table[col][sample[col].lower()]
                            # If value is of type string
                            if isinstance(sample[col], str)
                            # And column position is in encoding table
                            and col in self.encoding_table
                            # And string has an encoding
                            and sample[col].lower() in self.encoding_table[col]
                            # Otherwise, use value
                            else sample[col]
                        )
                        for col in range(len(sample))
                    ]
                    for sample in content
                ]
            )

        else:
            res = np.array(content)

        # Optionally create a log entry
        if self.logging_level < 21:
            logging.info(f"API: Received {str(res.shape[0])} data samples")

        return res, res.shape[0]


# End of MLAPI Template by vitorinojoao

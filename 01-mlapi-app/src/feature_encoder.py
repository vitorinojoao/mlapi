"""feature_encoder"""

import csv
import numpy as np


class FeatureEncoder:
    """Object to preprocess and encode categorical features"""

    def __init__(self, encoding_filepath):
        ## Nested dictionaries containing the encoding of each category
        ## of each categorical feature, according to its column position:
        ## {  int column: { string category: int encoding }  }
        self.encoding_table = {}

        ## For instance, for the first and second features, in columns 0 and 1:
        ## {  0: { 'TCP': 0, 'UDP': 1, 'OTHER': 2 },
        ##    1: { 'REJ': 0, 'RSTR': 1, 'SF': 2, 'S0': 3, 'OTHER': 4 }  }
        try:
            with open(encoding_filepath, "r") as f:
                ## Verify the CSV file header
                header = f.readline().rstrip("\n").split(",")

                if (
                    "column" not in header
                    or "category" not in header
                    or "encoding" not in header
                ):
                    raise TypeError(
                        "The Encoder requires the loaded CSV file to contain a header"
                        + " specifying 'column', 'category', and 'encoding'"
                    )

                ## Obtain the csv positions of the encodings
                ## Not related to the column positions that will be used
                csv_positions = (
                    header.index("column"),
                    header.index("category"),
                    header.index("encoding"),
                )

                ## Load the encoding of each category
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
            raise OSError(
                f"The Encoder could not load feature encodings from a CSV file at {encoding_filepath}"
            ) from e

    ## ----------------------------------------

    def preprocess(self, content, create_array=False):
        """Preprocess input data samples with categorical features"""

        if content is None:
            raise ValueError("The content must not be empty.")

        if not isinstance(content, list) or len(content) == 0:
            raise ValueError(
                "The content must be a 'list of lists', representing"
                + " a 2D array in the (n_samples, n_features) shape."
            )

        ## Convert each category of each categorical feature
        samples = [
            [
                (
                    ## Use encoding
                    self.encoding_table[feat][samp[feat].lower()]
                    ## If value is of type string
                    if isinstance(samp[feat], str)
                    ## And feature position is in encoding table
                    and feat in self.encoding_table
                    ## And string has an encoding
                    and samp[feat].lower() in self.encoding_table[feat]
                    ## Otherwise, use value
                    else samp[feat]
                )
                for feat in range(len(samp))
            ]
            for samp in content
        ]

        if create_array:
            samples = np.array(samples)
            return samples, samples.shape[0]

        return samples, len(samples)

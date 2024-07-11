# MLAPI Template by vitorinojoao


class Singleton:
    """
    Superclass for singleton objects.
    Note: it is necessary to override "single_init"
    instead of "__init__" in all subclasses.
    """

    def __new__(cls, *args, **kwds):
        """
        Method that enforces a single instance
        of each subclass.
        """

        it = cls.__dict__.get("__it__")

        if it is not None:
            return it

        cls.__it__ = it = object.__new__(cls)

        it.single_init(*args, **kwds)

        return it

    def single_init(self, *args, **kwds):
        """
        Method that must be overridden
        to perform a single initialization.
        """
        pass


# End of MLAPI Template by vitorinojoao

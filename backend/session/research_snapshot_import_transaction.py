class ResearchSnapshotImportTransaction:
    """
    Coordinates rollback-safe mutations across
    research domain stores.
    """

    def __init__(

        self,

        stores,

    ):

        self.stores = list(
            stores
        )

        self.snapshots = []

        self.active = False

    def begin(self):

        if self.active:

            raise RuntimeError(

                "Import transaction "
                "is already active."
            )

        self.snapshots = [

            (
                store,

                store.export_state(),
            )

            for store

            in self.stores
        ]

        self.active = True

    def commit(self):

        if not self.active:

            raise RuntimeError(

                "No active import "
                "transaction."
            )

        self.snapshots = []

        self.active = False

    def rollback(self):

        if not self.active:

            return

        errors = []

        for (
            store,
            state,

        ) in reversed(
            self.snapshots
        ):

            try:

                store.restore_state(
                    state
                )

            except Exception as error:

                errors.append(
                    error
                )

        self.snapshots = []

        self.active = False

        if errors:

            raise RuntimeError(

                "Research import rollback "
                "encountered one or more "
                "store restoration "
                "failures."
            ) from errors[0]

    def __enter__(self):

        self.begin()

        return self

    def __exit__(

        self,

        exc_type,

        exc_value,

        traceback,

    ):

        if exc_type is None:

            self.commit()

            return False

        self.rollback()

        return False

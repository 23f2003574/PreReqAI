from uuid import (
    uuid4,
)

from .research_workspace_subscription import (
    ResearchWorkspaceSubscription,
)


class ResearchWorkspaceEventBus:
    """
    Provides transport-agnostic in-process
    publication and subscription for
    workspace change events.
    """

    def __init__(self):

        self._subscriptions = {}

    def subscribe(

        self,

        callback,

        entity_types=None,

        operations=None,

    ):

        subscription = (

            ResearchWorkspaceSubscription(

                subscription_id=(

                    str(
                        uuid4()
                    )
                ),

                callback=(
                    callback
                ),

                entity_types=(

                    set(
                        entity_types
                        or []
                    )
                ),

                operations=(

                    set(
                        operations
                        or []
                    )
                ),
            )
        )

        self._subscriptions[

            subscription.subscription_id

        ] = subscription

        return subscription

    def unsubscribe(

        self,

        subscription_id,

    ):

        subscription = (

            self._subscriptions
            .pop(

                subscription_id,

                None,
            )
        )

        if subscription is None:

            return False

        subscription.active = False

        return True

    def publish(

        self,

        event,

    ):

        errors = []

        for subscription in list(

            self._subscriptions
            .values()

        ):

            if not subscription.matches(
                event
            ):

                continue

            try:

                subscription.callback(
                    event
                )

            except Exception as error:

                errors.append(

                    (
                        subscription
                        .subscription_id,

                        error,
                    )
                )

        return errors

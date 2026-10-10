from backend.interaction import (
    ObjectAction,
)

from .learning_content import (
    LearningContent,
)

from .learning_content_type import (
    LearningContentType,
)


class ContextualLearningPanel:
    """
    Manages educational content generated
    from research object interactions.
    """

    ACTION_CONTENT_TYPES = {

        ObjectAction.EXPLAIN:
            LearningContentType.EXPLANATION,

        ObjectAction.VISUALIZE:
            LearningContentType.VISUALIZATION,

        ObjectAction.IMPLEMENT:
            LearningContentType.IMPLEMENTATION,

        ObjectAction.COMPARE:
            LearningContentType.COMPARISON,

        ObjectAction.QUIZ:
            LearningContentType.QUIZ,

        ObjectAction.SHOW_PREREQUISITES:
            LearningContentType.PREREQUISITE,

        ObjectAction.SHOW_RELATIONS:
            LearningContentType.FOLLOW_UP,
    }

    def __init__(self):

        self.active_content = None

        self.content_history: list[
            LearningContent
        ] = []

    def present(

        self,

        content: LearningContent,

    ):

        self.active_content = content

        self.content_history.append(
            content
        )

        return content

    def present_response(

        self,

        research_object,

        action,

        response,

    ):

        content_type = (

            self._content_type_for(
                action
            )
        )

        body = self._extract_body(
            response
        )

        workflow = self._extract_workflow(
            response
        )

        content = LearningContent(

            id=(

                f"{research_object.id}:"
                f"{action.value}:"
                f"{len(self.content_history) + 1}"
            ),

            title=(

                f"{research_object.title} — "
                f"{action.value.replace('_', ' ').title()}"
            ),

            content_type=content_type,

            body=body,

            object_id=(
                research_object.id
            ),

            action=action.value,

            workflow=workflow,

            metadata={

                "object_title":
                    research_object.title,

                "object_type": (

                    research_object
                    .object_type
                    .value
                ),
            },
        )

        return self.present(
            content
        )

    @classmethod
    def _content_type_for(cls, action):

        return cls.ACTION_CONTENT_TYPES.get(

            action,

            LearningContentType.GENERAL,
        )

    def restore_artifact(

        self,

        artifact,

    ):

        content = (

            self._build_artifact_content(

                artifact
            )
        )

        self.active_content = (
            content
        )

        if not any(

            existing.metadata.get(
                "artifact_id"
            )

            == artifact.id

            for existing

            in self.content_history
        ):

            self.content_history.append(
                content
            )

        return content

    @staticmethod
    def _content_type_for_artifact(
        artifact,
    ):

        try:

            return LearningContentType(

                artifact
                .artifact_type
                .value
            )

        except ValueError:

            return (
                LearningContentType
                .GENERAL
            )

    def _build_artifact_content(

        self,

        artifact,

    ):

        action = (

            artifact.action

            or artifact
            .artifact_type
            .value
        )

        title = (

            artifact.title

            or (

                f"{artifact.object_id} — "
                f"{action.replace('_', ' ').title()}"
            )
        )

        return LearningContent(

            id=(
                f"artifact:{artifact.id}"
            ),

            title=title,

            content_type=(

                self._content_type_for_artifact(
                    artifact
                )
            ),

            body=(
                artifact.content
            ),

            object_id=(
                artifact.object_id
            ),

            action=action,

            metadata={

                **artifact.metadata,

                "artifact_id":
                    artifact.id,

                "artifact_type": (

                    artifact
                    .artifact_type
                    .value
                ),

                "artifact_version":
                    artifact.version,

                "restored": True,

                "content_type":
                    artifact.content_type,
            },
        )

    @staticmethod
    def _get(obj, key):
        """
        Reads `key` from a dict or an
        attribute from an object, since
        interaction results may arrive as
        either (real backend responses are
        dataclasses; hand-built responses
        in tests are often plain dicts).
        """

        if obj is None:

            return None

        if isinstance(obj, dict):

            return obj.get(key)

        return getattr(
            obj,
            key,
            None,
        )

    @classmethod
    def _extract_body(cls, response):

        if not isinstance(
            response,
            dict,
        ):

            return response

        interaction = response.get(
            "interaction"
        )

        inner_response = cls._get(

            interaction,

            "response",
        )

        if inner_response is not None:

            answer = cls._get(

                inner_response,

                "answer",
            )

            return (

                answer

                if answer is not None

                else inner_response
            )

        for key in (

            "content",

            "response",

            "result",

            "output",
        ):

            value = cls._get(

                interaction,

                key,
            )

            if value is not None:

                return value

        for key in (

            "content",

            "response",

            "result",

            "output",
        ):

            if key in response:

                return response[key]

        return response

    @classmethod
    def _extract_workflow(cls, response):

        if not isinstance(
            response,
            dict,
        ):

            return None

        interaction = response.get(
            "interaction"
        )

        workflow = cls._get(

            interaction,

            "workflow",
        )

        if workflow is not None:

            return workflow

        return response.get(
            "workflow"
        )

    def clear(self):

        self.active_content = None

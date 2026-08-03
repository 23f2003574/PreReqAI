import ast

from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError,
)

VALID_CONDITION_FAILURE_ACTIONS = (
    "fail",
    "block",
    "skip",
)

_ALLOWED_COMPARE_OPS = (
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
)

_ALLOWED_BOOL_OPS = (
    ast.And,
    ast.Or,
)

_ALLOWED_UNARY_OPS = (
    ast.Not,
    ast.USub,
    ast.UAdd,
)


def _validate_expression_syntax(expression: str, error_cls) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise error_cls(
            f"Invalid condition expression {expression!r}: {error.msg}."
        ) from error

    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load)):
            continue

        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, _ALLOWED_BOOL_OPS):
                raise error_cls(
                    f"Invalid condition expression {expression!r}: unsupported boolean operator."
                )

            continue

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARY_OPS):
                raise error_cls(
                    f"Invalid condition expression {expression!r}: unsupported unary operator."
                )

            continue

        if isinstance(node, ast.Compare):
            for op in node.ops:
                if not isinstance(op, _ALLOWED_COMPARE_OPS):
                    raise error_cls(
                        f"Invalid condition expression {expression!r}: unsupported comparison operator."
                    )

            continue

        if isinstance(node, (ast.Name, ast.Constant, ast.List, ast.Tuple)):
            continue

        if isinstance(node, (ast.boolop, ast.unaryop, ast.cmpop)):
            # The operator itself was already checked against the allowed
            # sets above, via its parent BoolOp/UnaryOp/Compare node.
            continue

        raise error_cls(
            f"Invalid condition expression {expression!r}: unsupported syntax {type(node).__name__!r}."
        )

    return tree


def evaluate_condition_expression(expression: str, context, error_cls) -> bool:
    """
    Safely evaluate a pipeline condition's expression against a
    context mapping.

    Only boolean operators, comparisons, literals, and name lookups
    are supported. The expression's syntax tree is validated before
    any evaluation is attempted, so it can never execute arbitrary
    code.

    Raises:
        error_cls: If the expression is syntactically invalid or
            uses unsupported syntax, or if it references a name
            absent from context
    """

    tree = _validate_expression_syntax(expression, error_cls)

    try:
        return bool(eval(compile(tree, "<condition>", "eval"), {"__builtins__": {}}, dict(context)))
    except NameError as error:
        raise error_cls(
            f"Cannot evaluate condition expression {expression!r}: {error}."
        ) from error


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition:
    """
    Immutable definition of a runtime precondition a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace pipeline stage must
    satisfy before it may run.

    The condition is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a pipeline gate service.

    Attributes:
        condition_id: The condition's unique identifier
        stage_id: The identifier of the stage the condition guards
        expression: A boolean expression evaluated against a runtime
            context; supports boolean operators, comparisons,
            literals, and name lookups only
        failure_action: What happens when the expression evaluates
            false: "fail" stops the pipeline, "block" withholds the
            stage without failing the pipeline, "skip" ignores the
            failure and lets the stage proceed
    """

    condition_id: str

    stage_id: str

    expression: str

    failure_action: str

    def __post_init__(self):
        if self.condition_id is None or not self.condition_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline condition with an empty or blank condition ID."
            )

        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline condition with an empty or blank stage ID."
            )

        if self.expression is None or not self.expression.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline condition with an empty or blank expression."
            )

        _validate_expression_syntax(self.expression, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError)

        if self.failure_action not in VALID_CONDITION_FAILURE_ACTIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                f"Invalid pipeline condition failure action {self.failure_action!r}. "
                f"Must be one of {VALID_CONDITION_FAILURE_ACTIONS!r}."
            )

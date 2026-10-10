from .research_workspace_consumer_contract_compatibility import (
    ResearchWorkspaceConsumerContractCompatibility,
)

from .research_workspace_consumer_contract_descriptor import (
    ResearchWorkspaceConsumerContractDescriptor,
)

from .research_workspace_consumer_contract_id import (
    ResearchWorkspaceConsumerContractId,
)

from .research_workspace_consumer_contract_parameter import (
    ResearchWorkspaceConsumerContractParameter,
)

from .research_workspace_consumer_contract_parameter_type import (
    ResearchWorkspaceConsumerContractParameterType,
)

from .research_workspace_consumer_contract_scope import (
    ResearchWorkspaceConsumerContractScope,
)

from .research_workspace_consumer_contract_stability import (
    ResearchWorkspaceConsumerContractStability,
)

from .research_workspace_consumer_contract_version import (
    ResearchWorkspaceConsumerContractVersion,
)


DEFAULT_RESEARCH_WORKSPACE_CONTRACTS = (

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .WORKSPACE_CAPABILITIES
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .WORKSPACE
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Describes the research workspace "
            "capabilities supported by the "
            "current backend."
        ),

        projection_name=(
            "ResearchWorkspaceCapabilityDescriptor"
        ),

        read_only=True,

        parameters=[],

        required_capabilities=[],
    ),

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .WORKSPACE_READINESS
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .WORKSPACE
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Assesses whether the research "
            "workspace is ready, degraded, "
            "or unavailable."
        ),

        projection_name=(
            "ResearchWorkspaceReadinessAssessment"
        ),

        read_only=True,

        parameters=[],

        required_capabilities=[],
    ),

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .WORKSPACE_BOOTSTRAP
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .WORKSPACE
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Assembles the bounded initial "
            "workspace context a consumer "
            "needs at startup."
        ),

        projection_name=(
            "ResearchWorkspaceBootstrapProjection"
        ),

        read_only=True,

        parameters=[

            ResearchWorkspaceConsumerContractParameter(

                name="recent_session_limit",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .INTEGER
                ),

                description=(
                    "Bounds how many recently "
                    "updated sessions are "
                    "included."
                ),
            ),

            ResearchWorkspaceConsumerContractParameter(

                name="recent_activity_limit",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .INTEGER
                ),

                description=(
                    "Bounds how many recent "
                    "activity events are "
                    "included."
                ),
            ),
        ],

        required_capabilities=[],
    ),

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .WORKSPACE_ATTENTION
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .WORKSPACE
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Projects current workspace "
            "conditions that may require "
            "attention."
        ),

        projection_name=(
            "ResearchWorkspaceAttentionProjection"
        ),

        read_only=True,

        parameters=[

            ResearchWorkspaceConsumerContractParameter(

                name="category",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .ENUM
                ),

                description=(
                    "Filter attention items by "
                    "category."
                ),
            ),

            ResearchWorkspaceConsumerContractParameter(

                name="minimum_severity",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .ENUM
                ),

                description=(
                    "Return only attention items "
                    "at or above the requested "
                    "severity."
                ),
            ),

            ResearchWorkspaceConsumerContractParameter(

                name="actionable_only",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .BOOLEAN
                ),

                description=(
                    "Return only actionable "
                    "attention items."
                ),
            ),

            ResearchWorkspaceConsumerContractParameter(

                name="limit",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .INTEGER
                ),

                description=(
                    "Limit the number of "
                    "returned attention items."
                ),
            ),
        ],

        required_capabilities=[],
    ),

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .WORKSPACE_ACTIONS
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .WORKSPACE
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Projects which workspace-level "
            "actions are currently available."
        ),

        projection_name=(
            "ResearchWorkspaceActionProjection"
        ),

        read_only=True,

        parameters=[

            ResearchWorkspaceConsumerContractParameter(

                name="include_unavailable",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .BOOLEAN
                ),

                description=(
                    "Include unavailable actions "
                    "alongside their reasons."
                ),
            ),
        ],

        required_capabilities=[],
    ),

    ResearchWorkspaceConsumerContractDescriptor(

        contract_id=(
            ResearchWorkspaceConsumerContractId
            .SESSION_ACTIONS
        ),

        version=(
            ResearchWorkspaceConsumerContractVersion(
                major=1,

                minor=0,
            )
        ),

        scope=(
            ResearchWorkspaceConsumerContractScope
            .SESSION
        ),

        stability=(
            ResearchWorkspaceConsumerContractStability
            .STABLE
        ),

        description=(
            "Projects which actions are "
            "currently available for a "
            "specific research session."
        ),

        projection_name=(
            "ResearchWorkspaceActionProjection"
        ),

        read_only=True,

        parameters=[

            ResearchWorkspaceConsumerContractParameter(

                name="session_id",

                required=True,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .ENTITY_ID
                ),

                description=(
                    "Identifies the research "
                    "session to evaluate."
                ),
            ),

            ResearchWorkspaceConsumerContractParameter(

                name="include_unavailable",

                required=False,

                value_type=(
                    ResearchWorkspaceConsumerContractParameterType
                    .BOOLEAN
                ),

                description=(
                    "Include unavailable actions "
                    "alongside their reasons."
                ),
            ),
        ],

        required_capabilities=[],
    ),
)


class ResearchWorkspaceConsumerContractRegistry:
    """
    Owns the authoritative set of consumer
    contract descriptors exposed by the
    research workspace.
    """

    def __init__(

        self,

        contracts=None,

    ):

        contracts = (

            contracts

            or DEFAULT_RESEARCH_WORKSPACE_CONTRACTS
        )

        self._validate(
            contracts
        )

        self._contracts = {

            descriptor.contract_id.value:
                descriptor

            for descriptor

            in contracts
        }

        self._order = [

            descriptor.contract_id.value

            for descriptor

            in contracts
        ]

    @staticmethod
    def _validate(

        contracts,

    ):

        seen_ids = set()

        for descriptor in contracts:

            contract_id = (
                descriptor.contract_id.value
            )

            if contract_id in seen_ids:

                raise ValueError(

                    "Duplicate consumer "
                    f"contract id: {contract_id}"
                )

            seen_ids.add(
                contract_id
            )

            seen_parameter_names = set()

            for parameter in (
                descriptor.parameters
            ):

                if (

                    parameter.name

                    in seen_parameter_names
                ):

                    raise ValueError(

                        "Duplicate parameter "
                        f"name '{parameter.name}' "
                        f"in contract {contract_id}"
                    )

                seen_parameter_names.add(
                    parameter.name
                )

    def list_contracts(self):

        return [

            self._contracts[
                contract_id
            ]

            for contract_id

            in self._order
        ]

    def get_contract(

        self,

        contract_id,

    ):

        if isinstance(

            contract_id,

            ResearchWorkspaceConsumerContractId,
        ):

            contract_id = (
                contract_id.value
            )

        return (

            self._contracts
            .get(
                contract_id
            )
        )

    def list_by_scope(

        self,

        scope,

    ):

        if isinstance(

            scope,

            ResearchWorkspaceConsumerContractScope,
        ):

            scope = scope.value

        return [

            descriptor

            for descriptor

            in self.list_contracts()

            if (

                descriptor.scope.value

                == scope
            )
        ]

    def list_by_stability(

        self,

        stability,

    ):

        if isinstance(

            stability,

            ResearchWorkspaceConsumerContractStability,
        ):

            stability = stability.value

        return [

            descriptor

            for descriptor

            in self.list_contracts()

            if (

                descriptor.stability.value

                == stability
            )
        ]

    def check_compatibility(

        self,

        contract_id,

        requested_version,

    ):

        normalized_id = (

            contract_id.value

            if isinstance(

                contract_id,

                ResearchWorkspaceConsumerContractId,
            )

            else contract_id
        )

        descriptor = (

            self.get_contract(
                contract_id
            )
        )

        if descriptor is None:

            return (

                ResearchWorkspaceConsumerContractCompatibility(

                    contract_id=(
                        normalized_id
                    ),

                    requested_version=(
                        requested_version
                    ),

                    available_version=None,

                    compatible=False,

                    reason=(
                        "The requested consumer "
                        "contract is not supported."
                    ),
                )
            )

        available_version = (
            descriptor.version
        )

        same_major = (

            available_version.major

            == requested_version.major
        )

        newer_or_equal_minor = (

            available_version.minor

            >= requested_version.minor
        )

        compatible = (

            same_major

            and newer_or_equal_minor
        )

        reason = None

        if not compatible:

            if not same_major:

                reason = (
                    "The available contract "
                    "version is a different "
                    "major version."
                )

            else:

                reason = (
                    "The available contract "
                    "version is older than the "
                    "requested compatible "
                    "version."
                )

        return (

            ResearchWorkspaceConsumerContractCompatibility(

                contract_id=normalized_id,

                requested_version=(
                    requested_version
                ),

                available_version=(
                    available_version
                ),

                compatible=compatible,

                reason=reason,
            )
        )

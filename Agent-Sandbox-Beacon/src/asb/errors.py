class ASBError(RuntimeError):
    """Base exception for Agent Sandbox Beacon failures."""


class SandboxEscapeError(ASBError):
    pass


class BeaconMismatchError(ASBError):
    pass


class BeaconExpiredError(ASBError):
    pass


class StaleSequenceError(ASBError):
    pass


class SessionMismatchError(ASBError):
    pass


class IllegalTransitionError(ASBError):
    pass


class PolicyDeniedError(ASBError):
    pass


class BeaconTamperError(ASBError):
    pass


class BeaconDivergenceError(ASBError):
    pass


class TransitionConflictError(ASBError):
    pass

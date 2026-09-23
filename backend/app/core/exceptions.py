class ApplicationError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProfileNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("PROFILE_NOT_FOUND", "Profile was not found", 404)


class ScenarioNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("SCENARIO_NOT_FOUND", "Active scenario was not found", 404)


class RouteNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("ROUTE_NOT_FOUND", "Route was not found", 404)


class RouteStepNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("ROUTE_STEP_NOT_FOUND", "Route step was not found", 404)


class UnknownUniversityError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "UNKNOWN_UNIVERSITY", "University was not found in the selected region", 422
        )


class InvalidOperationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_OPERATION", message, 409)


class UnauthorizedError(ApplicationError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHORIZED", message, 401)


class AuthUnavailableError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("AUTH_UNAVAILABLE", message, 503)


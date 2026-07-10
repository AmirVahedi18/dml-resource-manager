"""Maps the services layer's plain-Exception error types to HTTP responses in one place, so routers
stay thin (call a service function, let FastAPI's exception handling do the rest) instead of each
one repeating its own try/except HTTPException translation."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dml_core.services.auth_service import InvalidCredentialsError, UsernameAlreadyExistsError
from dml_core.services.reservation_service import ReservationError
from dml_core.services.server_service import GPUIndexConflictError, ServerAlreadyExistsError
from dml_core.services.user_service import UserAlreadyExistsError


def _handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidCredentialsError, _handler(401))
    app.add_exception_handler(UsernameAlreadyExistsError, _handler(409))
    app.add_exception_handler(UserAlreadyExistsError, _handler(409))
    app.add_exception_handler(ServerAlreadyExistsError, _handler(409))
    app.add_exception_handler(GPUIndexConflictError, _handler(409))
    # Covers every reservation-rule violation (slot alignment, RAM/duration/booking-horizon limits,
    # capacity, concurrent-GPU conflict, active-reservation cap, cancellation cutoff) -- one base
    # class, one handler, matching how reservation_service raises a specific subclass per rule.
    app.add_exception_handler(ReservationError, _handler(422))
    app.add_exception_handler(ValueError, _handler(422))

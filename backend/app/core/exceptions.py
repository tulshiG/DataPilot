from fastapi import HTTPException, status

class CredentialsException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

class NotFoundException(HTTPException):
    def __init__(self, name: str):
        super().__init__(status_code=404, detail=f"{name} not found")

class BadRequestException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)
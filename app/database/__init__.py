# Import models so metadata is registered before create_all runs.
from app.database import models

__all__ = ["models"]

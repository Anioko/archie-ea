from sqlalchemy.ext.mutable import MutableDict

from .. import db  # main SQLAlchemy object

# Import GenerationPipeline from models.py to avoid duplication
from .models import GenerationPipeline

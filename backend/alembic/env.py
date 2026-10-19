from alembic import context
from app.core import Base, engine
from app import models  # noqa: F401

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        render_as_batch=engine.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()

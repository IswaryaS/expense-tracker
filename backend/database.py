from sqlmodel import Session, SQLModel, create_engine

# --------------------------------------------------------------
#  SQLite DB (for the prototype)
# --------------------------------------------------------------
sqlite_file = "expense_tracker.db"
sqlite_url = f"sqlite:///{sqlite_file}"
engine = create_engine(sqlite_url, echo=False)


def get_engine() -> "Engine":
    """
    Returns a SQLAlchemy engine. If the DB file does not exist yet we
    create the file *and* the tables.
    """

    SQLModel.metadata.create_all(engine)

    return engine


# --------------------------------------------------------------
#  Dependency – new Session per request
# --------------------------------------------------------------


def get_session():
    with Session(get_engine()) as session:
        yield session

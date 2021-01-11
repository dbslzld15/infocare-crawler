import sqlalchemy as sa
import typing

from sqlalchemy import orm
from loan_model.models.base import Model as LoanModel


def create_session_factory(
    config: typing.Dict[str, typing.Any]
) -> orm.session:
    db_uri = config["SQLALCHEMY_DATABASE_URI"]
    db_engine = sa.create_engine(db_uri)
    session_factory = orm.sessionmaker(bind=db_engine)
    return session_factory


def init_loan_db_schema(session: orm.Session):
    LoanModel.metadata.drop_all(session.bind)
    LoanModel.metadata.create_all(session.bind)

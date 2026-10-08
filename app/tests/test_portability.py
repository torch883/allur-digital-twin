from sqlalchemy import create_mock_engine
from app.db import Base

def test_postgresql_schema_compiles():
    statements=[]
    def capture(sql,*multiparams,**params):statements.append(str(sql.compile(dialect=engine.dialect)))
    engine=create_mock_engine('postgresql+psycopg://',capture)
    Base.metadata.create_all(engine)
    assert len(statements)>=12
    assert any('CREATE TABLE production_records' in s for s in statements)
    assert any('CREATE TABLE plant_snapshots' in s and 'JSON' in s for s in statements)

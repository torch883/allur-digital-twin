import pytest
from sqlalchemy.orm import sessionmaker
from app.db import make_engine,Base,get_db
from app.seed.seed import seed

@pytest.fixture
def db(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'test.db'))
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as session:
        seed(session)
        yield session
    engine.dispose()

@pytest.fixture
def client(db,monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    factory=sessionmaker(bind=db.bind,expire_on_commit=False)
    monkeypatch.setattr(main,'engine',db.bind)
    monkeypatch.setattr(main,'SessionLocal',factory)
    def dependency():
        with factory() as session:yield session
    main.app.dependency_overrides[get_db]=dependency
    with TestClient(main.app) as c:
        main.app.state.simulator.enabled=False
        yield c
    main.app.dependency_overrides.clear()

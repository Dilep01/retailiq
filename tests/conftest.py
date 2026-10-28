import pytest
from django.contrib.auth import get_user_model
from retailiq.services.data import seed_demo


@pytest.fixture
def dataset(db):
    return seed_demo(seed=123, days=240, count=3)


@pytest.fixture
def planner(client, db):
    user = get_user_model().objects.create_user("tester", password="test-only-password")
    client.force_login(user)
    return client

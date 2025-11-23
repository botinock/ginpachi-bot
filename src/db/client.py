from os import getenv

from google.cloud.firestore import AsyncClient


def get_db_client() -> AsyncClient:
    project_id = getenv("FIRESTORE_PROJECT_ID")
    database_id = getenv("FIRESTORE_DATABASE_ID")
    db_client = AsyncClient(
        project=project_id,
        database=database_id
    )
    return db_client
from main.project_settings import BASE_DIR


def read_graphql(path_file: str) -> str:
    """Reads a `.graphql` script's contents from `path_file` (a path
    relative to the project root, e.g. "tests/graphql/mutations/login.graphql"),
    so test files stop embedding GraphQL documents as inline strings."""
    return (BASE_DIR / path_file).read_text()

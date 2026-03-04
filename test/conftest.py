import os
import tempfile

from src.ramose import APIManager


def execute_operation(api_manager: APIManager, operation_url: str) -> str:
    op = api_manager.get_op(operation_url)
    if isinstance(op, tuple):
        raise ValueError(f"Operation not found: {operation_url}")
    _, result, _ = op.exec(method="get", content_type="application/json")
    return result


def create_api_manager(
    config_path: str,
    replacements: dict[str, str],
    env_vars: dict[str, str] | None = None,
) -> APIManager:
    test_dir = os.path.dirname(os.path.abspath(__file__))
    full_config_path = os.path.join(test_dir, "..", config_path)

    with open(full_config_path, "r", encoding="utf8") as f:
        config_content = f.read()

    for old, new in replacements.items():
        config_content = config_content.replace(old, new)

    if env_vars:
        for key, value in env_vars.items():
            os.environ[key] = value

    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".hf", delete=False, dir=test_dir
    )
    tmp_file.write(config_content)
    tmp_file.close()

    try:
        return APIManager([tmp_file.name])
    finally:
        os.unlink(tmp_file.name)

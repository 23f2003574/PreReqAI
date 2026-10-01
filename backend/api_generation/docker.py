ASGI_SERVER = "uvicorn"  # the ASGI server already listed in the project's requirements.txt
BASE_IMAGE = "python:3.11-slim"  # the interpreter line the project is developed and tested on
DEFAULT_PORT = 8000


class InvalidDockerInputError(ValueError):
    """Raised when the generated files cannot be containerised as generated."""


def generate_dockerfile(files: dict, base_image: str = BASE_IMAGE, port: int = DEFAULT_PORT) -> str:
    """Dockerfile for a generated application: installs only the generated
    requirements.txt, copies the generated `app` package and serves
    `app.main:app` with the ASGI server. The listen address is taken from the
    HOST and PORT environment variables at run time (defaults 0.0.0.0 and
    `port`), and nothing depends on the machine that generated it."""
    for required in ("requirements.txt", "app/main.py"):
        if required not in files:
            raise InvalidDockerInputError(f"generated files lack {required}")
    if not any(line.split(">")[0].split("=")[0].strip() == ASGI_SERVER for line in files["requirements.txt"].splitlines()):
        raise InvalidDockerInputError(f"requirements.txt must list {ASGI_SERVER}, which the start command runs")
    return "\n".join(
        [
            f"FROM {base_image}",
            "WORKDIR /srv/api",
            "COPY requirements.txt ./",
            "RUN pip install --no-cache-dir -r requirements.txt",
            "COPY app ./app",
            f"ENV HOST=0.0.0.0 PORT={port}",
            f"EXPOSE {port}",
            f'CMD ["sh", "-c", "exec {ASGI_SERVER} app.main:app --host \\"$HOST\\" --port \\"$PORT\\""]',
            "",
        ]
    )

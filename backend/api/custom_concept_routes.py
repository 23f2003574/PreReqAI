"""The learner's custom concepts: list, confirm and forget (see backend/custom_concepts.py). A concept is added only by this explicit request."""
from fastapi import APIRouter
from pydantic import BaseModel

from backend import custom_concepts
from backend.api.workflow_result import failure_response, success_body

router = APIRouter(prefix="/api/custom-concepts", tags=["custom concepts"])


class NewConcept(BaseModel):
    name: str
    aliases: list[str] = []
    definition: str = ""


@router.get("")
def list_custom_concepts():
    concepts, problem = custom_concepts.load()
    return success_body("Custom Concepts", "custom_concepts", concepts=concepts, store=str(custom_concepts.store_path() or ""), warnings=[problem] if problem else [])


@router.post("")
def confirm_custom_concept(body: NewConcept):
    try:
        concept = custom_concepts.add(body.name, body.aliases, body.definition)
    except custom_concepts.CustomConceptError as error:
        return failure_response(422, "custom_concepts", str(error), hint="Use a new name of 3 to 80 letters, digits, spaces or hyphens, and set PREREQAI_PROFILE_DIR or PREREQAI_CUSTOM_CONCEPTS.")
    return success_body("Custom Concepts", "custom_concepts", concept=concept, note="It is used the next time a paper is analysed; it has no prerequisite rules.")


@router.delete("")
def forget_custom_concept(name: str):
    try:
        removed = custom_concepts.remove(name)
    except custom_concepts.CustomConceptError as error:
        return failure_response(422, "custom_concepts", str(error))
    if not removed:
        return failure_response(404, "custom_concepts", f"{name!r} is not a confirmed custom concept.", hint="GET /api/custom-concepts lists them.")
    return success_body("Custom Concepts", "custom_concepts", removed=name)

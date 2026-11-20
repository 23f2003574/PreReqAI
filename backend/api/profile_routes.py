"""Learner profile management: list, show, change, export, import and delete profiles (see backend/learner_profile.py and docs/learner-profile-format.md).
Everything needs PREREQAI_PROFILE_DIR; each name is its own file, so profiles never mix. A profile that cannot be read is reported (409) and never changed."""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import learner_profile, spaced_review
from backend.filelock import locked
from backend.api.workflow_result import failure_response, success_body

router = APIRouter(prefix="/api/profiles", tags=["Learner profiles"])
_NAME_HINT = "A profile name is 1 to 64 letters, digits, hyphens or underscores."


class ProfileUpdate(BaseModel):
    add_known: list[str] = Field(default_factory=list, description="concepts to mark as known")
    add_studied: list[str] = Field(default_factory=list, description="concepts to mark as studied (a known concept stays known)")
    forget: list[str] = Field(default_factory=list, description="concepts to remove from known and studied, so they no longer shape plans")
    forget_quiz: list[str] = Field(default_factory=list, description="concepts whose quiz history is deleted (mastery is never touched otherwise)")


def _located(name):
    """(path, None) for a valid name with profiles enabled, else (None, failure response)."""
    directory = learner_profile.configured_directory()
    if not directory:
        return None, failure_response(404, "profiles", f"Learner profiles are off: {learner_profile.PROFILE_DIR_ENV} is not set.",
                                      hint=f"Start the server with {learner_profile.PROFILE_DIR_ENV}=/some/private/dir.")
    path = learner_profile.profile_path(directory, name)
    if path is None:
        return None, failure_response(422, "profiles", f"Invalid profile name {name!r}.", hint=_NAME_HINT)
    return path, None


def _summary(path):
    profile, problem = learner_profile.load_full(path)
    if problem:
        return {"name": path.stem, "readable": False, "problem": problem}
    queue = spaced_review.queue(profile["quiz"], spaced_review.now())
    return {"name": path.stem, "readable": True, "known": len(profile["known"]), "studied": len(profile["studied"]), "questions": len(profile["quiz"]), "due": len(queue["due"])}


def _detail(path):
    profile, problem = learner_profile.load_full(path)
    if problem:
        return None, failure_response(409, "profiles", problem, hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    queue = spaced_review.queue(profile["quiz"], spaced_review.now())
    return {"name": path.stem, "format": learner_profile.FORMAT, "schema_version": learner_profile.SCHEMA_VERSION, "known": profile["known"], "studied": profile["studied"],
            "mastery": learner_profile.mastery(profile["quiz"]), "reviews": {"due": queue["due"], "upcoming": queue["upcoming"]}}, None


@router.get("")
def list_profiles():
    """The profiles on this server, each with counts (known, studied, questions, due reviews); an unreadable one is listed with its problem."""
    path, failure = _located(None)
    if failure:
        return failure
    return success_body("Learner Profiles", "profiles", profiles=[_summary(path.parent / f"{name}.json") for name in learner_profile.profile_names(path.parent)])


@router.get("/{name}")
def show_profile(name: str):
    """One profile: known and studied concepts, quiz mastery per concept and the reviews due or coming up. A name with no file yet is 404."""
    path, failure = _located(name)
    if failure:
        return failure
    if not path.exists():
        return failure_response(404, "profiles", f"There is no profile named {name!r}.", hint="A profile is created by analysing a paper with it, by PATCH, or by import.")
    detail, failure = _detail(path)
    return failure or success_body("Learner Profile", "profile", **detail)


@router.patch("/{name}")
def change_profile(name: str, body: ProfileUpdate):
    """Mark concepts known or studied, forget concepts, or delete quiz history, atomically. Concept names must be ones PreReqAI knows (any spelling of case, spaces,
    hyphens). Nothing else of the profile changes; an invalid name changes nothing."""
    path, failure = _located(name)
    if failure:
        return failure
    try:
        _, notes = learner_profile.update_profile(path, body.add_known, body.add_studied, body.forget, body.forget_quiz)
    except learner_profile.ProfileInputError as error:
        return failure_response(422, "profiles", str(error), hint="Use concept names from the study plan or the registry, such as Linear Algebra.")
    except learner_profile.ProfileError as error:
        return failure_response(409, "profiles", str(error), hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    except OSError as error:
        return failure_response(500, "profiles", f"The profile could not be saved ({getattr(error, 'strerror', None) or error}); the previous profile is unchanged.")
    detail, failure = _detail(path)
    return failure or success_body("Learner Profile", "profile", warnings=notes, **detail)


@router.get("/{name}/export")
def export_profile(name: str):
    """The profile as a portable file: the JSON document described in docs/learner-profile-format.md (version 1 files are exported as version 2)."""
    path, failure = _located(name)
    if failure:
        return failure
    if not path.exists():
        return failure_response(404, "profiles", f"There is no profile named {name!r}.")
    profile, problem = learner_profile.load_full(path)
    if problem:
        return failure_response(409, "profiles", problem, hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    document = {"format": learner_profile.FORMAT, "schema_version": learner_profile.SCHEMA_VERSION, **profile}
    return JSONResponse(document, headers={"Content-Disposition": f'attachment; filename="{path.stem}.prereqai-profile.json"'})


@router.post("/{name}/import")
async def import_profile(name: str, request: Request, replace: bool = False):
    """Create the profile from an exported document (version 1 or 2). An existing profile is not overwritten unless `replace=true`; an invalid or newer document changes nothing."""
    path, failure = _located(name)
    if failure:
        return failure
    raw = await request.body()
    if len(raw) > learner_profile.MAX_BYTES:
        return failure_response(422, "profiles", f"The document is larger than {learner_profile.MAX_BYTES} bytes.")
    try:
        profile = learner_profile.parse_full(raw)
    except learner_profile.ProfileError as error:
        return failure_response(422, "profiles", f"The document cannot be imported: {error}", hint="Send a document exported by PreReqAI.")
    with locked(path):
        if path.exists() and not replace:
            return failure_response(409, "profiles", f"A profile named {name!r} already exists.", hint="Send replace=true to overwrite it, or import under another name.")
        try:
            learner_profile.save(path, profile["known"], profile["studied"], profile["quiz"])
        except OSError as error:
            return failure_response(500, "profiles", f"The profile could not be saved ({getattr(error, 'strerror', None) or error}).")
    detail, failure = _detail(path)
    return failure or success_body("Learner Profile", "profile", **detail)


@router.delete("/{name}")
def delete_profile(name: str, confirm: bool = False):
    """Delete a whole profile (known, studied and quiz history) for good; `confirm=true` is required."""
    path, failure = _located(name)
    if failure:
        return failure
    if not confirm:
        return failure_response(422, "profiles", "Deleting a profile cannot be undone.", hint="Send confirm=true to delete it.")
    if not path.exists():
        return failure_response(404, "profiles", f"There is no profile named {name!r}.")
    path.unlink()
    return success_body("Learner Profile", "profile", name=name, deleted=True)

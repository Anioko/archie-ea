"""Epic hierarchy service — CRUD and tree operations for Epic/Story/Sub-task."""
from app import db


def _get_requirement_model():
    from app.models.models import Requirement
    return Requirement


def get_epic_tree(solution_id: int = None, board_id: int = None) -> list:
    """Return hierarchical tree of Epics with nested Stories and Sub-tasks.

    Returns:
        [
          {
            "id": N, "title": "Epic name", "type": "epic",
            "story_count": 3, "total_points": 21, "completed_points": 8,
            "stories": [
              {
                "id": M, "title": "As a user...", "type": "story",
                "story_points": 5, "dod_complete": False,
                "subtasks": [...]
              }
            ]
          }
        ]
    """
    Requirement = _get_requirement_model()

    epic_query = Requirement.query.filter_by(requirement_type="epic")
    if solution_id is not None:
        pass  # future: filter by solution_id when that FK exists
    epics = epic_query.order_by(Requirement.id).all()

    # Pre-fetch all stories and sub-tasks in two bulk queries to avoid N+1.
    epic_ids = [e.id for e in epics]
    if not epic_ids:
        return []

    all_stories = (  # model-safety-ok: single bulk query, not inside loop
        Requirement.query
        .filter(Requirement.requirement_type == "story",
                Requirement.epic_id.in_(epic_ids))
        .order_by(Requirement.id)
        .all()
    )
    story_ids = [s.id for s in all_stories]

    all_subtasks: list = []
    if story_ids:
        all_subtasks = (  # model-safety-ok: single bulk query, not inside loop
            Requirement.query
            .filter(Requirement.requirement_type == "sub_task",
                    Requirement.epic_id.in_(story_ids))
            .order_by(Requirement.id)
            .all()
        )

    # Index sub-tasks by parent story id
    subtasks_by_story: dict = {}
    for st in all_subtasks:
        subtasks_by_story.setdefault(st.epic_id, []).append(st)

    # Index stories by epic id
    stories_by_epic: dict = {}
    for s in all_stories:
        stories_by_epic.setdefault(s.epic_id, []).append(s)

    result = []
    for epic in epics:
        stories = stories_by_epic.get(epic.id, [])
        story_dicts = []
        total_points = 0
        completed_points = 0
        for story in stories:
            sp = story.story_points or 0
            total_points += sp
            if story.dod_complete:
                completed_points += sp
            subtasks = subtasks_by_story.get(story.id, [])
            story_dicts.append({
                "id": story.id,
                "title": story.title or "",
                "type": "story",
                "story_points": sp,
                "dod_complete": bool(story.dod_complete),
                "subtasks": [
                    {
                        "id": st.id,
                        "title": st.title or "",
                        "type": "sub_task",
                        "story_points": st.story_points or 0,
                        "dod_complete": bool(st.dod_complete),
                    }
                    for st in subtasks
                ],
            })
        result.append({
            "id": epic.id,
            "title": epic.title or "",
            "type": "epic",
            "story_count": len(stories),
            "total_points": total_points,
            "completed_points": completed_points,
            "stories": story_dicts,
        })
    return result


def create_epic(title: str, description: str = "", solution_id: int = None) -> dict:
    """Create a new epic Requirement."""
    Requirement = _get_requirement_model()
    epic = Requirement(
        title=title,
        description=description,
        requirement_type="epic",
    )
    db.session.add(epic)
    db.session.commit()
    return {"id": epic.id, "title": epic.title, "type": "epic"}


def create_story(title: str, epic_id: int, story_points: int = 0) -> dict:
    """Create a story under an epic."""
    Requirement = _get_requirement_model()
    story = Requirement(
        title=title,
        requirement_type="story",
        epic_id=epic_id,
        story_points=story_points,
        dod_complete=False,
    )
    db.session.add(story)
    db.session.commit()
    return {
        "id": story.id,
        "title": story.title,
        "type": "story",
        "epic_id": story.epic_id,
        "story_points": story.story_points or 0,
        "dod_complete": bool(story.dod_complete),
    }


def create_subtask(title: str, parent_story_id: int) -> dict:
    """Create a sub-task under a story (stored with epic_id = parent_story_id)."""
    Requirement = _get_requirement_model()
    subtask = Requirement(
        title=title,
        requirement_type="sub_task",
        epic_id=parent_story_id,
        story_points=0,
        dod_complete=False,
    )
    db.session.add(subtask)
    db.session.commit()
    return {
        "id": subtask.id,
        "title": subtask.title,
        "type": "sub_task",
        "parent_story_id": parent_story_id,
    }

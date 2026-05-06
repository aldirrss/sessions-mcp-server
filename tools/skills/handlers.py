import logging

from mcp.server.fastmcp import FastMCP

from .store import (
    read_skill,
    list_skills,
    search_skills,
    track_skill,
    recommend_skills,
)
from .models import (
    SkillReadInput,
    SkillListInput,
    SkillSearchInput,
    SkillTrackInput,
    SkillRecommendInput,
)

_logger = logging.getLogger("lm-mcp-ai.skills")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def register(mcp: FastMCP) -> None:
    """Register all skills tools on the given FastMCP instance."""

    @mcp.tool(
        name="skill_read",
        annotations={
            "title": "Read Skill",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def skill_read(params: SkillReadInput) -> str:
        """
        Read the full content of a skill from the library.

        Returns the complete Markdown content. Use this to load a skill's
        instructions into context before applying it.

        When session_id is provided, automatically records skill usage in
        session_skills (idempotent — safe to call multiple times).

        Args:
            params.slug: Skill slug to read.
            params.session_id: Active session ID for auto-tracking (optional).
        """
        try:
            skill = await read_skill(params.slug)
            if skill is None:
                return f"Skill `{params.slug}` not found."

            if params.session_id:
                try:
                    await track_skill(params.session_id, params.slug)
                except Exception:
                    pass

            tags_note = f"**Tags:** {', '.join(skill['tags'])}\n" if skill.get("tags") else ""
            cat_note = f"**Category:** {skill['category']}\n" if skill.get("category") else ""
            lines = [
                f"# Skill: {skill['name']}",
                f"**Slug:** `{skill['slug']}` | **Source:** {skill['source']}",
                f"**Updated:** {skill['updated_at']}",
                cat_note,
                tags_note,
                f"**Summary:** {skill['summary']}" if skill.get("summary") else "",
                "",
                "---",
                "",
                skill["content"],
            ]
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="skill_list",
        annotations={
            "title": "List Skills",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def skill_list(params: SkillListInput) -> str:
        """
        List all skills in the library (summary only, not full content).

        Use skill_read to load a specific skill's full content.

        Args:
            params.category: Filter by category (optional).
            params.tag: Filter by tag (optional).
            params.source: Filter by source — 'file' or 'manual' (optional).
        """
        try:
            skills = await list_skills(
                category=params.category,
                tag=params.tag,
                source=params.source,
            )
            if not skills:
                return "No skills found."

            lines = [
                f"## Skills Library ({len(skills)} skills)",
                "",
                "| Slug | Name | Category | Tags | Source |",
                "|------|------|----------|------|--------|",
            ]
            for s in skills:
                tags = ", ".join(s["tags"]) or "-"
                cat = s["category"] or "-"
                lines.append(
                    f"| `{s['slug']}` | {s['name']} | {cat} | {tags} | {s['source']} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="skill_search",
        annotations={
            "title": "Search Skills",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def skill_search(params: SkillSearchInput) -> str:
        """
        Full-text search across skill name, summary, content, and tags.

        Returns matching skills with a content snippet. Use skill_read to
        load the full content of a specific result.

        Args:
            params.query: Keyword to search for.
        """
        try:
            results = await search_skills(params.query)
            if not results:
                return f"No skills found matching '{params.query}'."

            lines = [f"## Search results for '{params.query}' ({len(results)} found)", ""]
            for r in results:
                cat = f" [{r['category']}]" if r.get("category") else ""
                tags = f" | tags: {', '.join(r['tags'])}" if r.get("tags") else ""
                lines.append(f"### `{r['slug']}` — {r['name']}{cat}")
                lines.append(f"*{r['summary']}*{tags}")
                lines.append(f"> {r.get('snippet', '')}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    # -----------------------------------------------------------------------
    # Session-skill tracking
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="skill_track",
        annotations={
            "title": "Track Skill Usage in Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def skill_track(params: SkillTrackInput) -> str:
        """
        Record that a skill was invoked in a session.

        Call this immediately after invoking any skill (/<slug>).
        On first use in a session: logs a compact note to the session automatically.
        On subsequent calls for the same skill+session: silently idempotent.

        Args:
            params.session_id: Active session ID.
            params.skill_slug: Slug of the skill that was invoked.
        """
        try:
            result = await track_skill(params.session_id, params.skill_slug)

            if result.get("skipped"):
                return (
                    f"Skill `{result['skill_slug']}` not found in skill library — tracking skipped."
                )

            if result["first_use"]:
                from tools.sessions.store import append_note
                await append_note(
                    params.session_id,
                    f"Skill activated: {result['skill_slug']} — {result['skill_name']}",
                    source="system",
                )
                return (
                    f"Skill `{result['skill_slug']}` tracked in session `{params.session_id}` "
                    f"(first use — note appended)."
                )

            return (
                f"Skill `{result['skill_slug']}` already tracked in session `{params.session_id}` "
                f"(no duplicate note)."
            )
        except FileNotFoundError as e:
            return _error(str(e))
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="skill_recommend",
        annotations={
            "title": "Recommend Skills for Session",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def skill_recommend(params: SkillRecommendInput) -> str:
        """
        Recommend skills not yet used in this session, ranked by tag overlap
        with the session's tags and overall usage frequency.

        Args:
            params.session_id: Active session ID to base recommendations on.
            params.limit: Maximum number of recommendations (default 5, max 20).
        """
        try:
            recs = await recommend_skills(params.session_id, limit=params.limit)
            if not recs:
                return (
                    f"No skill recommendations for session `{params.session_id}`. "
                    "All available skills may already be in use, or the session has no tags set."
                )

            lines = [
                f"## Recommended skills for `{params.session_id}` ({len(recs)} suggestions)",
                "",
            ]
            for r in recs:
                overlap = f" ★ {r['tag_overlap']} tag match" if r["tag_overlap"] > 0 else ""
                usage = f" · used in {r['usage_count']} sessions" if r["usage_count"] > 0 else " · new"
                lines.append(f"### `{r['slug']}` — {r['name']}{overlap}{usage}")
                if r.get("summary"):
                    lines.append(f"*{r['summary']}*")
                tags = ", ".join(r["tags"]) if r.get("tags") else ""
                if tags:
                    lines.append(f"Tags: {tags}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

import html
import sqlite3

import markdown_it
import nh3
import pypandoc

import quasilattice
import quasilattice.database

MARKDOWN_FLAVORS = ["commonmark", "pandoc", "gfm"]


def render_entry(cursor: sqlite3.Cursor, entry_dict: dict, target_markup: str = "html"):
    if target_markup.lower() == "html":
        return render_entry_to_html(cursor, entry_dict)
    return quasilattice.database.calculate_canonical_entry_bytes_from_dict(
        entry_dict
    ).decode("utf-8")


def render_entry_to_html(cursor: sqlite3.Cursor, entry_dict) -> str:
    if "content" not in entry_dict or not isinstance(entry_dict["content"], str):
        return nh3.clean(
            quasilattice.database.calculate_canonical_entry_bytes_from_dict(
                entry_dict
            ).decode("utf-8")
        )
    
    # plain text
    if ("markup" not in entry_dict or 
        not isinstance(entry_dict["markup"], str) or 
        entry_dict["markup"].lower() == "plain" or 
        entry_dict["markup"].lower() == "text" or 
        entry_dict["markup"].lower() == "txt" or 
        entry_dict["markup"].lower() == ""
    ):
        return html.escape(entry_dict["content"])

    # html
    if entry_dict["markup"].lower() == "html":
        return nh3.clean(entry_dict["content"])

    # markdown
    if (entry_dict["markup"].lower() == "markdown" or
        entry_dict["markup"].lower() == "md" or
        entry_dict["markup"].lower() in MARKDOWN_FLAVORS or
        "github" in entry_dict["markup"].lower()
    ):
        return render_entry_markdown_to_html(entry_dict)

    # TODO: add micron support (maybe use: https://github.com/JamesM92/micron2html)

    # pandoc
    try:
        return pypandoc.convert_text(
            entry_dict["content"], "html", format=entry_dict["markup"]
        )
    except (RuntimeError, OSError):
        return html.escape(entry_dict["content"])


def render_entry_markdown_to_html(cursor: sqlite3.Cursor, entry_dict: dict):
    md = markdown_it.MarkdownIt().use(markdown_embed_plugin)
    md.renderer.rules["embed"] = markdown_embed_renderer(md)

    html_str = md.render(entry_dict["content"])
    html_str = nh3.clean(html_str)
    return html_str


def markdown_parse_embed(src: str, pos: int) -> (str, str, str, int) | None:
    if src[pos : pos + 3] != "![[":
        return None

    start: int = pos + 3
    end: int = src.find("]]", start)
    if end == -1:
        return None

    content = src[start:end]
    if not content.strip():
        return None

    if "|" in content:
        target, alias = content.split("|", 1)
        alias = alias.strip()
    else:
        target = content
        alias = None

    if "#" in target:
        target, heading = target.split("#", 1)
        heading = heading.strip()
    else:
        heading = None

    target = target.strip()
    if not target:
        return None

    return target, heading, alias, end + 2


def markdown_embed_inline_rule(
    state: markdown_it.rules_inline.StateInline, silent: bool
) -> bool:
    result = markdown_parse_embed(state.src, state.pos)
    if result is None:
        return False

    target, heading, alias, end_pos = result

    if not silent:
        token = state.push("embed", "", 0)
        token.meta = {"target": target, "heading": heading, "alias": alias}
        token.markup = state.src[state.pos : end_pos]

    state.pos = end_pos
    return True


def markdown_embed_block_rule(
    state: markdown_it.rules_inline.StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    if state.sCount[start_line] - state.blkIndent >= 4:
        return False  # indent

    start_of_line: int = state.bMarks[start_line] + state.tShift[start_line]
    end_of_line: int = state.eMarks[start_line]
    line: str = state.src[start_of_line:end_of_line]

    result = markdown_parse_embed(line, 0)
    if result is None:
        return False

    target, heading, alias, end_pos = result

    if line[end_pos:].strip() != "":
        return False  # other content on this line

    if not silent:
        token = state.push("embed", "", 0)
        token.meta = {"target": target, "heading": heading, "alias": alias}
        token.block = True
        token.map = [start_line, start_line + 1]
        token.markup = line.strip()

    state.line = start_line + 1
    return True


def markdown_embed_plugin(md: markdown_it.MarkdownIt):
    md.inline.ruler.before("link", "embed", markdown_embed_inline_rule)
    md.block.ruler.before(
        "paragraph",
        "embed",
        markdown_embed_block_rule,
        {"alt": ["paragraph", "reference", "blockquote", "list"]},
    )


def markdown_parse_heading(line: str) -> (int, str) | None:
    """Returns (level, text) if line is a heading, else None."""
    level = 0
    while level < len(line) and line[level] == "#":
        level += 1
    if level == 0 or level > 6:
        return None
    if level >= len(line) or line[level] != " ":
        return None
    return level, line[level:].strip()


def markdown_extract_section(src: str, heading: str) -> str:
    """Extract the section of content under heading from markdown src."""
    lines = src.splitlines()
    output = []
    capturing = False
    level = None

    for line in lines:
        parsed = markdown_parse_heading(line)
        if parsed:
            heading_level, heading_text = parsed
            if capturing and heading_level <= level:
                break
            if heading_text == heading:
                capturing = True
                level = heading_level
                continue
        if capturing:
            output.append(line)

    return "\n".join(output)


def markdown_embed_renderer(md: markdown_it.MarkdownIt, max_depth: int = 6):
    stack: list[str] = []

    def render_embed(self, tokens, idx: int, options, env):
        meta = tokens[idx].meta
        target, heading, alias = meta["target"], meta["heading"], meta["alias"]

        entry_uuid = "uuid"  # get_entry_uuid(target) # TODO: implement
        if entry_uuid is None or entry_uuid in stack or len(stack) >= max_depth:
            return f"[[{html.escape(target)}]]"

        content = "CONTENT"  # quasilattice.database.read_entry_content_by_uuid(entry_uuid) # TODO: implement
        if heading:
            content = markdown_extract_section(content, heading)

        stack.append(entry_uuid)
        html_str = md.render(content, env)
        stack.pop()

        # TODO: do something with alias

        return html_str

    return render_embed

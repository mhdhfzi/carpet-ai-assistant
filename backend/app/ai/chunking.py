"""Split knowledge documents into retrievable chunks: one chunk per `##` section."""

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

_FRONT_MATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n", re.DOTALL)
_SECTION = re.compile(r"^## +(?P<heading>.+)$", re.MULTILINE)
_TITLE_LINE = re.compile(r"^# .*$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    source: str  # where it came from, e.g. "faq.md"; shown to the owner as the citation
    title: str  # document title
    heading: str  # section heading
    content: str

    @property
    def embedding_text(self) -> str:
        """What gets embedded. The title and heading give short sections their context:
        "Within 5 to 7 days..." alone says nothing about carpets."""
        return f"{self.title}: {self.heading}\n\n{self.content}"


def parse_document(text: str, source: str) -> list[Chunk]:
    text = text.replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError(f"{source}: missing front matter")
    title = _parse_meta(match["meta"]).get("title")
    if not title:
        raise ValueError(f"{source}: front matter has no title")

    body = text[match.end() :]
    sections = list(_SECTION.finditer(body))
    chunks = []

    # Text between the "# Title" line and the first "##" is an introduction.
    intro_end = sections[0].start() if sections else len(body)
    intro = _TITLE_LINE.sub("", body[:intro_end]).strip()
    if intro:
        chunks.append(Chunk(source, title, title, intro))

    for i, section in enumerate(sections):
        end = sections[i + 1].start() if i + 1 < len(sections) else len(body)
        content = body[section.end() : end].strip()
        if content:
            chunks.append(Chunk(source, title, section["heading"].strip(), content))
    return chunks


def load_documents(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    chunks = []
    for path in sorted(directory.glob("*.md")):
        if path.name != "README.md":
            chunks += parse_document(path.read_text(encoding="utf-8"), path.name)
    return chunks


def _parse_meta(meta: str) -> dict[str, str]:
    pairs = (line.split(":", 1) for line in meta.splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}

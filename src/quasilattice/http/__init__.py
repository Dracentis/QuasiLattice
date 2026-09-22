from __future__ import annotations

import fastapi

import quasilattice

from . import auth, editor, entries

app = fastapi.FastAPI()

app.include_router(auth.router)
app.include_router(editor.router)
app.include_router(entries.router)

@app.get("/api")
def get_api():
    return app.openapi()

def quasilattice_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = fastapi.openapi.utils.get_openapi(
        title="QuasiLattice",
        version=quasilattice.__version__,
        summary="A data analysis, knowledge base, journaling and note taking system.",
        description="""QuasiLattice (or Lattice for short) is a data analysis, knowledge base, journaling and note taking system built on a simple specification. This repository will contain a reference implementation written in Python, but it should be possible to build compatible QuasiLattice nodes in other languages or protocols other than HTTP.

QuasiLattice organizes data into "entries". Any file or JSON object is a valid QuasiLattice entry. Entries can contain a “content” string written in any markup language, which will be dynamically rendered when viewed.

Each QuasiLattice node maintains a list of entries and controls who has access to read and write to that list of entries.

Nodes can be configured to sync data with other nodes. This allows anybody to archive data from other QuasiLattice nodes. In protocols that support it, these mirrors provide bandwidth to reduce to load on the original source node and if the original source node fails then the data is still accessible. Every entry is canonically stored according to the JSON [RFC8785] subset, so hashes of entries can be compared between nodes.

QuasiLattice can also be configured in "archive_mode", where all changes to the entries are timestamped and nothing is deleted. In this mode, QuasiLattice can be used as an archival lab notebook for experimental research. Hashes of these entries could be proactively published online, cryptographically proving the timeline of scholarly work to third parties.""",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = quasilattice_openapi
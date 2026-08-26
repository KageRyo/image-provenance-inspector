# Real-world validation matrix

This matrix separates workflow coverage from claims about any particular tool.
Rows remain `Pending` until a legally redistributable source asset is captured,
its source and tool version are recorded, and the expected evidence is verified
against the actual file.

| Workflow | Origin | Editing | C2PA | EXIF preserved | Status |
| --- | --- | --- | --- | --- | --- |
| Official signed `c2pa.created` fixture | `UNKNOWN` | `UNKNOWN` | Yes | N/A | Validated |
| iPhone original photo | TBD | TBD | TBD | TBD | Pending asset |
| Photoshop traditional crop | TBD | TBD | TBD | TBD | Pending asset |
| Photoshop Generative Fill on camera photo | TBD | TBD | TBD | TBD | Pending asset |
| Gemini edit of a camera photo | TBD | TBD | TBD | TBD | Pending asset |
| ChatGPT generated image | TBD | TBD | TBD | TBD | Pending asset |
| Gemini generated image | TBD | TBD | TBD | TBD | Pending asset |
| Platform re-encoded download | TBD | TBD | TBD | TBD | Pending asset pair |

The `TBD` values are not failures. They prevent the test suite from encoding
assumptions about a vendor workflow before a real, traceable sample exists.

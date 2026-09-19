"""Central Unsplash photo system (backend mirror of frontend/src/utils/photos.js).

No uploads: doctors/hospitals automatically get an Unsplash URL on create.
Frontend already uses the same IDs; keep both lists in sync.
"""

def _u(pid: str, w: int = 256) -> str:
    return f"https://images.unsplash.com/{pid}?auto=format&fit=crop&w={w}&q=60"


DOCTOR_PHOTOS = [
    _u("photo-1559839734-2b71ea197ec2"),
    _u("photo-1612349317150-e413f6a5b16d"),
    _u("photo-1594824476967-48c8b964273f"),
    _u("photo-1622253692010-333f2da6031d"),
    _u("photo-1537368910025-700350fe46c7"),
    _u("photo-1651008376811-b90baee60c1f"),
    _u("photo-1582750433449-648ed127bb54"),
    _u("photo-1638202993928-7267aad84c31"),
    _u("photo-1551601651-2a8555f1a136"),
    _u("photo-1579684385127-1ef15d508118"),
    _u("photo-1612349316228-5942a9b489c2"),
    _u("photo-1580489944761-15a19d654956"),
]

HOSPITAL_COVERS = [
    _u("photo-1519494026892-80bbd2d6fd0d", 1200),
    _u("photo-1586773860418-d37222d8fce3", 1200),
    _u("photo-1538108149393-fbbd81895907", 1200),
    _u("photo-1516549655169-df83a0774514", 1200),
    _u("photo-1512678080530-7760d81faba6", 1200),
    _u("photo-1587854692152-cbe660dbde88", 1200),
]


def _hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def doctor_photo_for(key: str) -> str:
    """Deterministic auto photo for a doctor (no upload prompt)."""
    s = str(key or "x")
    return DOCTOR_PHOTOS[_hash(s) % len(DOCTOR_PHOTOS)]


def hospital_cover_for(slug: str) -> str:
    """Deterministic auto cover for a hospital (no upload prompt)."""
    s = str(slug or "x")
    return HOSPITAL_COVERS[_hash(s) % len(HOSPITAL_COVERS)]

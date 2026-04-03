from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    anime_data_root = Path(os.environ.get("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = Path(
        os.environ.get("ANIME_COLLECTION_ROOT", "/srv/anime-collection")
    )

    print("anime-postprocessor skeleton")
    print(f"ANIME_DATA_ROOT={anime_data_root}")
    print(f"ANIME_COLLECTION_ROOT={anime_collection_root}")
    print("TODO: implement parser, probe, decision engine, publisher")


if __name__ == "__main__":
    main()

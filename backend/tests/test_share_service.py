import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.models.schemas import ShareCreateRequest
from app.services.share_service import JsonShareStore


def test_json_share_store_creates_and_reads_snapshot(tmp_path):
    store = JsonShareStore(tmp_path / "shares.json")

    snapshot = store.create_share(
        ShareCreateRequest(
            title="测试标题",
            content="测试内容",
            hashtags=["小红书", "种草"],
            image_url="https://example.com/image.png",
        )
    )

    loaded = store.get_share(snapshot.id)

    assert loaded is not None
    assert loaded.id == snapshot.id
    assert loaded.title == "测试标题"
    assert loaded.hashtags == ["小红书", "种草"]

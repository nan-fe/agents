"""飞书 OAuth URL 构建测试。"""

from lark_im.oauth import LarkOAuthService


def test_build_authorize_url_encodes_redirect_uri() -> None:
    svc = LarkOAuthService(app_id="cli_x", app_secret="sec")
    url = svc.build_authorize_url(
        "http://localhost:8000/lark/oauth/callback",
        "signed-state",
        scope="offline_access",
    )
    assert "redirect_uri=" in url
    assert "state=signed-state" in url
    assert "scope=offline_access" in url

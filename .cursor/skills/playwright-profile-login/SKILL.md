---
name: playwright-profile-login
description: >-
  修复 Playwright 持久化 Profile 浏览器登录交互：打开可见浏览器、用户手动登录、
  前端点「我已登录」确认并持久化。适用于微博登录走不通、截图远程操控失败、
  OAuth/扫码登录需要真人操作、或用户要求简化第三方平台登录流程的场景。
---

# Playwright Profile 浏览器登录（手动确认模式）

## 核心原则

**不要**用截图 + 坐标点击 + 自动轮询来替代真人登录。

**应该**用「打开 Profile 浏览器 → 用户手动完成 → 用户主动确认」三步流：

1. 后端 `start`：Playwright `launch_persistent_context`，**`headless=False`**，打开目标站
2. 用户：在真实浏览器窗口完成账号/扫码/验证码
3. 后端 `confirm`：检测登录态 → 关闭浏览器（Cookie 写入 Profile 目录）→ 写 DB 记录

Profile 目录（如 `data/weibo-profile`）才是登录态载体；DB 只记「已确认」元数据，避免每次 `/social/status` 都起浏览器。

## 何时用这个模式

| 症状 | 原因 | 修复方向 |
|------|------|----------|
| 截图弹窗点不动 / 验证码过不了 | headless + 远程坐标交互不可靠 | 改可见浏览器 + 手动确认 |
| 自动轮询永远 `logged_in: false` | 检测时机或页面 DOM 变化 | 把检测挪到用户点「我已登录」时 |
| `socket hang up` on login/start | 后端未起或 Playwright 启动崩溃 | 先确认 `:8000` 与 `playwright install chromium` |
| Profile 锁冲突 | 同时开了登录会话和发布检测 | `weibo_profile_lock` 互斥，登录中 status 返回「登录进行中」 |

## 本仓库文件地图（微博实现）

```
backend/app/services/social/
├── weibo_login_session.py   # 会话：start / confirm / close
├── weibo_auth_store.py      # SQLite weibo_auth 表读写
├── weibo_publisher.py       # check_weibo_login_state、发布
├── profile_paths.py         # resolve_weibo_profile_dir、锁清理
frontend-share/src/app/studio/components/
├── weibo-login-panel.tsx    # 弹窗：提示 +「我已登录」
├── social-sync-settings.tsx # 入口按钮「登录微博」
frontend-share/src/services/api.ts
└── startWeiboLoginSession / confirmWeiboLogin / closeWeiboLoginSession
backend/app/main.py
└── POST .../login/start | .../confirm | DELETE .../{session_id}
```

配置：`WEIBO_PUBLISH_ENABLED`、`BROWSER_USE_PROFILE_PATH`、`WEIBO_BROWSER_CHANNEL=chrome`

## 修复清单（按顺序）

```
- [ ] 1. 确认问题属于「需要真人浏览器」而非 API/配置错误
- [ ] 2. 登录会话强制 headless=False、for_login=True
- [ ] 3. 新增 confirm 端点：evaluate_login → save_weibo_auth → close → invalidate cache
- [ ] 4. 前端去掉截图轮询/坐标点击，只保留「我已登录」+「取消」
- [ ] 5. check_weibo_login_state 无 force_refresh 时先读 DB 已确认记录
- [ ] 6. 更新 schema.d.ts、补测试（API flow + auth store + status mock）
- [ ] 7. 本地验证：start 弹出 Chrome → 登录 → confirm → status 显示已登录
```

## 后端要点

### start 会话

```python
context = await _launch_context(playwright, headless=False, for_login=True)
await page.goto("https://weibo.com/", wait_until="domcontentloaded")
```

- 持有 `weibo_profile_lock`，避免与发布/检测并发
- 若启动时已登录，直接 `save_weibo_auth` + `close`

### confirm 确认

```python
state = await session.evaluate_login()
if state["logged_in"]:
    await save_weibo_auth(profile_path=..., logged_in=True, current_url=...)
    invalidate_weibo_login_state_cache()
    await session.close()  # 持久化 Profile 到磁盘
else:
    raise HTTPException(400, "尚未检测到微博登录...")
```

### 登录检测（轻量）

在浏览器内 `page.evaluate`，看 URL 是否离开 passport/login，且 body 不含登录文案 marker。  
**避免**在登录进行中频繁 `page.content()` 拉整页 HTML。

### DB 表 `weibo_auth`（单例 id=default）

字段：`profile_path`、`logged_in`、`current_url`、`confirmed_at`。  
`get_weibo_auth()` 与当前 `resolve_weibo_profile_dir()` 路径一致时才视为有效。

## 前端要点

- 弹窗打开时 **只调一次** `startWeiboLoginSession()`
- 文案明确：「已打开 Profile 浏览器，请完成登录后点我已登录」
- `confirmWeiboLogin(sessionId)` 成功 → `onLoggedIn()` + `refreshStatus(true)`
- **不要**在 confirm 成功后再 `closeWeiboLoginSession`（confirm 已关浏览器）
- 取消时才 `DELETE .../login/{session_id}`

## 反模式（不要再做）

- headless 截图 + 前端 `<img onClick>` 模拟点击登录表单
- 每 5s 自动轮询 `status` 期望自动关闭（验证码/扫码场景不可靠）
- 用 `DISPLAY` 环境变量决定是否 headless（本机 Mac 也应直接可见浏览器）
- Profile 路径含 `chrome` 字样（Playwright 可能复制到临时目录，登录态丢失）

## 测试

```bash
cd backend
python3 -m pytest tests/test_weibo_login_api.py tests/test_weibo_auth_store.py tests/test_weibo_auto_publish.py -m "not network" -q
```

mock 要点：`get_weibo_auth` 返回 `None` 才能测到「未检测」与 force_refresh 分支。

## 参考脚本

本地一次性登录（与后端同 Profile）：

```bash
cd backend && python3 scripts/weibo_login.py
```

## 扩展到其他平台

复用同一骨架，替换：

| 层 | 替换项 |
|----|--------|
| URL | 目标站首页 / 登录页 |
| evaluate_login | 平台登录 marker 与 URL 规则 |
| DB 表名 | 如 `x_auth`，或通用 `browser_auth(platform)` |
| 前端文案 | 平台名与操作提示 |

保持：**可见浏览器 + 用户确认 + Profile 持久化 + DB 确认记录** 不变。

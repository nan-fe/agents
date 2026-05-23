---
name: frontend-rule
description: 规范
---

---
name: frontend-tailwind
description: 在写前端样式的时候，优先使用className="" 形式写tailwind 语法
---

# 技能标题

## 描述
使用 tailwind 语法写样式，减少style属性的使用，比如 className="flex flex-1 jusitify-between"

## 使用场景
在写前端样式的时候，比如改动的文件在 frontend-ts 下面，优先使用 tailwindcss 语法，例如
```bash
className="flex flex-1 justify-between"
```
如果不支持，可以降级使用 style={} 形式写，例如
```bash
style={{ display: 'flex', justifyContent: 'space-between' }}
```
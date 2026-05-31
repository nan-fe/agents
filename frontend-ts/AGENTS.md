# frontend-ts Agent Guidelines

本目录使用 **React 19** + **React Compiler**（Vite + `@vitejs/plugin-react` + `babel-plugin-react-compiler`）。新增或修改 React 代码时，应遵循 React 19 推荐写法，并确保代码可被 Compiler 自动优化。

## React 19 推荐模式

### 异步交互：优先 `useActionState`

对「触发异步操作 + pending 状态 + 更新结果」的场景，使用 `useActionState`，不要用 `useState` 手动管理 loading，也不要在组件内写 `try/catch/finally` 来切换 pending。

```tsx
// ✅ 推荐：action 定义在组件外，onClick 内用 startTransition 包裹 dispatch
import { startTransition, useActionState } from 'react';
const shareResultAction = async (prev: State, payload: Payload): Promise<State> => {
  try {
    const data = await api(payload);
    return { data };
  } catch (error) {
    console.error(error);
    return prev;
  }
};

const MyComponent = ({ payload }: Props) => {
  const [state, dispatch, isPending] = useActionState(shareResultAction, initialState);
  return (
    <Button
      loading={isPending}
      onClick={() => {
        startTransition(() => {
          dispatch(payload);
        });
      }}
    />
  );
};
```

```tsx
// ❌ 避免：手动 pending + 组件内 finally（会导致 React Compiler bailout）
const [loading, setLoading] = useState(false);
const handleClick = async () => {
  try {
    setLoading(true);
    await api();
  } finally {
    setLoading(false);
  }
};
```

参考实现：`src/components/result-display.tsx`。

**SSE 流式生成例外**：长连接流式场景（如 `dialog-content.tsx`）不要用 `useActionState` 包裹整段生成逻辑（会延迟中间 state 提交）。改用模块级 async + `isGenerating` state，action 逻辑放在组件外。

### 其他 React 19 API（按需使用）

- **`use`**：在支持 Suspense 的数据读取场景，优先于「mount 时 `useEffect` + `setState`」。
- **`useOptimistic`**：乐观 UI 更新。
- **表单提交**：可配合 `useActionState` 与 `<form action={...}>` 使用。

### 组件与函数风格

- 组件、helper、回调优先使用 **arrow function**（与仓库根目录 `AGENTS.md` 一致）。
- 样式优先 **Tailwind CSS** utility class。

## React Compiler 兼容性

Compiler 按**整个组件函数**分析。函数体内出现暂不支持的语法时，会**静默跳过该组件的全部优化**（DevTools 无 `Memo ✨`）。

### 必须遵守

1. 遵循 [Rules of React](https://react.dev/reference/rules)（Hooks 规则、组件 purity、refs 用法等）。
2. 组件内的 `try/catch/finally` 中，**避免 `finally`**；复杂错误处理抽到**组件外的纯函数 / action**。
3. 不要依赖「手写 `useMemo` / `useCallback` / `React.memo`」替代 Compiler；仅在 ESLint `preserve-manual-memoization` 等规则明确要求时保留。
4. 不要用 `"use no memo"` 除非有 documented 理由。

### 常见 bailout 语法（组件内避免）

- `try { } catch { } finally { }`
- `eval`、`with`
- 其他 `react-hooks/todo` / `react-hooks/unsupported-syntax` 报告的模式

## ESLint 检查（必跑）

项目通过 `eslint-plugin-react-hooks@7` 做静态检查，规则与 React Compiler 分析一致。

### 已启用规则

- `plugin:react-hooks/recommended-latest`：React 19 / Compiler 核心规则
- `react-hooks/todo`：**error** — 检测 Compiler 尚未支持的语法（静默 bailout）
- `react-hooks/unsupported-syntax`：**error** — 检测无法静态分析的语法

### 命令

```bash
# 仅检查 React 源码（推荐，CI / 提交前）
pnpm lint:react

# 全项目 ESLint（含 prettier 等）
pnpm lint
```

`pnpm lint:react` 对 `react-hooks/todo` 与 `react-hooks/unsupported-syntax` 必须 **0 error**，才视为通过 React 19 + Compiler 合规检查。

### 单文件调试

```bash
pnpm exec eslint src/components/result-display.tsx --quiet
```

## 人工验证（可选）

1. 本地 `pnpm dev`，打开 React DevTools Components 面板。
2. 已被 Compiler 优化的组件名称旁应显示 **`Memo ✨`**。
3. 若 ESLint 通过但无 badge，确认 `vite.config.ts` 中 React Compiler 配置仍生效。

## Code Review 清单

- [ ] 新的异步按钮/表单交互是否用了 `useActionState`（或等价的 form action），而非手动 `loading` state？
- [ ] 组件内是否没有 `try/finally`？
- [ ] 布局与视觉样式是否优先使用 Tailwind `className`，而非 inline `style` / 新增 CSS 文件？
- [ ] `pnpm lint:react` 是否 0 error？
- [ ] 是否 unnecessary 地添加了 `useMemo` / `useCallback` / `memo`？

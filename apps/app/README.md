# @repo/app — Kadal Mitra (Android) + web console

One Expo SDK 57 codebase (spec Chapter 17). Routes in `app/`, shared code in `src/`.

```bash
pnpm start          # Metro for the development build (Expo Go is not supported)
pnpm web            # web build in the browser
pnpm test           # jest-expo
pnpm typecheck
pnpm lint
```

Public settings come from `.env.local` (`EXPO_PUBLIC_*` only, see `.env.example`), validated by `src/env.ts`.

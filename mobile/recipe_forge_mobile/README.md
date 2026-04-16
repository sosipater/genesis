# Recipe Forge Mobile

Flutter app scaffold for Android cooking-first companion.

Current baseline modules:

- `lib/app`: app bootstrap and dependency wiring
- `lib/config`: mobile config defaults
- `lib/data/db`: SQLite schema bootstrap
- `lib/data/models`: typed recipe and sync models
- `lib/data/repositories`: local persistence and sync metadata repositories
- `lib/data/sync`: typed LAN sync API client and sync service
- `lib/features/library`: local recipe list
- `lib/features/recipe_view`: cooking-oriented tabbed recipe screen
- `lib/features/sync`: host configuration and manual sync actions

Quick dev commands (PowerShell):

- `.\dev.ps1 get` - install/update dependencies
- `.\dev.ps1 run` - run app
- `.\dev.ps1 test` - run tests
- `.\dev.ps1 analyze` - run analyzer
- `.\dev.ps1 check` - analyze + test
- `.\dev.ps1 clean` - clean + restore dependencies

Bundled content note:

- Mobile currently does not ship bundled recipe assets locally.
- Mobile local store receives recipe data via sync and preserves `scope` for distinction.
- Architecture remains ready for future bundled mobile asset overlay.


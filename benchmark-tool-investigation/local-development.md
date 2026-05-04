# Local Development

## Syncing a local Bench Pack into BenchLocal

BenchLocal runs installed Bench Packs from `~/.benchlocal/benchpacks/<benchpack-id>/versions/<current-version>`. If you edit a Bench Pack in this repository, those changes are not picked up by the app until the installed copy is updated.

Use the sync script:

```bash
npm run sync:benchpack -- ReasonMath-15
```

What it does:

- reads `benchlocal.pack.json` from the local Bench Pack
- runs `npm run build:benchlocal` when that script exists
- finds the active installed version from `~/.benchlocal/benchpacks/<id>/current.json`
- overlays the local Bench Pack files into that installed version
- preserves the installed `node_modules`

Preview without writing:

```bash
npm run sync:benchpack -- ReasonMath-15 --dry-run
```

Skip the build step:

```bash
npm run sync:benchpack -- ReasonMath-15 --no-build
```

Use a custom BenchLocal home:

```bash
node scripts/sync-local-benchpack.mjs ReasonMath-15 --benchlocal-home ~/.benchlocal
```

Restart BenchLocal after syncing so the main process reloads the updated Bench Pack module.

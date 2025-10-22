# Changelog

All notable changes to the atlas-rag package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.4.post5] - 2025-10-22

### Fixed
- **DatasetDict schema**: Fixed `load_dataset()` to return `DatasetDict` with "train" split instead of plain `Dataset`
  - Code expects `dataset["train"]` access pattern (line 378 in triple_extraction.py)
  - Now wraps Dataset in DatasetDict: `DatasetDict({"train": dataset})`

## [0.0.4.post4] - 2025-10-22

### Fixed
- **datasets compatibility**: Fixed `NotImplementedError: Loading a dataset cached in a LocalFileSystem` error
  - Rewrote `TripleExtractor.load_dataset()` to load JSON/JSONL files directly
  - Avoids HuggingFace datasets caching mechanism that changed in newer versions
  - Supports `.json`, `.json.gz`, `.jsonl`, and `.jsonl.gz` formats
  - Handles both single objects and arrays in JSON files

### Changed
- **datasets version constraint**: Pinned `datasets>=2.14.0,<3.0.0` for stability
- **Added faiss-cpu dependency**: Added `faiss-cpu>=1.7.4` for vector similarity search

### Improved
- Better error handling when loading datasets
- More flexible JSON file format support
- Clearer error messages when files cannot be loaded

## [0.0.4.post3] - 2025-10-22

### Fixed
- **Python 3.11+ compatibility**: Removed `azure-cli` dependency that pulled in Python 2-only packages
  - Removed `azure-cli` which depended on `futures` (Python 2 backport)
  - `futures` package explicitly fails on Python 3 with error: "This backport is meant only for Python 2"
  
### Changed
- Azure functionality preserved through modern SDK packages:
  - `azure-ai-projects`
  - `azure-ai-inference`
  - `azure-identity`

### Removed
- `azure-cli` dependency (was pulling in outdated 2017 version with Python 2 dependencies)

## [0.0.4.post2 and earlier]

Previous versions - see git history for details.

---

## Migration Guide

### From 0.0.4.post2 or earlier to 0.0.4.post3+

No code changes required. Simply update your dependency:

```bash
pip install --upgrade git+https://github.com/gobrainy/AutoSchemaKG.git@main
```

### Known Issues

None currently.

### Deprecations

None currently.

---

## Compatibility

- **Python**: 3.9, 3.10, 3.11, 3.12
- **datasets**: 2.14.0 - 2.x.x (not compatible with 3.x yet due to API changes)
- **transformers**: Any compatible version
- **Azure SDK**: Modern versions (`azure-ai-*` packages)

---

For detailed technical information about the compatibility fixes, see [COMPATIBILITY_FIXES.md](COMPATIBILITY_FIXES.md).


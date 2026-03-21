# ScriptSmith

Iterative screenplay optimizer using LLM-as-judge loop.

## Install

```bash
pip install scriptsmith
```

## Quick Start

```bash
scriptsmith init screenplay.docx --criteria scoring.docx
scriptsmith run --mode micro --rounds 20
scriptsmith status
scriptsmith export --output improved.docx
```

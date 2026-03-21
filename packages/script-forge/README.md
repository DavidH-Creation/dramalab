# Script-Forge

Iterative screenplay optimizer using LLM-as-judge loop.

## Install

```bash
pip install script-forge
```

## Quick Start

```bash
script-forge init screenplay.docx --criteria scoring.docx
script-forge run --mode micro --rounds 20
script-forge status
script-forge export --output improved.docx
```

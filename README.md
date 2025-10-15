# LLM Code Deployment System

An automated system that receives task briefs, generates web applications using AI, and deploys them to GitHub Pages.

## 🚀 System Overview

This project implements an API-driven deployment pipeline that:
- Receives task requests via REST API
- Generates complete web applications using LLM (AIpipe.org)
- Creates GitHub repositories automatically
- Deploys to GitHub Pages
- Handles iterative revisions (Round 1 & Round 2)

## 📡 API Endpoint

**Live Endpoint:** `https://23f1001792-llm-code-deployment.hf.space/api-endpoint`

## 🏗️ Architecture

- **API Server**: FastAPI hosted on Hugging Face Spaces
- **LLM Integration**: AIpipe.org for code generation
- **Repository Management**: GitHub API (PyGithub)
- **Deployment**: GitHub Pages (automatic)

## 📦 Generated Repositories

Task-specific repositories are automatically created with naming pattern:
- `sum-of-sales-{hash}`
- `markdown-to-html-{hash}`
- `github-user-created-{hash}`

Each generated repo includes:
- ✅ Complete working application (`index.html`)
- ✅ Professional README.md
- ✅ MIT LICENSE
- ✅ GitHub Pages deployment

## 🔗 Links

- **API Health Check**: https://23f1001792-llm-code-deployment.hf.space/health
- **Hugging Face Space**: https://huggingface.co/spaces/23f1001792/llm-code-deployment
- **GitHub Profile**: https://github.com/shreyamondal1

## 🛠️ Technology Stack

- Python 3.10
- FastAPI
- httpx (async HTTP client)
- GitHub REST API
- AIpipe.org LLM API

## 📋 Project Requirements

This system fulfills all project requirements:
- [x] Receives & verifies requests with secret validation
- [x] Uses LLM-assisted code generation
- [x] Creates GitHub repositories programmatically
- [x] Deploys to GitHub Pages automatically
- [x] Pings evaluation API with retry logic
- [x] Handles Round 1 (initial build)
- [x] Handles Round 2 (revisions)
- [x] Adds MIT LICENSE
- [x] Generates professional README
- [x] Response within 10-minute window

## 📝 License

MIT License - See individual generated repositories for details.

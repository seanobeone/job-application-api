# Job Application API

A local-first job-search and application-assistance project built with **Python, FastAPI, SQLite, Playwright, and REST-style APIs**. The project combines job discovery, role matching, resume selection, browser-assisted workflows, and optional Gmail status tracking in one local application.

## Why I Built It

I built this project to explore how API automation can reduce repetitive work in a job search while keeping important decisions under human control. It demonstrates practical work with Python services, local data storage, browser automation, configuration management, troubleshooting, and workflow design.

## Key Capabilities

- FastAPI service for local job workflow endpoints
- Job discovery and filtering logic
- Resume/job-description matching
- SQLite-backed job tracking
- Playwright-based browser assistance
- Optional Gmail OAuth integration for application-status signals
- Local control-center interface and PowerShell launch scripts
- Human-review controls for sensitive application questions
- Automatic final submission disabled by default

## Safety & Privacy Design

This public repository intentionally excludes personal resumes, browser profiles, databases, logs, OAuth credentials/tokens, and personal candidate answers. Sensitive demographic and screening responses are not inferred by the application. Users should review application data before submission.

## Technology

Python • FastAPI • Uvicorn • Pydantic • SQLite • HTTPX • Playwright/browser automation concepts • Google API/OAuth libraries • PowerShell

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `config.example.json` to `config.json` and customize only your local copy.
4. Copy `config/candidate_answers.example.json` to `config/candidate_answers.json` if using candidate-answer assistance.
5. Add your own resume paths to your private/local candidate profile.
6. If using Gmail integration, place your own Google OAuth credentials in `oauth/` and never commit them.
7. Start the API using the provided PowerShell launcher or Uvicorn.

## Portfolio Context

This repository is a sanitized portfolio edition of a working local project. It is intended to demonstrate my approach to automation, APIs, infrastructure-oriented problem solving, and secure handling of local configuration—not to expose private job-application data.

## Author

**Adrian Lyons**  
Cybersecurity • Cloud & DevOps • IT Infrastructure • AWS • Python • Automation

Portfolio: https://adrian-lyons-cybersecurity-portfolio.adrianlyons36.chatgpt.site/  
LinkedIn: https://www.linkedin.com/in/adrian-lyons-44a925b7/

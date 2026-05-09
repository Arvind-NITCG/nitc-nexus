#  NITC Nexus

**The Intelligent Campus Knowledge Agent for NIT Calicut** *Phase 1: CS Department MVP (RAG Architecture)*

NITC Nexus is an intelligent, hallucination-free conversational agent designed to centralize scattered campus data (circulars, attendance rules, syllabus). Instead of blindly searching PDFs, Nexus utilizes Agentic AI and Retrieval-Augmented Generation (RAG) to provide exact, context-aware answers to students via App and WhatsApp.

---

##  The Architecture (Two-Stream Memory)

We are building a highly modular, decoupled system.

- **AI & Data Core (The Brain & Vault):**  **Tech:** Python, LangChain, ChromaDB, Gemini/OpenAI API.                                                                                                                **Logic:** Automated Email IMAP parsing converts PDFs to Markdown JSON. LangChain chunks the data via headers, and ChromaDB handles local vector storage with strict metadata filtering to prevent stale data retrieval.
- **Backend Bridge (The Nervous System):** **Tech:** Python, FastAPI, PostgreSQL, Meta WhatsApp Webhook.
**Logic:** Asynchronous routing. Handles user session memory (sliding window of last 5 messages) and connects external interfaces to the AI core.
- **Frontend UI (The Face):** * **Tech:** Flutter / Kotlin.
**Logic:** Sleek, low-latency mobile application interacting via REST APIs with the FastAPI backend.

---

## The Team

* **Arvind** - System Architect & Lead Integrator
* **Prashant** - AI Logic & Data Refiner (LangChain Core)
* **Sanjitha** - Database Vault Keeper (ChromaDB)
* **Rahan** - Data Harvester (Email API Pipeline)
* **Akash** - Backend Infrastructure (FastAPI & PostgreSQL)
* **Jefin** - External Integrations (WhatsApp API)
* **Irene** - Frontend UI Experience (App Dev)

---

## Rules of Engagement & Branching Strategy

To prevent merge conflicts and protect the architecture, **NO ONE is allowed to push directly to the `main` branch.**

### The Branches:
* `main`  - Production-ready, 100% stable code. (Locked)
* `dev`  - The staging area for integration testing. (Locked)
* `feature/ai-core` - For Prashant, Sanjitha, and Rahan's scripts.
* `feature/backend` - For Akash and Jefin's server/routing code.
* `feature/frontend` - For Irene's UI code.

### The PR Workflow:
1. Switch to your designated feature branch locally.
2. Commit your code with clear, descriptive messages.
3. Push to your feature branch and open a **Pull Request (PR)** targeting the `dev` branch.
4. **All PRs require a mandatory code review and approval from the System Architect before merging.**

*let's build something legendary.*

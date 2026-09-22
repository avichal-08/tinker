# Tinker

Tinker is a local-first, CLI-based AI agent that diagnoses and resolves computer performance issues. It uses open-weights LLMs via Groq to read system metrics, map network ports, and scan for bloat, executing fixes through a strict human-in-the-loop safety gatekeeper.

## Capabilities

* **Stateful Interactive Chat:** Run continuous diagnostic sessions via `tinker chat`.
* **Zombie Port Resolver:** Maps open network ports to PIDs and kills processes causing `EADDRINUSE` conflicts.
* **Deep Bloat Scanning:** Safely finds and measures Docker artifacts, Windows update caches, and heavy developer folders (`node_modules`, `.venv`).
* **System & Thermal Sensors:** Reads real-time RAM/CPU pressure, battery health, and CPU clock frequencies to diagnose thermal throttling.
* **Startup Program Audit:** Inspects the Windows Registry to identify background apps slowing down boot times.
* **Zero-Risk Execution:** Never modifies the system without an explicit `[y/n]` terminal prompt. Deleted files are routed to the OS **Recycle Bin** (`send2trash`), never permanently destroyed.

---

## Setup Guide

### Prerequisites
* Python 3.12 or higher
* Windows 10 or 11
* Git
* A free API key from [Groq](https://console.groq.com/keys)

### 1. Clone the Repository
Open your terminal and clone the project to your local machine:
```bash
git clone [https://github.com/YOUR_USERNAME/tinker.git](https://github.com/YOUR_USERNAME/tinker.git)
cd tinker
```
### 2. Configure the Environment
Tinker requires a .env file to securely load your API key.
Create a file named .env in the root tinker/ directory and add your Groq key:
```bash
GROQ_API_KEY=your_api_key_here
```
### 3. Create a Virtual Environment
Isolate the project dependencies by creating and activating a Python virtual environment.
```bash
python -m venv venv
venv\Scripts\activate
```
### 4. Install Tinker Globally
Install the project in editable mode. This registers the tinker command globally in your active environment and installs all required dependencies (Pydantic, psutil, Rich, Typer, Docker SDK).
```bash
pip install -e .
```
### 5. Verify Installation
Ensure the CLI is wired up correctly by checking the help menu:
```bash
tinker --help
```
---

## Usage
Tinker can be run from any directory on your machine while your virtual environment is active.

Start a stateful conversation where Tinker remembers context across multiple queries:
```bash
tinker chat
```
Example flow:

- You: "What are my top 3 memory consuming processes?"

- You: "Kill the second one on that list."

### One-Shot Diagnostics
Pass a query directly to the CLI for a single-pass diagnosis and execution:
```bash
tinker "Why is my computer slow?"
tinker "Something is hogging port 8080, find it and kill it."
tinker "Scan for windows bloat and heavy project artifacts in my current folder."
```

## Architecture & Safety
Tinker is built with a Gatekeeper Pattern. The LLM operates in a read-only reasoning loop. When it decides to mutate the system (kill a process, delete a cache), it must hand off the request to src/safety/executor.py.

The execution pauses the UI spinner, presents a risk-assessed summary of the action, and requires explicit user approval. Critical Windows system processes (explorer.exe, svchost.exe, etc.) are hard-coded into a blocklist and will be unconditionally rejected, even if hallucinated by the model.

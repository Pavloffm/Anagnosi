# Anagnosi - Personal knowledge base
## Installation
### Prerequisites
- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- [Ollama](https://ollama.com/download) for local LLM serving

### 1: Clone the Repository
```commandline
git clone https://github.com/Pavloffm/Anagnosi.git
```
### 2: Install Dependencies
```commandline
poetry install
poetry shell
```

### 3: Configure Environment
Copy example environment file
```commandline
cp .env.example .env
```
Edit .env with your preferences

## Run tests
```commandline
poetry run pytest
```
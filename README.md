# CryptoQuant

**Institutional-grade quantitative research platform for cryptocurrency trading**

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Vision

CryptoQuant is a long-term quantitative investment research platform designed for systematic cryptocurrency trading. Built with institutional-grade architecture, it provides a comprehensive framework for data collection, technical analysis, strategy backtesting, AI-powered insights, and automated execution with human-in-the-loop approval workflows.

## Goals

- **Data-Driven Research**: Collect and analyze cryptocurrency market data from Coinbase API
- **Rigorous Backtesting**: Validate trading strategies against historical data with realistic simulation
- **AI-Enhanced Analysis**: Leverage OpenAI for market summaries, risk assessment, and trade explanations
- **Risk Management**: Implement approval workflows and position limits to prevent costly mistakes
- **Portfolio Analytics**: Track performance, attribution, and tax reporting
- **Production-Ready**: Enterprise-grade code quality, testing, and maintainability

## Architecture

CryptoQuant follows a **layered architecture** designed for scalability and maintainability:

```
┌─────────────────────────────────────────────────────────┐
│                     Presentation Layer                   │
│              (Dashboard, API, Notebooks)                 │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│      (Functions, Intelligence, Execution)                │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                      Domain Layer                        │
│   (Strategies, Backtesting, Portfolio, Indicators)       │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                       Data Layer                         │
│        (Collectors, Database, Models)                    │
└─────────────────────────────────────────────────────────┘
```

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for detailed architecture documentation.

## Technology Stack

### Core
- **Python 3.14**: Modern Python with type hints and performance improvements
- **Poetry**: Dependency management and packaging
- **Pydantic**: Data validation and settings management

### Data & Analytics
- **Pandas**: Data manipulation and time-series analysis
- **Polars**: High-performance data processing
- **NumPy**: Numerical computing
- **Plotly**: Interactive visualizations

### Web & API
- **FastAPI**: Modern async web framework (future)
- **Azure Functions**: Serverless scheduled tasks

### Database
- **Azure SQL**: Cloud-based relational database
- **SQLAlchemy**: ORM and query builder
- **Alembic**: Database migrations

### External APIs
- **Coinbase Advanced API**: Market data and trade execution
- **OpenAI SDK**: AI-powered market analysis

### Code Quality
- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **Mypy**: Static type checking
- **Pytest**: Testing framework
- **Pre-commit**: Git hooks for code quality

## Repository Structure

```
CryptoQuant/
├── src/cryptoquant/          # Main application code
│   ├── config/               # Configuration management
│   ├── common/               # Shared utilities
│   ├── database/             # SQLAlchemy models and session
│   ├── collectors/           # Market data collection (Coinbase)
│   ├── indicators/           # Technical indicators (RSI, MACD, etc.)
│   ├── strategies/           # Trading strategies
│   ├── backtesting/          # Backtesting engine
│   ├── portfolio/            # Portfolio management
│   ├── execution/            # Trade execution
│   ├── intelligence/         # AI analysis (OpenAI)
│   ├── functions/            # Azure Functions
│   ├── api/                  # REST API (future)
│   └── dashboard/            # Web dashboard (future)
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
├── docs/                     # Documentation
│   ├── architecture/         # Architecture documentation
│   ├── database/             # Database design
│   ├── roadmap/              # Development roadmap
│   ├── design/               # Design documents
│   └── diagrams/             # Architecture diagrams
├── scripts/                  # Utility scripts
│   ├── bootstrap.py          # Platform initialization
│   ├── collect_market_data.py
│   ├── generate_indicators.py
│   ├── run_backtest.py
│   └── sql/                  # SQL scripts and migrations
├── notebooks/                # Jupyter notebooks for research
├── data/                     # Data storage
│   ├── raw/                  # Raw market data
│   └── processed/            # Processed datasets
├── logs/                     # Application logs
└── pyproject.toml            # Project configuration
```

## Roadmap

CryptoQuant is developed in 10 phases:

1. **Market Data Platform** - Coinbase integration, data collection, storage
2. **Indicator Engine** - Technical indicators (RSI, MACD, EMA, ATR, ADX, Bollinger Bands)
3. **Backtesting Engine** - Historical replay, performance metrics, strategy validation
4. **Strategy Engine** - Momentum, trend following, mean reversion, DCA
5. **AI Intelligence** - OpenAI integration, market analysis, confidence scoring
6. **Approval Workflow** - Email approval, audit trail, manual confirmation
7. **Trade Execution** - Coinbase order management, execution logging
8. **Portfolio Analytics** - PnL, allocation, performance, tax reporting
9. **Dashboard** - FastAPI + Plotly visualization
10. **Future Expansion** - Additional exchanges, advanced features

See [docs/roadmap/ROADMAP.md](docs/roadmap/ROADMAP.md) for detailed phase descriptions.

## Development Workflow

### Setup

```bash
# Clone the repository
git clone https://github.com/chiragkhabaria/CryptoQuant.git
cd CryptoQuant

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Set up pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cryptoquant --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/

# Run all checks (pre-commit)
pre-commit run --all-files
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Git Branch Strategy

- **`main`** - Stable production-ready code. Protected branch.
- **`dev`** - Active development branch. All feature work merges here first.
- **Feature branches** - Created from `dev` for specific features (`feature/indicator-engine`)
- **Hotfix branches** - Created from `main` for critical fixes (`hotfix/api-timeout`)

### Workflow

```bash
# Start new feature
git checkout dev
git pull origin dev
git checkout -b feature/your-feature

# Make changes, commit
git add .
git commit -m "feat: your feature description"

# Push and create PR to dev
git push origin feature/your-feature
```

## Future Enhancements

- Support for additional exchanges (Binance, Kraken, etc.)
- Advanced order types (stop-loss, trailing stops, etc.)
- Multi-asset portfolio optimization
- Real-time streaming data pipeline
- Machine learning models for price prediction
- Sentiment analysis from social media and news
- Mobile app for monitoring and approvals
- Paper trading mode for strategy testing

## Contribution Guidelines

### Code Standards

- Follow PEP 8 style guide (enforced by Black)
- Use type hints for all function signatures
- Write docstrings for all modules, classes, and functions
- Maintain test coverage above 80%
- Pass all linting and type checking

### Pull Request Process

1. Create feature branch from `dev`
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation as needed
5. Run pre-commit hooks
6. Submit PR with clear description
7. Address code review feedback
8. Merge to `dev` after approval

### Commit Messages

Follow conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (no logic change)
- `refactor:` - Code refactoring
- `test:` - Test additions or changes
- `chore:` - Build process or tooling changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

**This is a research platform, not financial advice.** Cryptocurrency trading carries substantial risk. Past performance does not guarantee future results. Always do your own research and never invest more than you can afford to lose.

---

**Built with ❤️ for quantitative research**

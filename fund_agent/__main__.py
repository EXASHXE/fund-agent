"""Allow running fund_agent as a package: python -m fund_agent"""
from fund_agent.cli import main

raise SystemExit(main())

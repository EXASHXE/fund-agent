"""AI-native Skill classes for multi-agent fund research orchestration.

Each Skill is:
- Initialized with a ToolRegistry for tool access
- Pure orchestration: reasoning + routing, NO network calls, NO LLM calls
- Takes typed inputs, returns typed outputs
- Testable with mock ToolRegistry
"""

# Superpowers-ZH 中文增强版

> 由 superpowers-zh 框架管理，与 fund-agent 业务逻辑独立。

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录。

- **brainstorming**: 在实现之前先探索用户意图、需求和设计
- **chinese-code-review**: 中文代码审查规范
- **chinese-commit-conventions**: 中文 Git 提交规范
- **chinese-documentation**: 中文技术文档写作规范
- **chinese-git-workflow**: 适配国内 Git 平台的工作流规范
- **dispatching-parallel-agents**: 2 个以上独立任务并行分发
- **executing-plans**: 执行已有书面实现计划
- **finishing-a-development-branch**: 开发分支收尾（合并/PR/清理）
- **mcp-builder**: MCP 服务器构建方法论
- **receiving-code-review**: 收到代码审查反馈后处理
- **requesting-code-review**: 完成任务后请求审查
- **subagent-driven-development**: 包含独立任务的实现计划执行
- **systematic-debugging**: 遇到 bug 时系统性调试
- **test-driven-development**: TDD 驱动开发
- **using-git-worktrees**: 隔离 git 工作树
- **using-superpowers**: 确立技能查找和使用方式
- **verification-before-completion**: 完成前必须验证
- **workflow-runner**: 直接运行 agency-orchestrator YAML 工作流
- **writing-plans**: 多步骤任务编写实现计划
- **writing-skills**: 创建/编辑/验证技能

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。

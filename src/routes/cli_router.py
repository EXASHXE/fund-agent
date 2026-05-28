"""Argument parser and command dispatch for the fund-agent CLI."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence


Handler = Callable[[argparse.Namespace], object]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="基金分析 Agent CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="生成示例配置文件")
    p_init.add_argument("-o", "--output", default="fund-portfolio.yaml")

    p_import = sub.add_parser("import", help="从 YAML 导入持仓到数据库")
    p_import.add_argument("-c", "--config", required=True, help="YAML 配置文件路径")

    p_analyze = sub.add_parser("analyze", help="完整分析流程")
    p_analyze.add_argument("-c", "--config", required=True)
    p_analyze.add_argument("-o", "--output", default="report.md")
    p_analyze.add_argument("--recommend", action="store_true", help="启用基金推荐（默认关闭）")
    p_analyze.add_argument("--stress", action="store_true", help="启用情景压力测试（默认关闭）")
    p_analyze.add_argument(
        "--snapshot-after",
        action="store_true",
        default=True,
        help="报告生成后滚动定投记录并更新配置文件",
    )
    p_analyze.add_argument(
        "--no-snapshot-after",
        dest="snapshot_after",
        action="store_false",
        help="报告生成后不滚动 fund-portfolio.yaml",
    )
    p_analyze.add_argument(
        "--news-keyword-cache",
        default=None,
        help="Agent 生成的新闻关键词缓存路径，默认 data/cache/news_keyword_profiles.json",
    )
    p_analyze.add_argument(
        "--fallback-keywords",
        action="store_true",
        help="当缺失新闻关键词缓存时，自动使用重仓股和行业词作为兜底，并缓存，而不是生成请求并退出",
    )
    p_analyze.add_argument(
        "--agent-decisions",
        default=None,
        help="与本次 evidence 口径日一致的 Agent 最终决策 JSON；提供后生成最终报告",
    )
    p_analyze.add_argument(
        "--use-agents",
        action="store_true",
        default=False,
        help="使用新的 KG+AI 流水线（Phase 2-4）替代旧版关键词流水线",
    )

    p_fetch = sub.add_parser("fetch", help="仅拉取净值数据")
    p_fetch.add_argument("-c", "--config", required=True)

    p_score = sub.add_parser("score", help="仅对数据库现有持仓评分")
    p_score.add_argument("-o", "--output", default="report.md")
    p_score.add_argument("--stress", action="store_true", help="启用情景压力测试（默认关闭）")

    p_news = sub.add_parser("news", help="新闻采集与分析")
    p_news.add_argument("-c", "--config", required=True)
    p_news.add_argument("--days", type=int, default=7)

    p_rec = sub.add_parser("recommend", help="基金推荐")
    p_rec.add_argument("-c", "--config", required=True)
    p_rec.add_argument("--top", type=int, default=5)
    p_rec.add_argument("--days", type=int, default=7)

    p_diag = sub.add_parser("diagnose", help="单基金诊断")
    p_diag.add_argument("code", help="6位基金代码")

    p_snap = sub.add_parser("snapshot", help="更新持仓 YAML（含定投记录+备份）")
    p_snap.add_argument("-c", "--config", required=True, help="YAML 配置文件路径")

    p_ui = sub.add_parser("ui", help="启动交互式管理界面 (Streamlit)")
    p_ui.add_argument("-c", "--config", default="fund-portfolio.yaml", help="YAML 配置文件路径")
    p_ui.add_argument("-p", "--port", type=int, default=8501, help="端口号 (默认: 8501)")

    return parser


def dispatch(args: argparse.Namespace, handlers: Mapping[str, Handler], parser: argparse.ArgumentParser):
    handler = handlers.get(args.command or "")
    if handler is None:
        parser.print_help()
        return None
    return handler(args)


def run_cli(handlers: Mapping[str, Handler], argv: Sequence[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, handlers, parser)

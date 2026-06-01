# News Research Source Quality Policy

`news_research` converts host MCP results into `SoftEvidence`. Source quality is
owned by the host and should be reflected in confidence.

## Host Should Prefer

- primary filings, exchange notices, fund company notices, or regulator notices;
- reputable financial news sources;
- timestamped items with stable URLs or source IDs;
- items that map clearly to the fund, holding, sector, or macro topic.

## Host Should Downgrade

- duplicated syndication;
- unsourced summaries;
- stale items;
- promotional content;
- unclear entity mapping.

## Runtime Behavior

The runtime should not independently fetch, rank, or verify sources. It should
convert structured host results into `SoftEvidence` with source metadata.

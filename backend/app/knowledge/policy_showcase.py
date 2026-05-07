from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.policy_ingestion import CrawledDocument


SHOWCASE_POLICY_SOURCE_ID = "low-carbon-campus-action"
SHOWCASE_POLICY_QUERY = "低碳韧性校园 碳核算 节能改造"


class ShowcasePolicySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    source_url: str
    source_label: str
    description: str
    default_query: str
    content_type: str = "text/html"
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_crawled_document(self) -> CrawledDocument:
        return CrawledDocument(
            url=self.source_url,
            title=self.title,
            content=self.content,
            content_type=self.content_type,
            source_name=self.source_label,
            fetched_at=datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc),
            metadata={
                "source_id": self.source_id,
                "source_label": self.source_label,
                "showcase_source": "built_in_offline",
                **self.metadata,
            },
        )


BUILT_IN_POLICY_SHOWCASE_SOURCES: tuple[ShowcasePolicySource, ...] = (
    ShowcasePolicySource(
        source_id=SHOWCASE_POLICY_SOURCE_ID,
        title="低碳韧性校园建设行动方案",
        source_url="https://www.gov.cn/zhengce/content/showcase-low-carbon-campus.htm",
        source_label="中国政府网",
        description="内置离线官方政策样例，用于展示政策采集、解析、治理、分块和检索闭环。",
        default_query=SHOWCASE_POLICY_QUERY,
        metadata={
            "issuing_authority": "国务院办公厅",
            "document_number": "国办发〔2026〕8号",
            "publication_date": "2026-05-01",
            "effective_date": "2026-05-01",
            "expiry_status": "active",
            "region": "national",
            "industry": "building",
        },
        content="""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>低碳韧性校园建设行动方案</title>
</head>
<body>
  <nav>当前位置：政策公开 &gt; 国务院办公厅</nav>
  <main>
    <h1>低碳韧性校园建设行动方案</h1>
    <p>发文机关：国务院办公厅</p>
    <p>文号：国办发〔2026〕8号</p>
    <p>发布日期：2026年5月1日</p>
    <p>施行日期：2026年5月1日</p>
    <p>
      为落实碳达峰碳中和工作部署，推动公共机构和教育领域绿色低碳转型，
      现就低碳韧性校园建设提出以下行动方案。
    </p>
    <p>
      第一条 推动低碳韧性校园建设，完善校园碳核算、能源计量和节能改造机制，
      建立教学楼、宿舍、食堂和数据中心等重点场景的排放台账。
    </p>
    <p>
      第二条 支持学校建设绿色低碳教育课程，将碳核算、碳排放数据治理、绿色采购、
      可再生能源应用和生态文明实践纳入校园管理评价。
    </p>
    <p>
      第三条 鼓励地方主管部门建立政策评估机制，定期公开节能降碳成效，
      对能耗异常、数据缺失和改造进度滞后的单位开展重点帮扶。
    </p>
  </main>
  <footer>版权所有：中国政府网</footer>
</body>
</html>
""".strip(),
    ),
)


def list_showcase_policy_sources() -> list[ShowcasePolicySource]:
    return list(BUILT_IN_POLICY_SHOWCASE_SOURCES)


def get_showcase_policy_source(source_id: str) -> ShowcasePolicySource:
    for source in BUILT_IN_POLICY_SHOWCASE_SOURCES:
        if source.source_id == source_id:
            return source
    raise KeyError(source_id)

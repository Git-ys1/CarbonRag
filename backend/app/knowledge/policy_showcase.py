from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.policy_ingestion import CrawledDocument


SHOWCASE_POLICY_SOURCE_ID = "low-carbon-campus-action"
SHOWCASE_POLICY_QUERY = "低碳韧性校园建设如何开展碳核算和节能改造？"


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
                "showcase_source": "demo_synthetic",
                "source_kind": "demo_showcase",
                "is_synthetic": "true",
                "citation_source_type": "public_policy_demo",
                "citation_disclaimer": "内置演示样例，不代表真实官方政策，不可作为官方政策依据引用。",
                **self.metadata,
            },
        )


BUILT_IN_POLICY_SHOWCASE_SOURCES: tuple[ShowcasePolicySource, ...] = (
    ShowcasePolicySource(
        source_id=SHOWCASE_POLICY_SOURCE_ID,
        title="CarbonRag 低碳韧性校园建设演示样例",
        source_url="carbonrag://showcase/policy/low-carbon-campus-action",
        source_label="CarbonRag 内置演示样例",
        description="内置离线合成样例，用于展示采集、解析、治理、分块和检索闭环；不是官方政策文件。",
        default_query=SHOWCASE_POLICY_QUERY,
        metadata={
            "showcase_source": "demo_synthetic",
            "source_kind": "demo_showcase",
            "is_synthetic": "true",
            "citation_source_type": "public_policy_demo",
            "citation_disclaimer": "内置演示样例，不代表真实官方政策，不可作为官方政策依据引用。",
            "issuing_authority": "CarbonRag Demo",
            "document_number": "DEMO-SHOWCASE-2026-001",
            "publication_date": "2026-05-01",
            "effective_date": "2026-05-01",
            "expiry_status": "unknown",
            "region": "demo",
            "industry": "building",
        },
        content="""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>CarbonRag 低碳韧性校园建设演示样例</title>
</head>
<body>
  <main>
    <h1>CarbonRag 低碳韧性校园建设演示样例</h1>
    <p>来源：CarbonRag 内置演示样例</p>
    <p>样例编号：DEMO-SHOWCASE-2026-001</p>
    <p>发布日期：2026年5月1日</p>
    <p>说明：本文档为合成演示资料，不代表真实官方政策文件，不可作为官方政策依据引用。</p>
    <p>
      为展示 CarbonRag 政策知识三段式摄取能力，本样例围绕低碳韧性校园建设，
      覆盖碳核算、能源计量、节能改造、绿色采购和数据治理等演示主题。
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
      第三条 鼓励管理部门建立演示评估机制，定期公开节能降碳成效，
      对能耗异常、数据缺失和改造进度滞后的单位开展重点帮扶。
    </p>
  </main>
  <footer>CarbonRag 内置演示样例，不代表任何官方发布主体。</footer>
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

import json

from app.carbon.explain import CarbonExplainer
from app.carbon.schemas import StoredCarbonCalculation
from app.report.schemas import ReportCitation, ReportSourceSummary, ReportType
from app.report.templates import ReportTemplate
from app.schemas.ask import AskCitation
from app.session.schemas import SessionDetail, SessionMessage


class ReportComposer:
    def __init__(self, *, explainer: CarbonExplainer | None = None) -> None:
        self.explainer = explainer or CarbonExplainer()

    def collect_message_citations(self, messages: list[SessionMessage]) -> list[ReportCitation]:
        seen: set[tuple[str, str, str]] = set()
        citations: list[ReportCitation] = []

        for message in messages:
            for citation in message.citations:
                key = (citation.source_type, citation.doc_id, citation.chunk_id)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(self._from_ask_citation(citation))

        return citations

    def collect_carbon_citations(self, carbon_result: StoredCarbonCalculation | None) -> list[ReportCitation]:
        if carbon_result is None:
            return []

        return [
            ReportCitation(
                source_type="carbon_factor",
                title=f"排放因子 {citation.factor_id}",
                source=citation.source,
                source_url=citation.source_url,
                snippet=f"使用排放因子 {citation.factor_id} 进行核算说明。",
                chunk_id=None,
                factor_id=citation.factor_id,
            )
            for citation in carbon_result.citations
        ]

    def build_source_summary(self, citations: list[ReportCitation]) -> ReportSourceSummary:
        return ReportSourceSummary(
            public_policy_count=sum(1 for item in citations if item.source_type == "public_policy"),
            public_policy_demo_count=sum(1 for item in citations if item.source_type == "public_policy_demo"),
            private_sample_count=sum(1 for item in citations if item.source_type == "private_sample"),
            carbon_factor_count=sum(1 for item in citations if item.source_type == "carbon_factor"),
            total_citation_count=len(citations),
        )

    def build_provider_user_input(
        self,
        *,
        template: ReportTemplate,
        session: SessionDetail,
        selected_messages: list[SessionMessage],
        citations: list[ReportCitation],
        carbon_result: StoredCarbonCalculation | None,
        requested_title: str | None,
    ) -> str:
        carbon_payload = None
        if carbon_result is not None:
            carbon_payload = {
                "trace_id": carbon_result.trace_id,
                "period_label": carbon_result.period_label,
                "electricity_kwh": carbon_result.electricity_kwh,
                "natural_gas_m3": carbon_result.natural_gas_m3,
                "diesel_l": carbon_result.diesel_l,
                "total_emission_kgco2e": carbon_result.total_emission_kgco2e,
                "breakdown": [item.model_dump() for item in carbon_result.breakdown],
                "formula_summary": self.explainer.build_formula_summary(carbon_result.breakdown),
            }

        payload = {
            "session": {"session_id": session.session_id, "title": session.title},
            "requested_title": requested_title,
            "report_type": template.report_type,
            "template_name": template.display_name,
            "template_sections": list(template.sections),
            "selected_messages": [
                {
                    "message_id": message.message_id,
                    "content": message.content,
                    "trace_id": message.trace_id,
                }
                for message in selected_messages
            ],
            "citations": [item.model_dump() for item in citations],
            "carbon_result": carbon_payload,
            "rules": [
                "Use only the supplied context.",
                "Do not invent evidence or enterprise facts.",
                "When mixed sources exist, separate policy basis from enterprise sample observations.",
                "Return concise Chinese report text.",
            ],
            "output_contract": {
                "title": "string",
                "sections": [{"heading": heading, "body": "string"} for heading in template.sections],
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def build_provider_system_prompt(self, template: ReportTemplate) -> str:
        return (
            "You are CarbonRag's controlled report generator. "
            f"Generate a {template.display_name} using only the supplied JSON context. "
            "Return valid JSON only with keys title and sections. "
            "Each section must contain heading and body. "
            "The section headings must exactly match template_sections in the same order. "
            "Do not wrap the JSON in markdown fences."
        )

    def build_references_markdown(self, citations: list[ReportCitation]) -> str:
        if not citations:
            return "暂无依据。"

        lines: list[str] = []
        for citation in citations:
            if citation.source_type == "carbon_factor":
                lines.append(
                    f"- [{citation.source_type}] {citation.title} | 来源：{citation.source} | factor_id：{citation.factor_id or '-'}"
                )
                if citation.source_url:
                    lines.append(f"  - 链接：{citation.source_url}")
            else:
                lines.append(
                    f"- [{citation.source_type}] {citation.title} | 来源：{citation.source} | 片段：{citation.snippet}"
                )
                if citation.source_url:
                    lines.append(f"  - 链接：{citation.source_url}")
        return "\n".join(lines)

    @staticmethod
    def build_default_title(report_type: ReportType, session_title: str) -> str:
        title_map = {
            "policy_summary": "政策解读摘要",
            "mixed_analysis": "政策与企业样例初步分析",
            "carbon_summary": "碳核算结果说明",
        }
        return f"{title_map[report_type]} - {session_title}"

    @staticmethod
    def _from_ask_citation(citation: AskCitation) -> ReportCitation:
        return ReportCitation(
            source_type=citation.source_type,
            title=citation.title,
            source=citation.source,
            source_url=citation.source_url,
            snippet=citation.snippet,
            chunk_id=citation.chunk_id,
        )

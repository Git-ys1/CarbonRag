from __future__ import annotations

from typing import Any, Mapping

from app.ai_runtime.schemas.tool import ToolResult
from app.ai_runtime.tools.base import BaseTool, ToolDefinition
from app.report.export.schemas import CreateReportExportRequest
from app.report.export.service import ReportExportService
from app.report.schemas import CreateReportRequest
from app.report.service import ReportProviderFailure, ReportService, ReportValidationError


REPORT_FILE_INTENT_KEYWORDS = (
    "生成报告",
    "导出报告",
    "下载报告",
    "创建报告",
    "新建报告",
    "报告文件",
    "可下载报告",
    "生成文件",
    "导出文件",
    "创建文件",
    "新建文件",
    "保存为",
    "整理成报告",
    "写成报告",
    "做成报告",
    "整理成文件",
    "写成文件",
    "做成文件",
    "下载链接",
    "文件链接",
    "可下载",
    "word文档",
    "word 文件",
    "docx 文件",
    "report file",
    "create report",
    "export report",
    "download report",
    "download link",
)


class ReportFileGenerateTool(BaseTool):
    def __init__(
        self,
        *,
        report_service: ReportService | None = None,
        export_service: ReportExportService | None = None,
    ) -> None:
        self.report_service = report_service or ReportService()
        self.export_service = export_service or ReportExportService(report_service=self.report_service)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_file_generate",
            description="Generate a controlled CarbonRag report and export it as DOCX/PDF files.",
            category="report_generation",
        )

    def invoke(
        self,
        *,
        arguments: Mapping[str, Any],
        context: Mapping[str, Any],
        trace_id: str,
    ) -> ToolResult:
        del context
        question = str(arguments.get("question") or arguments.get("user_input") or "").strip()
        payload = arguments.get("payload") if isinstance(arguments.get("payload"), dict) else {}
        owner_user_id = str(payload.get("owner_user_id") or "").strip()
        session_id = str(payload.get("session_id") or "").strip()
        formats = _infer_formats(question)
        report_type = _infer_report_type(question)
        title = _infer_title(question, report_type=report_type)

        if not owner_user_id or not session_id:
            return _error_result(
                trace_id=trace_id,
                message="缺少 owner_user_id 或 session_id，无法在聊天中生成报告文件。",
                error_stage="runtime_payload",
                question=question,
                formats=formats,
                report_type=report_type,
            )

        if not _looks_like_report_file_intent(question):
            return _error_result(
                trace_id=trace_id,
                message="本轮问题没有明确的报告文件生成意图。",
                error_stage="intent_detection",
                question=question,
                formats=formats,
                report_type=report_type,
            )

        warnings: list[str] = []
        try:
            report = self.report_service.create_report(
                owner_user_id=owner_user_id,
                payload=CreateReportRequest(
                    session_id=session_id,
                    report_type=report_type,
                    title=title,
                ),
            )
            export_response = self.export_service.create_exports(
                owner_user_id=owner_user_id,
                report_id=report.report_id,
                payload=CreateReportExportRequest(
                    formats=formats,
                    force_regenerate=True,
                ),
            )
        except ReportValidationError as exc:
            try:
                report = self.report_service.create_conversation_draft_report(
                    owner_user_id=owner_user_id,
                    session_id=session_id,
                    report_type=report_type,
                    title=f"{title}（即时草稿）",
                    request_text=question,
                    validation_warning=str(exc),
                )
                export_response = self.export_service.create_exports(
                    owner_user_id=owner_user_id,
                    report_id=report.report_id,
                    payload=CreateReportExportRequest(
                        formats=formats,
                        force_regenerate=True,
                    ),
                )
                warnings.append(f"正式报告校验未满足（{exc}），已先生成可下载即时草稿。")
            except Exception as fallback_exc:  # pragma: no cover - defensive fallback boundary
                return _error_result(
                    trace_id=trace_id,
                    message=f"{exc}; fallback draft failed: {fallback_exc}",
                    error_stage="source_validation",
                    question=question,
                    formats=formats,
                    report_type=report_type,
                )
        except ReportProviderFailure as exc:
            return _error_result(
                trace_id=trace_id,
                message=str(exc),
                error_stage="report_generation_provider",
                question=question,
                formats=formats,
                report_type=report_type,
            )
        except KeyError as exc:
            return _error_result(
                trace_id=trace_id,
                message=f"找不到生成报告所需对象：{exc}",
                error_stage="missing_source",
                question=question,
                formats=formats,
                report_type=report_type,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            return _error_result(
                trace_id=trace_id,
                message=str(exc),
                error_stage="unexpected_error",
                question=question,
                formats=formats,
                report_type=report_type,
            )

        files = [item.model_dump(mode="json") for item in export_response.files]
        return ToolResult(
            name=self.definition.name,
            status="success",
            output={
                "skill": {
                    "name": "report-file-generation",
                    "triggered": True,
                },
                "intent_detected": True,
                "report_id": report.report_id,
                "report_type": report.report_type,
                "title": report.title,
                "formats": formats,
                "files": files,
                "download_urls": [item["download_url"] for item in files],
                "content_preview": report.content[:800],
                "warnings": warnings,
            },
            metadata={"trace_id": trace_id, "file_count": len(files)},
        )


def _looks_like_report_file_intent(question: str) -> bool:
    normalized = question.lower()
    if any(keyword in normalized for keyword in REPORT_FILE_INTENT_KEYWORDS):
        return True
    file_words = ("word", "docx", "pdf", "报告文件", "文件")
    action_words = ("生成", "创建", "新建", "导出", "下载", "保存", "整理", "做成", "写成", "给我", "来一份", "create", "export", "download", "save")
    return any(word in normalized for word in file_words) and any(word in normalized for word in action_words)


def _infer_formats(question: str) -> list[str]:
    normalized = question.lower()
    formats = ["docx"]
    if "pdf" in normalized:
        formats.append("pdf")
    return list(dict.fromkeys(formats))


def _infer_report_type(question: str) -> str:
    normalized = question.lower()
    if any(keyword in normalized for keyword in ("碳核算", "碳排放", "排放量", "核算结果", "carbon")):
        return "carbon_summary"
    if any(keyword in normalized for keyword in ("上传", "附件", "知识库", "企业", "综合", "mixed", "样例")):
        return "mixed_analysis"
    return "policy_summary"


def _infer_title(question: str, *, report_type: str) -> str:
    title_map = {
        "policy_summary": "对话政策摘要报告",
        "mixed_analysis": "对话综合分析报告",
        "carbon_summary": "对话碳核算报告",
    }
    if "pdf" in question.lower():
        suffix = "（含 PDF 导出）"
    else:
        suffix = ""
    return f"{title_map.get(report_type, '对话报告')}{suffix}"


def _error_result(
    *,
    trace_id: str,
    message: str,
    error_stage: str,
    question: str,
    formats: list[str],
    report_type: str,
) -> ToolResult:
    return ToolResult(
        name="report_file_generate",
        status="error",
        output={
            "skill": {
                "name": "report-file-generation",
                "triggered": True,
            },
            "intent_detected": True,
            "report_generated": False,
            "error_stage": error_stage,
            "error_message": message,
            "question": question,
            "formats": formats,
            "report_type": report_type,
            "files": [],
            "warnings": [
                "报告文件未生成。请先让聊天产生带 citation 的回答，或先完成碳核算结果，再要求导出报告文件。"
            ],
        },
        metadata={"trace_id": trace_id, "error_stage": error_stage},
    )

from __future__ import annotations

from pathlib import Path

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    MarkItDown = None


class MarkdownConversionError(RuntimeError):
    pass


def convert_to_markdown(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return source_path.read_text(encoding="utf-8")

    if MarkItDown is None:
        raise MarkdownConversionError(
            "MarkItDown 未安装，请安装 Python 依赖后再上传非 Markdown/TXT 文件。"
        )

    try:
        result = MarkItDown(enable_plugins=False).convert(str(source_path))
    except Exception as error:
        raise MarkdownConversionError(f"MarkItDown 转换失败：{error}") from error

    markdown = getattr(result, "text_content", "")
    if not isinstance(markdown, str):
        markdown = str(markdown or "")

    return markdown

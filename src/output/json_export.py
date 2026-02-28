"""JSON export for debate results"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from slugify import slugify

if TYPE_CHECKING:
    from ..debate.orchestrator import DebateResult


class JSONExporter:
    """Exports debate results to JSON format"""

    def __init__(self, output_dir: str = "debates"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_filename(self, question: str, timestamp: datetime) -> str:
        """Generate filename from question and timestamp"""
        date_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        slug = slugify(question[:50], max_length=50)
        return f"debate_{date_str}_{slug}.json"

    def export(self, result: DebateResult) -> str:
        """Export debate result to JSON file"""
        filename = self.generate_filename(result.question, result.started_at)
        filepath = self.output_dir / filename

        data = result.to_dict()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return str(filepath)

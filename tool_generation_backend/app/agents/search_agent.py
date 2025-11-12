"""
Search Agent for exploring library documentation and repositories.

This agent uses LLM backend (Codex or Claude Code) to search for APIs,
code examples, and documentation relevant to the tool requirements.
"""

import logging
from pathlib import Path
from typing import List

from app.config import get_settings
from app.models.pipeline_v2 import (
    ToolDefinition,
    ExplorationReport
)
from app.utils.llm_backend import execute_llm_browse

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Agent for exploring library documentation and repositories.

    Uses LLM backend (Codex or Claude Code) to:
    1. Identify relevant library
    2. Search documentation
    3. Extract API function references
    4. Find code examples
    5. Generate exploration report
    """

    def __init__(self, available_packages: List[str]):
        """Initialize the search agent.

        Args:
            available_packages: List of available package names for documentation search
        """
        self.settings = get_settings()
        self.available_libraries = available_packages
        logger.info(f"Initialized search agent with {len(self.available_libraries)} libraries: {self.available_libraries}")

    async def explore(
        self,
        tool_definition: ToolDefinition,
        open_questions: List[str],
        task_id: str = "_",
        job_id: str = "_"
    ) -> ExplorationReport:
        """
        Explore documentation to find relevant APIs and examples.

        Args:
            tool_definition: Tool specification from Intake Agent
            open_questions: Questions to investigate
            task_id: Task ID for V2 pipeline (for saving searches to task dir)
            job_id: Job ID for V2 pipeline (for saving searches to job dir)

        Returns:
            ExplorationReport: Consolidated findings from documentation
        """
        try:
            logger.info(f"Starting documentation exploration for: {tool_definition.name}")

            # Step 1: Write questions to file for reference
            open_questions_file = self._write_questions_file(open_questions, job_id, task_id)

            # Step 2: Execute documentation search across all available libraries
            # Let the LLM decide which libraries are relevant
            # Note: We no longer parse the markdown results - downstream agents read the file directly
            api_refs_file = ""

            logger.info(f"Searching documentation across {len(self.available_libraries)} libraries with {len(open_questions)} questions")
            # Pass all available libraries to the LLM
            browse_result = await execute_llm_browse(
                libraries=self.available_libraries,
                questions=open_questions,
                questions_file_path=open_questions_file,
                task_id=task_id,
                job_id=job_id
            )

            if browse_result.success:
                # Track the API reference file (markdown format)
                if browse_result.output_file:
                    api_refs_file = browse_result.output_file
                    logger.info(f"Search results saved to: {api_refs_file}")
            else:
                logger.warning(f"Batch browse query failed - {browse_result.error}")

            logger.info(f"Exploration complete. Results saved to markdown file: {api_refs_file}")

            # Step 3: Create exploration report with file reference
            # Downstream agents will read the markdown file directly
            report = ExplorationReport(
                api_refs_file=api_refs_file or f"{self.settings.searches_path}/api_refs_unknown.md",
            )

            return report

        except Exception as e:
            logger.error(f"Error in search agent exploration: {e}")
            # Return empty report with error indication
            return ExplorationReport(
                api_refs_file=f"error: {str(e)}",
            )

    def _write_questions_file(
        self,
        open_questions: List[str],
        job_id: str,
        task_id: str
    ) -> str:
        """
        Write open questions to file.

        Args:
            open_questions: Questions from Intake Agent
            job_id: Job identifier
            task_id: Task identifier

        Returns:
            str: Path to the created questions file
        """

        # Create search directory
        search_dir = Path(self.settings.tools_path) / job_id / task_id / "search"
        search_dir.mkdir(parents=True, exist_ok=True)

        # Create questions file
        questions_file = search_dir / "questions.txt"

        try:
            with open(questions_file, 'w') as f:
                f.write("# Open Questions from Intake Agent\n\n")
                for i, question in enumerate(open_questions, 1):
                    f.write(f"{i}. {question}\n")

            logger.info(f"Wrote questions to: {questions_file}")
            return str(questions_file)

        except Exception as e:
            logger.error(f"Failed to write questions file: {e}")
            return ""

    async def cleanup(self):
        """Clean up search agent resources if needed."""
        logger.info("Search agent cleanup completed")

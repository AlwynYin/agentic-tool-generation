"""
Search Agent for exploring library documentation and repositories.

This agent uses LLM backend (Codex or Claude Code) to search for APIs,
code examples, and documentation relevant to the tool requirements.
"""

import logging
import json
from pathlib import Path
from typing import List

from app.config import get_settings
from app.models.pipeline_v2 import (
    ToolDefinition,
    ExplorationReport,
    ApiFunction,
    CodeExample,
    ParameterSpec,
    OutputSpec,
    QuestionAnswer
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
            apis = []
            examples = []
            paths = []
            entry_points = []
            question_answers = []
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
                # Parse the browse result and extract APIs and question answers
                parsed = self._parse_browse_result(browse_result)
                apis.extend(parsed["apis"])
                examples.extend(parsed["examples"])
                paths.extend(parsed["paths"])
                entry_points.extend(parsed["entry_points"])
                question_answers.extend(parsed["question_answers"])

                # Track the API reference file
                if browse_result.output_file:
                    api_refs_file = browse_result.output_file
            else:
                logger.warning(f"Batch browse query failed - {browse_result.error}")

            # Step 3: Deduplicate and consolidate findings
            paths = list(set(paths))
            entry_points = list(set(entry_points))

            logger.info(f"Exploration complete: {len(apis)} APIs, {len(examples)} examples, {len(question_answers)} answers")

            # Step 4: Create exploration report
            report = ExplorationReport(
                apis=apis,
                paths=paths,
                entry_points=entry_points,
                examples=examples,
                api_refs_file=api_refs_file or f"{self.settings.searches_path}/api_refs_unknown.json",
                question_answers=question_answers
            )

            return report

        except Exception as e:
            logger.error(f"Error in search agent exploration: {e}")
            # Return empty report with error indication
            return ExplorationReport(
                apis=[],
                paths=[],
                entry_points=[],
                examples=[],
                api_refs_file=f"error: {str(e)}",
                question_answers=[]
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

    def _parse_browse_result(self, browse_result) -> dict:
        """
        Parse browse result from execute_llm_browse.

        Args:
            browse_result: ApiBrowseResult from execute_llm_browse

        Returns:
            dict: Parsed APIs, examples, paths, entry_points, question_answers
        """

        apis = []
        examples = []
        paths = []
        entry_points = []
        question_answers = []

        try:
            # Parse the JSON search results
            if browse_result.search_results:
                search_data = json.loads(browse_result.search_results)

                # Extract question answers (new format from Option 2)
                if "question_answers" in search_data:
                    for qa in search_data["question_answers"]:
                        question_answers.append(QuestionAnswer(
                            question=qa.get("question", ""),
                            type=qa.get("type", "api_discovery"),
                            answer=qa.get("answer", ""),
                            library=qa.get("library"),
                            code_example=qa.get("code_example")
                        ))

                # Extract API functions
                api_functions_data = search_data.get("api_functions", [])
                for api_func in api_functions_data:
                    # Convert to our ApiFunction model
                    apis.append(ApiFunction(
                        function_name=api_func.get("function_name", "unknown"),
                        description=api_func.get("description", ""),
                        input_schema=[
                            ParameterSpec(
                                name=param.get("name", ""),
                                type=param.get("type", "Any"),
                                description=param.get("description", ""),
                                default=param.get("default"),
                                required=param.get("required", True)
                            )
                            for param in api_func.get("input_schema", [])
                        ],
                        output_schema=OutputSpec(
                            type=api_func.get("output_schema", {}).get("type", "Any"),
                            description=api_func.get("output_schema", {}).get("description", ""),
                            units=api_func.get("output_schema", {}).get("units")
                        ),
                        examples=[
                            CodeExample(
                                code=ex.get("code", ""),
                                description=ex.get("description", ""),
                                source=ex.get("source", "documentation")
                            )
                            for ex in api_func.get("examples", [])
                        ]
                    ))

                    # Extract entry point (main function to call)
                    entry_points.append(api_func.get("function_name", "unknown"))

                    # Extract examples from API functions
                    for ex in api_func.get("examples", []):
                        examples.append(CodeExample(
                            code=ex.get("code", ""),
                            description=ex.get("description", ""),
                            source=ex.get("source", "documentation")
                        ))

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from browse result: {e}")
        except Exception as e:
            logger.error(f"Error parsing browse result: {e}")

        return {
            "apis": apis,
            "examples": examples,
            "paths": paths,
            "entry_points": entry_points,
            "question_answers": question_answers
        }

    async def cleanup(self):
        """Clean up search agent resources if needed."""
        logger.info("Search agent cleanup completed")

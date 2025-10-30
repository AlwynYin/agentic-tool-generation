"""
Search Agent for exploring library documentation and repositories.

This agent uses Codex CLI to search for APIs, code examples, and
documentation relevant to the tool requirements.
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
    OutputSpec
)
from app.utils.codex_utils import execute_codex_browse

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Agent for exploring library documentation and repositories.

    Uses Codex CLI to:
    1. Identify relevant library
    2. Search documentation
    3. Extract API function references
    4. Find code examples
    5. Generate exploration report
    """

    def __init__(self):
        """Initialize the search agent."""
        self.settings = get_settings()
        self.available_libraries = ["rdkit", "ase", "pymatgen", "pyscf", "orca"]

    async def explore(
        self,
        tool_definition: ToolDefinition,
        open_questions: List[str],
        task_id: str = None,
        job_id: str = None
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

            # Step 1: Identify relevant library
            library = self._identify_library(tool_definition, open_questions)
            logger.info(f"Identified library: {library}")

            # Step 2: Build search queries from tool definition and open questions
            queries = self._build_search_queries(tool_definition, open_questions)
            logger.info(f"Generated {len(queries)} search queries")

            # Step 3: Execute documentation search
            # Execute all queries in a single batch call
            apis = []
            examples = []
            paths = []
            entry_points = []
            api_refs_file = ""

            logger.info(f"Searching documentation with {len(queries)} queries in batch")
            # Pass all queries at once to execute_codex_browse
            browse_result = await execute_codex_browse(library, queries, task_id=task_id, job_id=job_id)

            if browse_result.success:
                # Parse the browse result and extract APIs
                parsed = self._parse_browse_result(browse_result)
                apis.extend(parsed["apis"])
                examples.extend(parsed["examples"])
                paths.extend(parsed["paths"])
                entry_points.extend(parsed["entry_points"])

                # Track the API reference file
                if browse_result.output_file:
                    api_refs_file = browse_result.output_file
            else:
                logger.warning(f"Batch browse query failed - {browse_result.error}")

            # Step 4: Deduplicate and consolidate findings
            apis = self._deduplicate_apis(apis)
            examples = self._deduplicate_examples(examples)
            paths = list(set(paths))
            entry_points = list(set(entry_points))

            logger.info(f"Exploration complete: {len(apis)} APIs, {len(examples)} examples")

            # Step 5: Create exploration report
            report = ExplorationReport(
                apis=apis,
                paths=paths,
                entry_points=entry_points,
                examples=examples,
                api_refs_file=api_refs_file or f"{self.settings.searches_path}/{library}_api_refs_unknown.json"
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
                api_refs_file=f"error: {str(e)}"
            )

    def _identify_library(
        self,
        tool_definition: ToolDefinition,
        open_questions: List[str]
    ) -> str:
        """
        Identify which chemistry library is most relevant.

        Args:
            tool_definition: Tool specification
            open_questions: Questions from intake

        Returns:
            str: Library name (rdkit, ase, pymatgen, pyscf, orca)
        """
        # Simple heuristic-based library identification
        # In a more advanced version, this could use an LLM

        combined_text = (
            tool_definition.name + " " +
            tool_definition.signature + " " +
            tool_definition.docstring + " " +
            " ".join(open_questions)
        ).lower()

        # Library keyword patterns
        library_keywords = {
            "rdkit": ["smiles", "molecule", "molecular weight", "descriptor", "fingerprint", "mol", "inchi"],
            "ase": ["atom", "geometry", "optimize", "calculator", "trajectory", "xyz", "structure"],
            "pymatgen": ["crystal", "structure", "lattice", "material", "cif", "poscar", "band"],
            "pyscf": ["dft", "scf", "hartree", "fock", "homo", "lumo", "orbital", "quantum", "basis"],
            "orca": ["orca", "single point", "coupled cluster", "ccsd"]
        }

        # Score each library
        scores = {lib: 0 for lib in self.available_libraries}
        for lib, keywords in library_keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    scores[lib] += 1

        # Return library with highest score (default to rdkit if tie)
        best_library = max(scores.items(), key=lambda x: x[1])
        logger.info(f"Library scores: {scores}")

        if best_library[1] == 0:
            logger.warning("No clear library match found, defaulting to rdkit")
            return "rdkit"

        return best_library[0]

    def _build_search_queries(
        self,
        tool_definition: ToolDefinition,
        open_questions: List[str]
    ) -> List[str]:
        """
        Build search queries from tool definition and open questions.

        Args:
            tool_definition: Tool specification
            open_questions: Questions to investigate

        Returns:
            List[str]: Search queries for documentation
        """
        queries = []

        # Convert open questions to queries
        for question in open_questions[:3]:  # Limit to first 3 questions
            # Clean up question format
            query = question.replace("?", "").strip()
            queries.append(f"Documentation for: {query}")

        return queries

    def _parse_browse_result(self, browse_result) -> dict:
        """
        Parse browse result from execute_codex_browse.

        Args:
            browse_result: ApiBrowseResult from execute_codex_browse

        Returns:
            dict: Parsed APIs, examples, paths, entry_points
        """
        apis = []
        examples = []
        paths = []
        entry_points = []

        try:
            # The browse_result has api_functions, examples, relevant_files
            if hasattr(browse_result, 'api_functions') and browse_result.api_functions:
                for api_func in browse_result.api_functions:
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

            # Extract examples
            if hasattr(browse_result, 'examples') and browse_result.examples:
                for ex in browse_result.examples:
                    examples.append(CodeExample(
                        code=ex.get("code", ""),
                        description=ex.get("description", ""),
                        source=ex.get("source", "documentation")
                    ))

            # Extract relevant file paths
            if hasattr(browse_result, 'relevant_files') and browse_result.relevant_files:
                paths.extend(browse_result.relevant_files)

        except Exception as e:
            logger.error(f"Error parsing browse result: {e}")

        return {
            "apis": apis,
            "examples": examples,
            "paths": paths,
            "entry_points": entry_points
        }

    def _deduplicate_apis(self, apis: List[ApiFunction]) -> List[ApiFunction]:
        """Deduplicate API functions by function_name."""
        seen = set()
        unique_apis = []
        for api in apis:
            if api.function_name not in seen:
                seen.add(api.function_name)
                unique_apis.append(api)
        return unique_apis

    def _deduplicate_examples(self, examples: List[CodeExample]) -> List[CodeExample]:
        """Deduplicate code examples by code content."""
        seen = set()
        unique_examples = []
        for example in examples:
            code_hash = hash(example.code)
            if code_hash not in seen:
                seen.add(code_hash)
                unique_examples.append(example)
        return unique_examples

    async def cleanup(self):
        """Clean up search agent resources if needed."""
        logger.info("Search agent cleanup completed")

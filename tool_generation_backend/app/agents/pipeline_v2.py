"""
Multi-agent iterative pipeline for tool generation (V2).

This pipeline replaces the single-agent V1 pipeline with a multi-agent
approach featuring iterative refinement.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.models.specs import UserToolRequirement
from app.models.tool_generation import ToolGenerationOutput, ToolGenerationResult, ToolGenerationFailure
from app.models.pipeline_v2 import IterationData, IterationSummary
from app.utils.pytest_runner import get_pytest_runner
from app.utils.code_parser import parse_function_from_code, extract_description_from_code
from app.utils.task_logger import get_task_logger, log_divider, log_multiline
from app.agents.intake_agent import IntakeAgent
from app.agents.search_agent import SearchAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.implementer_agent import ImplementerAgent
from app.agents.test_agent import TestAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.summarizer_agent import SummarizerAgent

logger = logging.getLogger(__name__)


class ToolGenerationPipelineV2:
    """
    Multi-agent iterative pipeline for robust tool generation.

    Pipeline Flow:
    1. Intake → Validate and synthesize Tool Definition
    2. Search → Explore APIs and patterns
    3. Plan → Create step-by-step implementation plan
    4-9. Iterative Refinement Loop (max iterations):
        4. Implement → Generate tool code
        5. Test → Generate test suite
        6. Run Tests → Execute pytest
        7. Review → Analyze code and results
        8. Summarize → Compress iteration (if rejected)
        9. Loop back to step 4 with feedback
    """

    def __init__(self):
        """Initialize the pipeline with all agents."""
        self.settings = get_settings()

        # Load available packages from repository service (singleton)
        # Import here to avoid circular import (dependencies -> task_service -> pipeline_v2 -> dependencies)
        from app.dependencies import get_repository_service
        repository_service = get_repository_service()
        available_packages = repository_service.get_available_packages()
        logger.info(f"Loaded {len(available_packages)} available packages: {available_packages}")

        # Initialize all agents with available packages
        self.intake_agent = IntakeAgent(available_packages=available_packages)
        self.search_agent = SearchAgent(available_packages=available_packages)
        self.planner_agent = PlannerAgent(available_packages=available_packages)
        self.implementer_agent = ImplementerAgent(available_packages=available_packages)
        self.test_agent = TestAgent()
        self.reviewer_agent = ReviewerAgent()
        self.summarizer_agent = SummarizerAgent()

        # Pytest runner
        self.pytest_runner = get_pytest_runner()

        # Configuration
        self.max_iterations = self.settings.max_refinement_iterations

        logger.info(f"Initialized ToolGenerationPipelineV2 (max_iterations={self.max_iterations})")

    async def process_tool_generation(
        self,
        task_id: str,
        requirement: UserToolRequirement,
        job_id: str = None
    ) -> ToolGenerationOutput:
        """
        Execute the full pipeline with iterative refinement.

        Args:
            task_id: Task identifier
            requirement: User tool requirement
            job_id: Job identifier (for organizing output files)

        Returns:
            ToolGenerationOutput: Generation result (success or failure)
        """
        # Initialize task-specific file logging
        pipeline_logger = get_task_logger("pipeline", job_id or "unknown", task_id)

        try:
            logger.info(f"Starting pipeline V2 for task {task_id}: {requirement.description[:100]}...")

            # Debug log: Pipeline start
            log_divider(pipeline_logger, "PIPELINE START")
            pipeline_logger.debug(f"Task ID: {task_id}")
            pipeline_logger.debug(f"Job ID: {job_id}")
            pipeline_logger.debug(f"Requirement Description: {requirement.description}")
            pipeline_logger.debug(f"Requirement Input: {requirement.input}")
            pipeline_logger.debug(f"Requirement Output: {requirement.output}")

            # ===== STEP 1: INTAKE =====
            log_divider(pipeline_logger, "STEP 1: INTAKE")
            logger.info("Step 1: Intake - Validating requirement")
            intake_output = await self.intake_agent.process(requirement,
                                                            #job_id, task_id
                                                            )

            pipeline_logger.debug(f"Intake validation status: {intake_output.validation_status}")
            if intake_output.tool_definition:
                pipeline_logger.debug(f"Tool name: {intake_output.tool_definition.name}")
                pipeline_logger.debug(f"Tool signature: {intake_output.tool_definition.signature}")
                pipeline_logger.debug(f"Open questions count: {len(intake_output.open_questions)}")

            if intake_output.validation_status == "invalid":
                logger.error(f"Requirement validation failed: {intake_output.error}")
                return ToolGenerationOutput(
                    results=[],
                    failures=[ToolGenerationFailure(
                        toolRequirement=requirement,
                        error=intake_output.error or "Invalid requirement",
                        error_type="invalid_requirement"
                    )]
                )

            if not intake_output.tool_definition:
                logger.error("Intake agent did not produce tool definition")
                return ToolGenerationOutput(
                    results=[],
                    failures=[ToolGenerationFailure(
                        toolRequirement=requirement,
                        error="Failed to synthesize tool definition",
                        error_type="intake_error"
                    )]
                )

            tool_definition = intake_output.tool_definition
            open_questions = intake_output.open_questions
            logger.info(f"Tool definition created: {tool_definition.name}")
            logger.debug(f"tool definition created: {open_questions}")
            logger.debug(f"open questions: {open_questions}")

            # ===== STEP 2: SEARCH =====
            log_divider(pipeline_logger, "STEP 2: SEARCH")
            logger.info("Step 2: Search - Exploring APIs and documentation")
            exploration_report = await self.search_agent.explore(
                tool_definition,
                open_questions,
                task_id=task_id,
                job_id=job_id
            )
            logger.info(f"Found {len(exploration_report.apis)} APIs, {len(exploration_report.examples)} examples")

            pipeline_logger.debug(f"APIs found: {len(exploration_report.apis)}")
            pipeline_logger.debug(f"Examples found: {len(exploration_report.examples)}")
            pipeline_logger.debug(f"Question answers: {len(exploration_report.question_answers)}")

            # ===== STEP 3: PLAN =====
            log_divider(pipeline_logger, "STEP 3: PLAN")
            logger.info("Step 3: Plan - Creating implementation plan")
            plan = await self.planner_agent.create_plan(
                tool_definition,
                exploration_report,
                task_id=task_id,
                job_id=job_id or "unknown"
            )
            logger.info(f"Plan created with {len(plan.steps)} steps")

            pipeline_logger.debug(f"Plan steps count: {len(plan.steps)}")
            pipeline_logger.debug(f"Validation rules count: {len(plan.validation_rules)}")
            pipeline_logger.debug(f"API refs: {plan.api_refs}")

            # ===== STEPS 4-9: ITERATIVE REFINEMENT LOOP =====
            iteration_history = []

            for iteration in range(1, self.max_iterations + 1):
                log_divider(pipeline_logger, f"ITERATION {iteration}/{self.max_iterations}")
                logger.info(f"Starting iteration {iteration}/{self.max_iterations}")
                pipeline_logger.debug(f"Iteration history entries: {len(iteration_history)}")

                # === STEP 4: IMPLEMENT ===
                pipeline_logger.debug(f"Step 4: Implementing tool (iteration {iteration})")
                logger.info(f"Step 4 (iter {iteration}): Implement - Generating tool code")
                impl_result = await self.implementer_agent.implement(
                    tool_definition,
                    plan,
                    exploration_report,
                    iteration_history
                )

                if not impl_result.success:
                    logger.error(f"Implementation failed: {impl_result.error}")
                    return ToolGenerationOutput(
                        results=[],
                        failures=[ToolGenerationFailure(
                            toolRequirement=requirement,
                            error=impl_result.error or "Implementation failed",
                            error_type="implementation_error"
                        )]
                    )

                logger.info(f"Tool implemented: {impl_result.tool_file_path}")
                pipeline_logger.debug(f"Implementation success: {impl_result.success}")
                pipeline_logger.debug(f"Tool file: {impl_result.tool_file_path}")
                pipeline_logger.debug(f"Tool code length: {len(impl_result.tool_code)} chars")

                # === STEP 5: GENERATE TESTS ===
                pipeline_logger.debug(f"Step 5: Generating tests (iteration {iteration})")
                logger.info(f"Step 5 (iter {iteration}): Test - Generating test suite")
                test_result = await self.test_agent.generate_tests(
                    tool_definition,
                    plan,
                    exploration_report,
                    iteration_history
                )

                if not test_result.success:
                    logger.error(f"Test generation failed: {test_result.error}")
                    return ToolGenerationOutput(
                        results=[],
                        failures=[ToolGenerationFailure(
                            toolRequirement=requirement,
                            error=test_result.error or "Test generation failed",
                            error_type="test_generation_error"
                        )]
                    )

                logger.info(f"Tests generated: {test_result.test_file_path}")
                pipeline_logger.debug(f"Test generation success: {test_result.success}")
                pipeline_logger.debug(f"Test file: {test_result.test_file_path}")
                pipeline_logger.debug(f"Test types: {test_result.test_types}")
                pipeline_logger.debug(f"Fixtures created: {len(test_result.fixtures_created)}")

                # === STEP 6: RUN TESTS ===
                pipeline_logger.debug(f"Step 6: Running pytest (iteration {iteration})")
                logger.info(f"Step 6 (iter {iteration}): Running pytest")

                task_dir = Path(self.settings.tools_path) / job_id / task_id
                test_results = await self.pytest_runner.run_tests(
                    test_result.test_file_path,
                    working_dir=str(task_dir),
                    # job_id=job_id,
                    # task_id=task_id
                )

                pipeline_logger.debug(f"Test results: {test_results.passed} passed, {test_results.failed} failed, {test_results.errors} errors")
                pipeline_logger.debug(f"Test duration: {test_results.duration:.2f}s")

                # === STEP 7: REVIEW ===
                pipeline_logger.debug(f"Step 7: Reviewing (iteration {iteration})")
                logger.info(f"Step 7 (iter {iteration}): Review - Analyzing code and results")
                review_report = await self.reviewer_agent.review(
                    tool_code=impl_result.tool_code,
                    test_code=test_result.test_code,
                    test_results=test_results,
                    plan=plan,
                    iteration=iteration,
                    # job_id=job_id,
                    # task_id=task_id
                )

                logger.info(f"Review complete: approved={review_report.approved}")
                pipeline_logger.debug(f"Review approved: {review_report.approved}")
                pipeline_logger.debug(f"Review issues: {len(review_report.issues)}")

                if review_report.approved:
                    # === SUCCESS - TOOL APPROVED ===
                    log_divider(pipeline_logger, "TOOL APPROVED")
                    logger.info(f"✅ Tool approved after {iteration} iteration(s)")
                    pipeline_logger.debug(f"Total iterations: {iteration}")
                    pipeline_logger.debug(f"Final tool file: {impl_result.tool_file_path}")

                    # Parse input and output schemas from the ACTUAL generated code
                    # This is more accurate than using the tool definition
                    input_schema, output_schema, actual_func_name = parse_function_from_code(
                        impl_result.tool_code
                    )

                    # Extract description from the actual code
                    description = extract_description_from_code(impl_result.tool_code)
                    if not description:
                        # Fallback to tool definition
                        description = tool_definition.docstring.split('\n')[0]

                    # Use the actual function name from code (in case it differs)
                    function_name = actual_func_name if actual_func_name != "unknown" else tool_definition.name

                    # Create successful result
                    result = ToolGenerationResult(
                        success=True,
                        name=function_name,
                        file_name=f"{function_name}.py",
                        description=description,
                        input_schema=input_schema,
                        output_schema=output_schema,
                        dependencies=self._extract_dependencies(plan)
                    )

                    return ToolGenerationOutput(
                        results=[result],
                        failures=[]
                    )

                # === STEP 8: SUMMARIZE ===
                pipeline_logger.debug(f"Step 8: Summarizing iteration {iteration}")
                logger.info(f"Step 8 (iter {iteration}): Summarize - Compressing iteration data")
                summary = await self.summarizer_agent.summarize(
                    IterationData(
                        iteration=iteration,
                        logs=[],  # Could collect from logger if needed
                        failures=test_results.failures,
                        review_report=review_report,
                        plan=plan
                    ),
                    # job_id=job_id,
                    # task_id=task_id
                )

                iteration_history.append(summary)
                logger.info(f"Iteration {iteration} summary: {summary.what_failed[:100]}...")
                pipeline_logger.debug(f"What failed: {summary.what_failed}")
                pipeline_logger.debug(f"Next focus: {summary.next_focus}")

                # === STEP 9: LOOP BACK ===
                if iteration < self.max_iterations:
                    logger.info(f"Re-implementing based on feedback (iteration {iteration + 1})")
                else:
                    logger.warning(f"Max iterations ({self.max_iterations}) reached without approval")

            # ===== MAX ITERATIONS REACHED WITHOUT APPROVAL =====
            logger.error(f"Failed to generate approved tool after {self.max_iterations} iterations")

            # Collect failure information from final iteration
            final_summary = iteration_history[-1] if iteration_history else None
            error_message = (
                f"Failed to generate approved tool after {self.max_iterations} iterations. "
                f"Final issues: {final_summary.what_failed if final_summary else 'Unknown'}"
            )

            return ToolGenerationOutput(
                results=[],
                failures=[ToolGenerationFailure(
                    toolRequirement=requirement,
                    error=error_message,
                    error_type="max_iterations_exceeded"
                )]
            )

        except Exception as e:
            logger.error(f"Unexpected error in pipeline V2: {e}", exc_info=True)
            return ToolGenerationOutput(
                results=[],
                failures=[ToolGenerationFailure(
                    toolRequirement=requirement,
                    error=f"Pipeline error: {str(e)}",
                    error_type="pipeline_error"
                )]
            )

    def _extract_dependencies(self, plan) -> list[str]:
        """
        Extract Python package dependencies from plan.

        Args:
            plan: Implementation plan

        Returns:
            list[str]: List of required packages
        """
        dependencies = set()

        # Extract from API references
        for api_ref in plan.api_refs:
            # Extract package name (first part of dotted name)
            package = api_ref.split('.')[0].lower()
            dependencies.add(package)

        return sorted(list(dependencies))

    async def cleanup(self):
        """Clean up all agent resources."""
        logger.info("Cleaning up pipeline V2 agents")
        await self.intake_agent.cleanup()
        await self.search_agent.cleanup()
        await self.planner_agent.cleanup()
        await self.implementer_agent.cleanup()
        await self.test_agent.cleanup()
        await self.reviewer_agent.cleanup()
        await self.summarizer_agent.cleanup()
        logger.info("Pipeline V2 cleanup completed")

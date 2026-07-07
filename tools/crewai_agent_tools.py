"""CrewAI runtime setup, execution, and JSON result helpers."""

import os

from core.agent_utils import parse_json_object


def build_crewai_llm(LLM, model_name, *, timeout, max_tokens, temperature=0.2):
    """Build a CrewAI LLM with the shared defaults used across this project."""
    return LLM(
        model=model_name,
        temperature=temperature,
        timeout=timeout,
        max_tokens=max_tokens,
    )


def build_crewai_agent(Agent, llm, spec):
    """Create one CrewAI agent from a simple specification mapping."""
    return Agent(
        role=spec["role"],
        goal=spec["goal"],
        backstory=spec["backstory"],
        llm=llm,
        allow_delegation=spec.get("allow_delegation", False),
        verbose=spec.get("verbose", True),
        tools=spec.get("tools") or [],
    )


def run_crewai_json_agent(
    *,
    role,
    goal,
    backstory,
    task_prompt,
    expected_output,
    api_key,
    model_name,
    max_tokens=4096,
    timeout=45,
    label="CrewAI agent",
    tools=None,
):
    """Run one CrewAI agent/task and parse the JSON object it returns.
    (the factory that creates any CrewAI agent object)
    """
    configure_google_key(api_key)
    Agent, Crew, LLM, Process, Task = load_crewai()
    llm = build_crewai_llm(
        LLM,
        model_name,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    agent = build_crewai_agent(Agent, llm, {
        "role": role,
        "goal": goal,
        "backstory": backstory,
        "allow_delegation": False,
        "verbose": True,
        "tools": tools or [],
    })
    task = Task(
        description=task_prompt,
        expected_output=expected_output,
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    try:
        result = crew.kickoff()
        return parse_crewai_json_result(result, task, error_label=label)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"{label} failed: {exc}") from exc


def run_crewai_json_crew(
    *,
    task_specs,
    api_key,
    default_model_name,
    max_tokens=8192,
    timeout=60,
    label="CrewAI workflow",
):
    """Run one sequential CrewAI crew and parse each task's JSON output."""
    configure_google_key(api_key)
    Agent, Crew, LLM, Process, Task = load_crewai()

    agents = []
    tasks = []
    tasks_by_name = {}
    for spec in task_specs:
        name = spec["name"]
        llm = build_crewai_llm(
            LLM,
            spec.get("model_name") or default_model_name,
            temperature=spec.get("temperature", 0.2),
            timeout=spec.get("timeout", timeout),
            max_tokens=spec.get("max_tokens", max_tokens),
        )
        agent = build_crewai_agent(Agent, llm, spec)
        task_kwargs = {
            "description": spec["task_prompt"],
            "expected_output": spec["expected_output"],
            "agent": agent,
        }
        """" later task can look at the output of earlier tasks. """
        context_names = spec.get("context") or []
        if context_names:
            task_kwargs["context"] = [tasks_by_name[item] for item in context_names]
        task = Task(**task_kwargs)
        agents.append(agent)
        tasks.append(task)
        tasks_by_name[name] = task

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )
    try:
        crew.kickoff()
        return {
            spec["name"]: parse_crewai_json_result(
                None,
                tasks_by_name[spec["name"]],
                error_label=spec.get("label") or f"{label} {spec['name']}",
            )
            for spec in task_specs
        }
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"{label} failed: {exc}") from exc


def run_crewai_json_hierarchical_crew(
    *,
    agent_specs,
    task_prompt,
    expected_output,
    api_key,
    manager_model_name,
    task_agent_name,
    default_model_name=None,
    max_tokens=8192,
    timeout=60,
    label="CrewAI hierarchical workflow",
):
    """Run one hierarchical CrewAI crew and parse the final task output as JSON."""
    configure_google_key(api_key)
    Agent, Crew, LLM, Process, Task = load_crewai()

    workers = []
    agents_by_name = {}
    worker_model_name = default_model_name or manager_model_name
    for spec in agent_specs:
        llm = build_crewai_llm(
            LLM,
            spec.get("model_name") or worker_model_name,
            temperature=spec.get("temperature", 0.2),
            timeout=spec.get("timeout", timeout),
            max_tokens=spec.get("max_tokens", max_tokens),
        )
        agent = build_crewai_agent(Agent, llm, spec)
        workers.append(agent)
        agents_by_name[spec["name"]] = agent

    try:
        task_agent = agents_by_name[task_agent_name]
    except KeyError as exc:
        raise RuntimeError(
            f"{label} failed: unknown hierarchical task agent {task_agent_name!r}."
        ) from exc

    task = Task(
        description=task_prompt,
        expected_output=expected_output,
        agent=task_agent,
    )
    manager_llm = build_crewai_llm(
        LLM,
        manager_model_name,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    crew = Crew(
        agents=workers,
        tasks=[task],
        process=Process.hierarchical,
        manager_llm=manager_llm,
        verbose=True,
    )
    try:
        result = crew.kickoff()
        return parse_crewai_json_result(result, task, error_label=label)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"{label} failed: {exc}") from exc


def load_crewai():
    """Import CrewAI lazily so app startup can report a clear dependency error."""
    try:
        from crewai import Agent, Crew, LLM, Process, Task
    except ImportError as exc:
        raise RuntimeError(
            "CrewAI is not installed. Install the project requirements, including crewai[google-genai]."
        ) from exc
    return Agent, Crew, LLM, Process, Task


def configure_google_key(api_key):
    """Expose the Gemini key through the env names CrewAI/LiteLLM integrations expect."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    os.environ.setdefault("GEMINI_API_KEY", api_key)
    os.environ.setdefault("GOOGLE_API_KEY", api_key)


def crew_output_text(result, task):
    """Return the raw text from a CrewAI result across supported output shapes."""
    for value in (
        getattr(result, "raw", None),
        getattr(getattr(task, "output", None), "raw", None),
        result,
    ):
        if value:
            return str(value)
    return ""


def parse_crewai_json_result(result, task, *, error_label="CrewAI agent"):
    """Parse a CrewAI result object into JSON."""
    return parse_json_object(crew_output_text(result, task), error_label=error_label)

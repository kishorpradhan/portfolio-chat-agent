from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_prompt(template_name: str, **kwargs: str) -> str:
    base_dir = Path(__file__).resolve().parent
    env = Environment(
        loader=FileSystemLoader(base_dir),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    return template.render(**kwargs)

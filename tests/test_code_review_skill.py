from pathlib import Path
import yaml


def test_code_review_skill_exists_and_has_valid_frontmatter():
    skill_file = Path(".agents/skills/code-review/SKILL.md")
    assert skill_file.is_file(), "SKILL.md must exist in .agents/skills/code-review/"

    content = skill_file.read_text(encoding="utf-8")
    assert content.startswith("---"), "SKILL.md must start with YAML frontmatter"
    parts = content.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must contain closing frontmatter delimiter '---'"

    meta = yaml.safe_load(parts[1])
    assert isinstance(meta, dict), "Frontmatter must be a valid YAML mapping"
    assert meta.get("name") == "code-review"
    assert meta.get("description") and len(meta["description"].strip()) > 10


def test_code_review_skill_mentions_boost_and_the_four_pillars():
    skill_file = Path(".agents/skills/code-review/SKILL.md")
    content = skill_file.read_text(encoding="utf-8")

    # Must explicitly instruct the reviewer to use /boost
    assert "/boost" in content, "SKILL.md must explicitly reference /boost"

    # Must cover the 4 review pillars
    assert "Safety & Sensitive Data Redaction" in content or "Pillar 1: Safety" in content
    assert "Contract & Output Stream" in content or "Pillar 2: Contract" in content
    assert "Evaluator Integrity" in content or "Pillar 3: Evaluator" in content
    assert "Test & Implementation" in content or "Pillar 4: Test" in content

    # Must detail the exit code contract and precedence rule
    assert "Exit Code 1" in content
    assert "schema_version" in content
    assert "Precedence Rule" in content


def test_code_review_checklist_exists():
    checklist_file = Path(".agents/skills/code-review/references/checklist.md")
    assert checklist_file.is_file(), "checklist.md must exist in references/"

    content = checklist_file.read_text(encoding="utf-8")
    assert "Safety & Sensitive Data Checks" in content
    assert "CLI & Integration Contract Checks" in content
    assert "Presets & Evaluation Questions" in content
    assert "Test Quality & Regressions" in content


def test_agents_and_readme_reference_code_review_skill():
    agents_md = Path("AGENTS.md").read_text(encoding="utf-8")
    readme_md = Path("README.md").read_text(encoding="utf-8")

    assert ".agents/skills/code-review" in agents_md
    assert "/boost" in agents_md

    assert ".agents/skills/code-review" in readme_md
    assert "/boost" in readme_md

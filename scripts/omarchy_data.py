"""Load bounded plain YAML/JSON, without Ansible evaluation or duplicate keys."""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def plain(value, depth=0):
    if depth > 30:
        raise ValueError("Configuration nesting is too deep")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Configuration keys must be strings")
            plain(key, depth + 1)
            plain(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            plain(item, depth + 1)
    elif isinstance(value, str):
        if any(token in value for token in ("{{", "{%", "{#")):
            raise ValueError("Templates and lookups are not allowed in configuration")
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError("Configuration must contain only plain data")
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("Configuration numbers must be finite")
    return value


def pairs(rows):
    result = {}
    for key, value in rows:
        if not isinstance(key, str) or key in result:
            raise ValueError("Configuration keys must be unique strings")
        result[key] = value
    return result


def read_data(path, *, fallback=True):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 262144:
        raise ValueError("Configuration must be a file of at most 256 KiB")
    source = path.read_text()
    try:
        return plain(json.loads(source, object_pairs_hook=pairs))
    except json.JSONDecodeError:
        pass
    try:
        import yaml
    except ImportError:
        # Reuse PyYAML from the already installed Ansible runtime; never install it.
        executable = shutil.which("ansible-playbook") if fallback else None
        if not executable:
            raise ValueError("YAML requires the existing Ansible Python runtime; JSON also works")
        interpreter = Path(executable).resolve().read_text().splitlines()[0][2:].strip()
        if not Path(interpreter).is_file():
            raise ValueError("Cannot locate Ansible's Python runtime; use JSON")
        result = subprocess.run([interpreter, "-I", str(Path(__file__).resolve()), str(path)],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError(result.stderr.strip() or "Unable to read plain YAML")
        return plain(json.loads(result.stdout))

    class Loader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            return pairs((self.construct_object(key, deep=deep), self.construct_object(value, deep=deep))
                         for key, value in node.value)

    try:
        # Reject aliases, anchors, tags and YAML merge keys rather than evaluating them.
        depth = 0
        for event in yaml.parse(source):
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
            if depth > 30:
                raise ValueError("Configuration nesting is too deep")
            if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None) or getattr(event, "tag", None):
                raise ValueError("YAML aliases, anchors and explicit tags are not supported")
        return plain(yaml.load(source, Loader=Loader))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid plain YAML in {path.name}") from error


if __name__ == "__main__":
    try:
        print(json.dumps(read_data(sys.argv[1], fallback=False), allow_nan=False))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

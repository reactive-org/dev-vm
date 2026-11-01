"""Shared, standard-library-only feature validation for the controller and guest."""

import json
import re
from pathlib import Path


CATALOGUE_PATH = Path(__file__).with_name("catalogue.json")
if not CATALOGUE_PATH.exists():
    CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "features/catalogue.json"
CATALOGUE = json.loads(CATALOGUE_PATH.read_text())
FEATURES = tuple(CATALOGUE["features"])
NAME = r"[a-z][a-z0-9_-]*"
REFERENCE = rf"{NAME}(?:\.{NAME})?"
PACKAGE = r"[a-z0-9][a-z0-9@._+\-]*"


class FeatureError(ValueError):
    pass


def strings(value, pattern, label):
    if (not isinstance(value, list) or any(not isinstance(x, str) or not re.fullmatch(pattern, x) for x in value)
            or len(value) != len(set(value))):
        raise FeatureError(f"{label} must be a list of unique valid names")
    return value


def selection(value, allowed, label):
    strings(value, PACKAGE, label)
    if set(value) - set(allowed):
        raise FeatureError(f"{label} must be selected from {', '.join(sorted(allowed))}")
    return value


def tools(value, *, agents=False):
    if not isinstance(value, dict):
        raise FeatureError("Tools must be a mapping of mise short names to version selectors")
    for tool, version in value.items():
        if not isinstance(tool, str) or not re.fullmatch(NAME, tool):
            raise FeatureError("Use a mise registry short name, without backend commands or paths")
        if agents and tool not in CATALOGUE["features"]["agents"]["choices"]:
            raise FeatureError(f"Unsupported coding agent: {tool}")
        if not isinstance(version, str) or (version and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", version)):
            raise FeatureError(f"Invalid mise version selector for {tool}")
    return value


def validate_config(feature, value, *, extension=False):
    if not isinstance(value, dict):
        raise FeatureError("Feature input must be an object")
    if extension:
        if not isinstance(feature, str) or not re.fullmatch(rf"{NAME}\.{NAME}", feature) or feature.startswith("builtin."):
            raise FeatureError("Extension IDs must be namespaced and cannot shadow built-ins")
        definition = {"handler": "tools", "defaults": {"packages": [], "tools": {}}}
    else:
        if feature not in FEATURES:
            raise FeatureError(f"Unknown feature: {feature}")
        definition = CATALOGUE["features"][feature]
    if set(value) != set(definition["defaults"]):
        raise FeatureError(f"Unexpected or missing fields for {feature}")
    handler = definition["handler"]
    if handler == "tools":
        strings(value["packages"], PACKAGE, "packages")
        tools(value["tools"])
    elif handler in ("browsers", "selection"):
        option = definition.get("option", "browsers")
        selection(value[option], definition["choices"], option)
    elif handler in ("languages", "agents"):
        tools(value["tools"], agents=handler == "agents")
    elif handler == "toolchain":
        selection(value["prerequisites"], CATALOGUE["language_packages"], "toolchain prerequisites")
    elif handler == "credentials":
        selection(value["packages"], definition["choices"], "credential packages")
    elif handler == "workstation":
        if not isinstance(value["font_size"], str) or not re.fullmatch(r"(?:[6-9]|[12][0-9]|3[0-2])(?:\.[0-9]+)?", value["font_size"]):
            raise FeatureError("Foot font size must be between 6 and 32")
        if value["idle_mode"] not in ("host", "guest", "keep"):
            raise FeatureError("Idle mode must be host, guest or keep")
        if not isinstance(value["theme"], str) or (value["theme"] and not re.fullmatch(
            r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._+\-]*/?", value["theme"]
        )):
            raise FeatureError("Theme must be an HTTPS GitHub repository URL")
        if type(value["remove_layout"]) is not bool or not isinstance(value["layout"], str):
            raise FeatureError("Invalid layout selection")
        if value["layout"] and value["remove_layout"]:
            raise FeatureError("Choose a layout or removal, not both")
    return value


def requirements(feature, config, *, extension=False):
    validate_config(feature, config, extension=extension)
    definition = {} if extension else CATALOGUE["features"][feature]
    handler = definition.get("handler", "tools")
    packages, requested = [], {}
    if handler == "tools":
        packages.extend(config["packages"])
        requested.update(config["tools"])
    elif handler in ("selection", "browsers"):
        packages.extend(definition["choices"][item] for item in config[definition.get("option", "browsers")])
    elif handler == "docker":
        packages.extend(definition["packages"])
    elif handler == "credentials":
        packages.extend(config["packages"])
    elif handler == "workstation":
        packages.extend(CATALOGUE["workstation_packages"])
    elif handler == "toolchain":
        packages.append("mise-bin")
        for language in config["prerequisites"]:
            packages.extend(CATALOGUE["language_packages"][language])
    elif handler in ("languages", "agents"):
        requested.update(config["tools"])
        if handler == "languages":
            for tool in requested:
                packages.extend(CATALOGUE["language_packages"].get(tool, []))
    if requested:
        packages.append("mise-bin")
    return list(dict.fromkeys(packages)), requested

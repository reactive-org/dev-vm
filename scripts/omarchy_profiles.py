"""Resolve profiles and explicitly supplied data-only extension catalogues."""

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from omarchy_data import read_data

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "omarchy/guest"))
import feature_contract as contract

ProfileError = contract.FeatureError


def fields(value, allowed, required=(), label="configuration"):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ProfileError(f"Unknown or missing fields in {label}")
    return value


def version(value):
    if type(value) is not int or value != 1:
        raise ProfileError("Unsupported schema_version; expected 1")


class Conflict:
    """Unresolved sibling choices, preserved until an explicit child/user override."""


def overlay(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict) or not override:
        return copy.deepcopy(override)
    result = copy.deepcopy(base)
    for key, value in override.items():
        result[key] = overlay(result[key], value) if key in result else copy.deepcopy(value)
    return result


def siblings(left, right):
    if left == right:
        return copy.deepcopy(left)
    if isinstance(left, dict) and isinstance(right, dict) and left and right:
        result = copy.deepcopy(left)
        for key, value in right.items():
            result[key] = siblings(result[key], value) if key in result else copy.deepcopy(value)
        return result
    return Conflict()


def no_conflicts(value, path="options"):
    if isinstance(value, Conflict):
        raise ProfileError(f"Conflicting profile choices at {path}; supply an explicit override")
    if isinstance(value, dict):
        for key, item in value.items():
            no_conflicts(item, path + "." + key)


class Resolver:
    def __init__(self):
        self.features = copy.deepcopy(contract.CATALOGUE["features"])
        self.profiles = copy.deepcopy(contract.CATALOGUE["profiles"])
        self.sources = []
        self.namespaces = {"builtin"}
        self.profile_cache = {}
        self.source(contract.CATALOGUE_PATH)

    def source(self, path):
        path = Path(path).resolve(strict=True)
        self.sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    @staticmethod
    def verify_source(source):
        if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ProfileError("Feature source changed after resolution; review a new proposal")

    @staticmethod
    def reference(name):
        if not isinstance(name, str) or not re.fullmatch(contract.REFERENCE, name):
            raise ProfileError("Use a feature/profile name or namespace.name")
        return name[8:] if name.startswith("builtin.") else name

    def refs(self, values, label):
        contract.strings(values, contract.REFERENCE, label)
        result = [self.reference(x) for x in values]
        if len(result) != len(set(result)):
            raise ProfileError(f"Duplicate aliases in {label}")
        return result

    def load_catalogue(self, path):
        value = fields(read_data(path), {"schema_version", "namespace", "features", "profiles"},
                       {"schema_version", "namespace", "features"}, "catalogue")
        version(value["schema_version"])
        namespace = value["namespace"]
        if not isinstance(namespace, str) or not re.fullmatch(contract.NAME, namespace) or namespace in self.namespaces:
            raise ProfileError("Catalogue namespace must be unique and cannot shadow builtin")
        self.namespaces.add(namespace)
        for kind in ("features", "profiles"):
            definitions = value.get(kind, {})
            if not isinstance(definitions, dict):
                raise ProfileError(f"Catalogue {kind} must be a mapping")
            for name, definition in definitions.items():
                if not isinstance(name, str) or not re.fullmatch(contract.NAME, name):
                    raise ProfileError("Catalogue entries must have simple local names")
                identifier = namespace + "." + name
                if kind == "features":
                    fields(definition, {"description", "requires", "packages", "mise"}, {"description"}, identifier)
                    if not isinstance(definition["description"], str) or not definition["description"].strip():
                        raise ProfileError("Each extension feature needs a description")
                    defaults = {"packages": definition.get("packages", []), "tools": definition.get("mise", {})}
                    contract.validate_config(identifier, defaults, extension=True)
                    self.features[identifier] = {"description": definition["description"], "handler": "tools",
                                                 "requires": definition.get("requires", []), "defaults": defaults}
                else:
                    self.profiles[identifier] = copy.deepcopy(definition)
        self.source(path)

    def options(self, value):
        if not isinstance(value, dict):
            raise ProfileError("Options must be a feature-to-options mapping")
        result = {}
        for name, options in value.items():
            name = self.reference(name)
            if name not in self.features or name in result or not isinstance(options, dict):
                raise ProfileError(f"Unknown, duplicate or invalid feature options: {name}")
            # A supplied option field replaces that field's baseline. Inheritance
            # and personal overrides merge tool maps before this materialization.
            self.configuration(name, options)
            result[name] = copy.deepcopy(options)
        return result

    def configuration(self, name, options):
        config = {**copy.deepcopy(self.features[name]["defaults"]), **options}
        if isinstance(config.get("tools"), dict):
            # Null is an override tombstone, never a mise version. Validate its
            # tool name before dropping it from the executable configuration.
            checked = {**config, "tools": {tool: "" if selector is None else selector
                                           for tool, selector in config["tools"].items()}}
            contract.validate_config(name, checked, extension=name not in contract.FEATURES)
            config["tools"] = {tool: selector for tool, selector in config["tools"].items() if selector is not None}
        contract.validate_config(name, config, extension=name not in contract.FEATURES)
        return config

    def validate(self):
        for name, feature in self.features.items():
            dependencies = self.refs(feature.get("requires", []), "feature prerequisites")
            if set(dependencies) - set(self.features):
                raise ProfileError(f"Unknown prerequisite for {name}")
            feature["requires"] = dependencies
        for name, profile in self.profiles.items():
            fields(profile, {"description", "extends", "features", "options"}, label=name)
            if "description" in profile and not isinstance(profile["description"], str):
                raise ProfileError("Profile description must be a string")
            profile["extends"] = self.refs(profile.get("extends", []), "profile parents")
            profile["features"] = self.refs(profile.get("features", []), "profile features")
            profile["options"] = self.options(profile.get("options", {}))
            if set(profile["extends"]) - set(self.profiles) or set(profile["features"]) - set(self.features):
                raise ProfileError(f"Unknown parent or feature in profile {name}")
        self.acyclic(self.features, "requires")
        self.acyclic(self.profiles, "extends")

    @staticmethod
    def acyclic(definitions, edge):
        visited, active = set(), set()

        def visit(name):
            if len(active) >= 30:
                raise ProfileError("Dependency/inheritance graph is too deep")
            if name in active:
                raise ProfileError(f"Dependency/inheritance cycle at {name}")
            if name in visited:
                return
            active.add(name)
            for parent in definitions[name].get(edge, []):
                visit(parent)
            active.remove(name)
            visited.add(name)

        for name in definitions:
            visit(name)

    def profile(self, name):
        if name in self.profile_cache:
            return self.profile_cache[name]
        definition = self.profiles[name]
        selected, values = set(definition["features"]), {}
        for parent in definition["extends"]:
            inherited, options = self.profile(parent)
            selected.update(inherited)
            values = self.combine(values, options)
        self.profile_cache[name] = (selected, overlay(values, definition["options"]) if definition["options"] else values)
        return self.profile_cache[name]

    @staticmethod
    def combine(left, right):
        result = copy.deepcopy(left)
        for key, value in right.items():
            result[key] = siblings(result[key], value) if key in result else copy.deepcopy(value)
        return result

    def resolve(self, *, profiles=None, features=None, setup_file=None, catalogues=None, overrides=None):
        setup = {}
        if setup_file:
            setup_file = Path(setup_file).resolve(strict=True)
            setup = fields(read_data(setup_file), {"schema_version", "catalogues", "profiles", "features", "options"},
                           {"schema_version"}, "selection")
            version(setup["schema_version"])
            paths = setup.get("catalogues", [])
            if not isinstance(paths, list) or any(not isinstance(x, str) or not x for x in paths):
                raise ProfileError("catalogues must be explicit local file paths")
            for path in paths:
                self.load_catalogue(setup_file.parent / path)
            self.source(setup_file)
        for path in catalogues or []:
            self.load_catalogue(path)
        self.validate()
        chosen_profiles = self.refs(self.refs(setup.get("profiles", []), "profiles") + self.refs(profiles or [], "profiles"), "profiles")
        if set(chosen_profiles) - set(self.profiles):
            raise ProfileError("Unknown profile selection")
        selection = fields(setup.get("features", {}), {"enable", "disable"}, label="feature selection")
        enabled = self.refs(selection.get("enable", []), "enabled features")
        disabled = set(self.refs(selection.get("disable", []), "disabled features"))
        additions = self.refs(features or [], "features")
        if (set(enabled) | disabled | set(additions)) - set(self.features):
            raise ProfileError("Unknown feature selection")
        selected, options, reasons = set(), {}, {}
        for name in chosen_profiles:
            inherited, values = self.profile(name)
            selected.update(inherited)
            options = self.combine(options, values)
            for feature in inherited:
                reasons.setdefault(feature, []).append("profile " + name)
        if not chosen_profiles and not enabled and features is None:
            enabled = ["workstation"]
        for feature in enabled + additions:
            selected.add(feature)
            reasons.setdefault(feature, []).append("explicit selection")
        selected -= disabled
        user_options = self.options(setup.get("options", {}))
        # Legacy variables / command-line choices are the last explicit layer.
        user_options = overlay(user_options, self.options(overrides)) if overrides else user_options
        for feature, value in user_options.items():
            options[feature] = overlay(options.get(feature, {}), value) if value else {}
        ordered, visited = [], set()

        def include(feature):
            if feature in disabled:
                raise ProfileError(f"Disabled required feature: {feature}")
            if feature in visited:
                return
            visited.add(feature)
            for prerequisite in self.features[feature].get("requires", []):
                reasons.setdefault(prerequisite, []).append("required by " + feature)
                include(prerequisite)
            ordered.append(feature)

        for name in sorted(selected, key=lambda x: list(self.features).index(x)):
            include(name)
        configs, packages, mise = {}, {}, {}
        for name in ordered:
            no_conflicts(options.get(name, {}), "options." + name)
            config = self.configuration(name, options.get(name, {}))
            requested_packages, requested_tools = contract.requirements(name, config, extension=name not in contract.FEATURES)
            configs[name] = config
            for package in requested_packages:
                packages.setdefault(package, []).append(name)
            for tool, selector in requested_tools.items():
                if tool in mise and mise[tool]["selector"] != selector:
                    raise ProfileError(f"Conflicting selectors for mise tool {tool}; override every requesting feature")
                mise.setdefault(tool, {"selector": selector, "features": []})["features"].append(name)
        for package, tool in contract.CATALOGUE["package_tools"].items():
            if package in packages and tool in mise:
                raise ProfileError(f"Competing package/mise providers: {package} and {tool}; select one provider")
        files = []
        if "workstation" in ordered:
            files.extend(["~/.config/foot/foot.ini", "~/.config/omarchy/shell.json", "~/.config/hypr/ (selected theme/layout)",
                          "~/.config/systemd/user/ (native idle/known first-login compatibility)"])
        if mise:
            files.append("~/.config/mise/config.toml (explicit selections only; native declarations reused)")
        return {"schema_version": 1, "profiles": chosen_profiles, "features": ordered, "options": configs,
                "reasons": {name: sorted(set(reasons.get(name, []))) for name in ordered},
                "packages": packages, "mise": mise, "sources": self.sources,
                "effects": {"files": files,
                            "native": "Packages, browser integration and shims remain owned by native Omarchy/mise commands",
                            "services": ["Docker UFW integration and socket activation"] if "docker" in ordered else []},
                "limits": ["Selectors may move; guest package and ARM64 tool availability are checked in the guest.",
                           "No authentication, project hooks, project dependencies or application services are configured."]}


def schemas():
    """Editor schemas generated from the same built-in feature definitions."""
    def obj(properties, required=()):
        return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}

    def names(pattern):
        return {"type": "array", "items": {"type": "string", "pattern": "^" + pattern + "$"}, "uniqueItems": True}

    packages = names(contract.PACKAGE)
    tools = {"type": "object", "propertyNames": {"pattern": "^" + contract.NAME + "$"},
             "additionalProperties": {"type": "string", "pattern": "^(?:|[A-Za-z0-9][A-Za-z0-9._+\\-]*)$"}}
    option_tools = copy.deepcopy(tools)
    option_tools["additionalProperties"]["type"] = ["string", "null"]
    operation = obj({"packages": packages, "tools": option_tools})
    properties = {}
    for name, definition in contract.CATALOGUE["features"].items():
        handler = definition["handler"]
        if handler == "tools":
            config = copy.deepcopy(operation)
        elif handler in ("languages", "agents"):
            config = obj({"tools": copy.deepcopy(option_tools)})
            if handler == "agents":
                config["properties"]["tools"]["propertyNames"] = {"enum": definition["choices"]}
        elif handler in ("selection", "browsers", "credentials"):
            option = definition.get("option", "browsers" if handler == "browsers" else "packages")
            config = obj({option: {"type": "array", "uniqueItems": True,
                                   "items": {"enum": list(definition["choices"])}}})
        elif handler == "docker":
            config = obj({})
        else:
            config = obj({"font_size": {"type": "string", "pattern": "^(?:[6-9]|[12][0-9]|3[0-2])(?:\\.[0-9]+)?$"},
                          "idle_mode": {"enum": ["host", "guest", "keep"]}, "theme": {"type": "string"},
                          "layout": {"type": "string"}, "remove_layout": {"type": "boolean"}})
        properties[name] = config
        properties["builtin." + name] = copy.deepcopy(config)
    options = {"type": "object", "properties": properties, "patternProperties": {
        "^(?!builtin\\.)" + contract.NAME + "\\." + contract.NAME + "$": operation}, "additionalProperties": False}
    references = names(contract.REFERENCE)
    profile = obj({"description": {"type": "string"}, "extends": references, "features": references, "options": options})
    catalogue = obj({"schema_version": {"type": "integer", "const": 1}, "namespace": {"type": "string", "pattern": "^(?!builtin$)" + contract.NAME + "$"},
                     "features": {"type": "object", "propertyNames": {"pattern": "^" + contract.NAME + "$"},
                                  "additionalProperties": obj({"description": {"type": "string", "minLength": 1},
                                      "requires": references, "packages": packages, "mise": tools}, ["description"])},
                     "profiles": {"type": "object", "propertyNames": {"pattern": "^" + contract.NAME + "$"}, "additionalProperties": profile}},
                    ["schema_version", "namespace", "features"])
    selection = obj({"schema_version": {"type": "integer", "const": 1}, "catalogues": {"type": "array", "items": {"type": "string", "minLength": 1}},
                     "profiles": references, "features": obj({"enable": references, "disable": references}), "options": options}, ["schema_version"])
    return {name: {"$schema": "https://json-schema.org/draft/2020-12/schema", **value}
            for name, value in [("selection", selection), ("catalogue", catalogue)]}


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-schemas"]:
        sys.exit("Usage: python3 scripts/omarchy_profiles.py --write-schemas")
    for name, schema in schemas().items():
        (ROOT / f"omarchy/features/{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")

"""
Validators for model configuration and adapter files.

Provides comprehensive validation for:
- config.yaml structure and content
- adapter.py code safety and compliance
- Security checks
"""
import ast
import re
import yaml
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validator for config.yaml files."""

    # Required fields in config.yaml
    REQUIRED_FIELDS = {
        "model_name": str,
        "framework": str,
    }

    # Optional but recommended fields
    RECOMMENDED_FIELDS = {
        "version": str,
        "input_size": list,
        "class_names": list,
        "framework_version": str,
    }

    # Valid framework values
    VALID_FRAMEWORKS = {
        "pytorch", "tensorflow", "onnx", "tensorrt",
        "openvino", "custom", "keras", "paddlepaddle"
    }

    # Maximum allowed values
    MAX_INPUT_SIZE = 4096
    MAX_CLASSES = 10000
    MAX_MODEL_NAME_LENGTH = 200

    @classmethod
    def validate(cls, config: Dict[str, Any], strict: bool = False) -> List[str]:
        """
        Validate config.yaml content.

        Args:
            config: Parsed YAML configuration
            strict: If True, enforce recommended fields

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        for field, expected_type in cls.REQUIRED_FIELDS.items():
            if field not in config:
                errors.append(f"Missing required field: '{field}'")
                continue

            if not isinstance(config[field], expected_type):
                errors.append(
                    f"Field '{field}' must be {expected_type.__name__}, "
                    f"got {type(config[field]).__name__}"
                )

        # Check recommended fields (warnings only)
        if strict:
            for field in cls.RECOMMENDED_FIELDS:
                if field not in config:
                    logger.warning(f"Recommended field '{field}' is missing")

        # Validate specific fields
        if "model_name" in config:
            errors.extend(cls._validate_model_name(config["model_name"]))

        if "framework" in config:
            errors.extend(cls._validate_framework(config["framework"]))

        if "input_size" in config:
            errors.extend(cls._validate_input_size(config["input_size"]))

        if "class_names" in config:
            errors.extend(cls._validate_class_names(config["class_names"]))

        if "inference_params" in config:
            errors.extend(cls._validate_inference_params(config["inference_params"]))

        return errors

    @classmethod
    def _validate_model_name(cls, model_name: str) -> List[str]:
        """Validate model_name field."""
        errors = []

        if not isinstance(model_name, str):
            errors.append("model_name must be a string")
            return errors

        if len(model_name) == 0:
            errors.append("model_name cannot be empty")

        if len(model_name) > cls.MAX_MODEL_NAME_LENGTH:
            errors.append(
                f"model_name exceeds maximum length of {cls.MAX_MODEL_NAME_LENGTH}"
            )

        # Check for potentially dangerous characters
        if re.search(r'[<>:"/\\|?*\x00-\x1f]', model_name):
            errors.append("model_name contains invalid characters")

        return errors

    @classmethod
    def _validate_framework(cls, framework: str) -> List[str]:
        """Validate framework field."""
        errors = []

        if not isinstance(framework, str):
            errors.append("framework must be a string")
            return errors

        framework_lower = framework.lower()
        if framework_lower not in cls.VALID_FRAMEWORKS:
            logger.warning(
                f"Framework '{framework}' is not in standard list: "
                f"{cls.VALID_FRAMEWORKS}. Using 'custom' might be more appropriate."
            )

        return errors

    @classmethod
    def _validate_input_size(cls, input_size: Any) -> List[str]:
        """Validate input_size field."""
        errors = []

        if not isinstance(input_size, list):
            errors.append("input_size must be a list")
            return errors

        if len(input_size) != 2:
            errors.append("input_size must have exactly 2 elements [height, width]")
            return errors

        for i, size in enumerate(input_size):
            dim_name = "height" if i == 0 else "width"

            if not isinstance(size, int):
                errors.append(f"input_size {dim_name} must be an integer")
                continue

            if size <= 0:
                errors.append(f"input_size {dim_name} must be positive")

            if size > cls.MAX_INPUT_SIZE:
                errors.append(
                    f"input_size {dim_name} exceeds maximum of {cls.MAX_INPUT_SIZE}"
                )

        return errors

    @classmethod
    def _validate_class_names(cls, class_names: Any) -> List[str]:
        """Validate class_names field."""
        errors = []

        if not isinstance(class_names, list):
            errors.append("class_names must be a list")
            return errors

        if len(class_names) == 0:
            errors.append("class_names cannot be empty")

        if len(class_names) > cls.MAX_CLASSES:
            errors.append(
                f"class_names exceeds maximum of {cls.MAX_CLASSES} classes"
            )

        # Check for duplicates
        if len(class_names) != len(set(class_names)):
            errors.append("class_names contains duplicates")

        # Validate each class name
        for idx, class_name in enumerate(class_names):
            if not isinstance(class_name, str):
                errors.append(f"class_names[{idx}] must be a string")
                continue

            if len(class_name) == 0:
                errors.append(f"class_names[{idx}] cannot be empty")

            if len(class_name) > 100:
                errors.append(f"class_names[{idx}] exceeds 100 characters")

        return errors

    @classmethod
    def _validate_inference_params(cls, params: Any) -> List[str]:
        """Validate inference_params field."""
        errors = []

        if not isinstance(params, dict):
            errors.append("inference_params must be a dictionary")
            return errors

        # Validate common inference parameters
        if "conf_threshold" in params:
            conf = params["conf_threshold"]
            if not isinstance(conf, (int, float)):
                errors.append("conf_threshold must be a number")
            elif not 0.0 <= conf <= 1.0:
                errors.append("conf_threshold must be between 0.0 and 1.0")

        if "iou_threshold" in params:
            iou = params["iou_threshold"]
            if not isinstance(iou, (int, float)):
                errors.append("iou_threshold must be a number")
            elif not 0.0 <= iou <= 1.0:
                errors.append("iou_threshold must be between 0.0 and 1.0")

        if "max_detections" in params:
            max_det = params["max_detections"]
            if not isinstance(max_det, int):
                errors.append("max_detections must be an integer")
            elif max_det <= 0:
                errors.append("max_detections must be positive")

        return errors


class AdapterValidator:
    """Validator for adapter.py files."""

    # Dangerous operations that should not be in adapter code
    DANGEROUS_OPERATIONS = {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",  # Direct file operations (should use provided paths)
        "os.system",
        "os.popen",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
    }

    # Dangerous imports
    DANGEROUS_IMPORTS = {
        "os.system",
        "subprocess",
        "pickle",  # Unsafe deserialization
        "shelve",
        "marshal",
    }

    # Required imports for a valid adapter
    REQUIRED_IMPORTS = {
        "app.ai.base_detector",
    }

    @classmethod
    def validate_code(cls, code: str, filename: str = "adapter.py") -> List[str]:
        """
        Validate adapter.py code for security and compliance.

        Args:
            code: Source code of adapter.py
            filename: Filename for error messages

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Parse AST
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            errors.append(f"Syntax error in {filename}: {e}")
            return errors

        # Check for required structure
        has_detector_class = cls._check_detector_class(tree)
        if not has_detector_class:
            errors.append(
                "No valid detector class found. "
                "Must contain a class inheriting from BaseObjectDetector"
            )

        # Security checks
        errors.extend(cls._check_dangerous_operations(tree, code))
        errors.extend(cls._check_dangerous_imports(tree))

        # Compliance checks
        errors.extend(cls._check_required_methods(tree))
        errors.extend(cls._check_required_imports(tree))

        return errors

    @classmethod
    def _check_detector_class(cls, tree: ast.AST) -> bool:
        """Check if code contains a BaseObjectDetector subclass."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    # Check for BaseObjectDetector inheritance
                    if isinstance(base, ast.Name) and base.id == "BaseObjectDetector":
                        return True
                    # Check for full path import
                    if isinstance(base, ast.Attribute):
                        if base.attr == "BaseObjectDetector":
                            return True
        return False

    @classmethod
    def _check_dangerous_operations(cls, tree: ast.AST, code: str) -> List[str]:
        """Check for dangerous operations in code."""
        errors = []

        for node in ast.walk(tree):
            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                func_name = cls._get_function_name(node.func)

                # Check if it's a standalone dangerous function (not a method call)
                if isinstance(node.func, ast.Name) and node.func.id in cls.DANGEROUS_OPERATIONS:
                    # This is a direct call like exec() or eval()
                    errors.append(
                        f"Dangerous operation detected: {node.func.id}(). "
                        f"This is not allowed for security reasons."
                    )
                elif func_name in cls.DANGEROUS_OPERATIONS and '.' not in func_name:
                    # Additional check for non-method calls
                    errors.append(
                        f"Dangerous operation detected: {func_name}(). "
                        f"This is not allowed for security reasons."
                    )

        return errors

    @classmethod
    def _check_dangerous_imports(cls, tree: ast.AST) -> List[str]:
        """Check for dangerous imports."""
        errors = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in cls.DANGEROUS_IMPORTS:
                        errors.append(
                            f"Dangerous import detected: {alias.name}. "
                            f"This module is not allowed."
                        )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    if full_name in cls.DANGEROUS_IMPORTS or module in cls.DANGEROUS_IMPORTS:
                        errors.append(
                            f"Dangerous import detected: {full_name}. "
                            f"This module is not allowed."
                        )

        return errors

    @classmethod
    def _check_required_methods(cls, tree: ast.AST) -> List[str]:
        """Check if detector class implements required methods."""
        errors = []
        required_methods = {"load_model", "preprocess", "predict", "postprocess"}

        # Find all classes inheriting from BaseObjectDetector
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from BaseObjectDetector
                is_detector = any(
                    (isinstance(base, ast.Name) and base.id == "BaseObjectDetector") or
                    (isinstance(base, ast.Attribute) and base.attr == "BaseObjectDetector")
                    for base in node.bases
                )

                if is_detector:
                    # Get all method names in this class
                    methods = {
                        item.name for item in node.body
                        if isinstance(item, ast.FunctionDef)
                    }

                    # Check for required methods
                    missing = required_methods - methods
                    if missing:
                        errors.append(
                            f"Class '{node.name}' is missing required methods: "
                            f"{', '.join(missing)}"
                        )

        return errors

    @classmethod
    def _check_required_imports(cls, tree: ast.AST) -> List[str]:
        """Check if adapter has required imports."""
        errors = []
        found_imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                found_imports.add(module)

        # Check if BaseObjectDetector is imported
        has_base_import = any(
            "base_detector" in imp for imp in found_imports
        )

        if not has_base_import:
            errors.append(
                "Missing required import: 'from app.ai.base_detector import BaseObjectDetector'"
            )

        return errors

    @classmethod
    def _get_function_name(cls, node: ast.AST) -> str:
        """Extract function name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # For module.function() calls
            value = cls._get_function_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        return ""


class YAMLSafetyValidator:
    """Additional YAML safety checks."""

    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_NESTING_DEPTH = 10

    @classmethod
    def validate_yaml_file(cls, file_path: str) -> List[str]:
        """
        Validate YAML file for safety.

        Args:
            file_path: Path to YAML file

        Returns:
            List of validation errors
        """
        errors = []

        # Check file size
        try:
            file_size = Path(file_path).stat().st_size
            if file_size > cls.MAX_FILE_SIZE:
                errors.append(
                    f"YAML file too large: {file_size} bytes "
                    f"(max: {cls.MAX_FILE_SIZE})"
                )
        except Exception as e:
            errors.append(f"Cannot read file: {e}")
            return errors

        # Try to parse
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Use safe_load (never load!)
            data = yaml.safe_load(content)

            # Check nesting depth
            depth = cls._get_nesting_depth(data)
            if depth > cls.MAX_NESTING_DEPTH:
                errors.append(
                    f"YAML nesting depth {depth} exceeds maximum {cls.MAX_NESTING_DEPTH}"
                )

        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML: {e}")

        return errors

    @classmethod
    def _get_nesting_depth(cls, obj: Any, depth: int = 0) -> int:
        """Calculate nesting depth of nested dict/list."""
        if isinstance(obj, dict):
            if not obj:
                return depth
            return max(cls._get_nesting_depth(v, depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return depth
            return max(cls._get_nesting_depth(item, depth + 1) for item in obj)
        else:
            return depth

import json
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigError(Exception):
    """Base exception for configuration loading errors."""

    pass


class ConfigNotFoundError(ConfigError):
    """Raised when a specified configuration file cannot be found."""

    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration fails schema validation."""

    pass


class LoopDetectionConfig(BaseModel):
    """Configuration for deterministic infinite loop detection."""

    enabled: bool = Field(default=True, description="Enable infinite loop detection")
    max_hops: int = Field(default=10, ge=1, le=100, description="Maximum allowed hop count for a message")
    ttl_seconds: int = Field(default=60, ge=1, description="TTL in seconds for trace history retention")
    history_window: int = Field(default=100, ge=10, description="Number of recent trace IDs to track per agent")


class RateLimitingConfig(BaseModel):
    """Configuration for dynamic rate limiting."""

    enabled: bool = Field(default=True, description="Enable dynamic rate limiting")
    default_rps: float = Field(default=100.0, gt=0.0, description="Default requests per second limit")
    burst_capacity: int = Field(default=150, ge=1, description="Maximum burst capacity allowance")
    algorithm: str = Field(default="token_bucket", description="Rate limiting algorithm (token_bucket, leaky_bucket)")

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = {"token_bucket", "leaky_bucket", "fixed_window"}
        if v.lower() not in allowed:
            raise ValueError(f"Algorithm must be one of {allowed}")
        return v.lower()


class CircuitBreakerConfig(BaseModel):
    """Configuration for resilient circuit breakers."""

    enabled: bool = Field(default=True, description="Enable circuit breaker protection")
    failure_threshold: int = Field(default=5, ge=1, description="Number of failures before tripping circuit")
    recovery_time_seconds: float = Field(default=30.0, gt=0.0, description="Time in seconds before attempting reset")
    half_open_max_requests: int = Field(default=3, ge=1, description="Requests allowed in half-open state")


class TrafficConfig(BaseModel):
    """Aggregated traffic management configuration."""

    loop_detection: LoopDetectionConfig = Field(default_factory=LoopDetectionConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)


class TracingConfig(BaseModel):
    """Configuration for distributed tracing."""

    enabled: bool = Field(default=True, description="Enable distributed tracing")
    exporter: str = Field(default="otlp", description="Tracing exporter (otlp, jaeger, stdout, memory)")
    endpoint: str = Field(default="http://localhost:4317", description="Tracing collector endpoint URL")
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Sampling rate between 0.0 and 1.0")


class ApiConfig(BaseModel):
    """Configuration for the mesh management REST API."""

    enabled: bool = Field(default=True, description="Enable REST API server")
    host: str = Field(default="0.0.0.0", description="API server bind host")
    port: int = Field(default=8000, ge=1, le=65535, description="API server bind port")
    secret_key: str = Field(
        default="sk_test_default_mesh_secret_key_change_in_prod",
        description="JWT or authentication secret key",
    )


class LoggingConfig(BaseModel):
    """Configuration for system logging."""

    level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    json_format: bool = Field(default=True, description="Enable structured JSON log format")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in allowed:
            raise ValueError(f"Logging level must be one of {allowed}")
        return upper_v


class MeshConfig(BaseModel):
    """Top-level mesh node configuration model."""

    node_id: str = Field(
        default_factory=lambda: f"node-{socket.gethostname()}-{uuid.uuid4().hex[:6]}",
        description="Unique identifier for this mesh node",
    )
    cluster_name: str = Field(default="default-cluster", description="Name of the mesh cluster")
    host: str = Field(default="127.0.0.1", description="Internal node communication host")
    port: int = Field(default=9090, ge=1, le=65535, description="Internal node communication port")
    environment: str = Field(default="production", description="Runtime environment (development, staging, production)")
    traffic: TrafficConfig = Field(default_factory=TrafficConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ConfigLoader:
    """Handles loading, parsing, env override merging, and validation of MeshConfig."""

    DEFAULT_CONFIG_PATHS: List[Path] = [
        Path("agent_mesh.yaml"),
        Path("agent_mesh.yml"),
        Path("config/agent_mesh.yaml"),
        Path("/etc/agent_mesh/config.yaml"),
    ]

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        env_prefix: str = "AGENT_MESH_",
    ) -> None:
        self.config_path: Optional[Path] = Path(config_path) if config_path else None
        self.env_prefix: str = env_prefix

    def load_from_yaml(self, path: Path) -> Dict[str, Any]:
        """Loads and parses a YAML configuration file.

        Args:
            path: Path to the YAML file.

        Returns:
            Dict containing raw configuration key-value pairs.

        Raises:
            ConfigNotFoundError: If file does not exist.
            ConfigError: If YAML parsing fails.
        """
        if not path.exists() or not path.is_file():
            raise ConfigNotFoundError(f"Configuration file not found at path: {path.absolute()}")

        try:
            with open(path, "r", encoding="utf-8") as file:
                content = yaml.safe_load(file)
                return content if isinstance(content, dict) else {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse YAML configuration file '{path}': {e}") from e
        except Exception as e:
            raise ConfigError(f"Unexpected error reading config file '{path}': {e}") from e

    def extract_env_vars(self) -> Dict[str, Any]:
        """Extracts and parses environment variables with the defined prefix.

        Supports nested fields using double underscores (`__`).
        Example: AGENT_MESH__TRAFFIC__RATE_LIMITING__DEFAULT_RPS=200.0

        Returns:
            Nested dictionary derived from environment variables.
        """
        env_dict: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(self.env_prefix):
                continue

            stripped_key = key[len(self.env_prefix) :].lower()
            if not stripped_key:
                continue

            parts = stripped_key.split("__")
            parsed_value = self._cast_env_value(value)

            current = env_dict
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = parsed_value

        return env_dict

    @staticmethod
    def _cast_env_value(value: str) -> Any:
        """Casts string environment variable values to proper Python primitives."""
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False
        if value.lower() in ("none", "null", ""):
            return None

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        return value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merges override dictionary into base dictionary."""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def find_config_file(self) -> Optional[Path]:
        """Resolves configuration file location from explicit path or default search paths."""
        if self.config_path:
            if self.config_path.exists():
                return self.config_path
            raise ConfigNotFoundError(f"Explicitly specified config file not found: {self.config_path}")

        for candidate in self.DEFAULT_CONFIG_PATHS:
            if candidate.exists() and candidate.is_file():
                return candidate

        return None

    def load(self) -> MeshConfig:
        """Loads configuration from YAML and environment variables, then validates against MeshConfig model.

        Returns:
            Validated MeshConfig instance.

        Raises:
            ConfigError: If loading or parsing fails.
            ConfigValidationError: If validation fails.
        """
        raw_config: Dict[str, Any] = {}

        file_path = self.find_config_file()
        if file_path:
            raw_config = self.load_from_yaml(file_path)

        env_config = self.extract_env_vars()
        merged_config = self._deep_merge(raw_config, env_config)

        try:
            return MeshConfig(**merged_config)
        except ValidationError as e:
            raise ConfigValidationError(f"Configuration validation failed:\n{e}") from e


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    env_prefix: str = "AGENT_MESH_",
) -> MeshConfig:
    """Utility entry point function to load and validate MeshConfig in one call.

    Args:
        config_path: Optional path to YAML configuration file.
        env_prefix: Prefix for environment variable overrides.

    Returns:
        Instantiated and validated MeshConfig object.
    """
    loader = ConfigLoader(config_path=config_path, env_prefix=env_prefix)
    return loader.load()

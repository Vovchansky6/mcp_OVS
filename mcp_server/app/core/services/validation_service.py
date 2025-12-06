from typing import Dict, List, Optional, Any
import asyncio
import uuid
import structlog
from datetime import datetime
from pydantic import BaseModel

from app.core.models.mcp_protocol import MCPTool, BusinessRule

logger = structlog.get_logger()


class ValidationResult(BaseModel):
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = []


class ValidationService:
    """Service for validating business rules and data"""
    
    def __init__(self):
        self.business_rules: Dict[str, BusinessRule] = {}
        self._lock = asyncio.Lock()
    
    async def validate_tool_definition(self, tool: MCPTool) -> ValidationResult:
        """Validate tool definition against business rules"""
        warnings = []
        
        # Basic validation
        if not tool.name or not tool.name.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Tool name is required"
            )
        
        if not tool.description or not tool.description.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Tool description is required"
            )
        
        if not tool.input_schema:
            return ValidationResult(
                is_valid=False,
                error_message="Input schema is required"
            )
        
        # Validate input schema structure
        schema_validation = await self._validate_json_schema(tool.input_schema)
        if not schema_validation.is_valid:
            return schema_validation
        
        # Business rule validation
        applicable_rules = await self._get_applicable_rules("tool_definition")
        for rule in applicable_rules:
            rule_result = await self._apply_business_rule(rule, tool.dict())
            if not rule_result.is_valid:
                return rule_result
            warnings.extend(rule_result.warnings)
        
        return ValidationResult(is_valid=True, warnings=warnings)
    
    async def validate_tool_parameters(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> ValidationResult:
        """Validate tool parameters against tool schema"""
        # Get tool schema (this would typically come from the tool registry)
        # For now, we'll do basic validation
        
        if not isinstance(parameters, dict):
            return ValidationResult(
                is_valid=False,
                error_message="Parameters must be a dictionary"
            )
        
        # Apply business rules for parameter validation
        applicable_rules = await self._get_applicable_rules("tool_parameters")
        for rule in applicable_rules:
            rule_result = await self._apply_business_rule(
                rule, 
                {"tool_name": tool_name, "parameters": parameters}
            )
            if not rule_result.is_valid:
                return rule_result
        
        return ValidationResult(is_valid=True)
    
    async def validate_business_task(
        self, 
        domain: str, 
        task_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate business task against domain-specific rules"""
        warnings = []
        
        # Check if domain is supported
        supported_domains = ["finance", "healthcare", "retail", "manufacturing", "technology"]
        if domain not in supported_domains:
            return ValidationResult(
                is_valid=False,
                error_message=f"Domain '{domain}' is not supported. Supported domains: {supported_domains}"
            )
        
        # Apply domain-specific rules
        domain_rules = await self._get_domain_rules(domain)
        for rule in domain_rules:
            rule_result = await self._apply_business_rule(rule, task_data)
            if not rule_result.is_valid:
                return rule_result
            warnings.extend(rule_result.warnings)
        
        return ValidationResult(is_valid=True, warnings=warnings)
    
    async def add_business_rule(self, rule: BusinessRule) -> bool:
        """Add a new business rule"""
        async with self._lock:
            self.business_rules[rule.id] = rule
            logger.info("Business rule added", rule_id=rule.id, name=rule.name)
            return True
    
    async def remove_business_rule(self, rule_id: str) -> bool:
        """Remove a business rule"""
        async with self._lock:
            if rule_id not in self.business_rules:
                return False
            
            del self.business_rules[rule_id]
            logger.info("Business rule removed", rule_id=rule_id)
            return True
    
    async def get_business_rules(self, domain: str = None) -> List[BusinessRule]:
        """Get business rules, optionally filtered by domain"""
        async with self._lock:
            rules = list(self.business_rules.values())
            
            if domain:
                rules = [rule for rule in rules if rule.domain == domain]
            
            return rules
    
    async def _validate_json_schema(self, schema: Dict[str, Any]) -> ValidationResult:
        """Validate JSON schema structure"""
        if not isinstance(schema, dict):
            return ValidationResult(
                is_valid=False,
                error_message="Schema must be a dictionary"
            )
        
        # Basic JSON Schema validation
        if "type" not in schema:
            return ValidationResult(
                is_valid=False,
                error_message="Schema must have a 'type' property"
            )
        
        if schema["type"] not in ["object", "string", "number", "boolean", "array"]:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid schema type: {schema['type']}"
            )
        
        return ValidationResult(is_valid=True)
    
    async def _get_applicable_rules(self, context: str) -> List[BusinessRule]:
        """Get business rules applicable to a context"""
        # This would typically query a database or rule engine
        # For now, return some default rules
        
        default_rules = [
            BusinessRule(
                id="tool_name_validation",
                name="Tool Name Validation",
                domain="general",
                condition="tool.name matches pattern",
                action="validate tool name format",
                priority=1
            ),
            BusinessRule(
                id="parameter_size_limit",
                name="Parameter Size Limit",
                domain="general", 
                condition="parameters.size < 1MB",
                action="validate parameter size",
                priority=2
            )
        ]
        
        return [rule for rule in default_rules if rule.active]
    
    async def _get_domain_rules(self, domain: str) -> List[BusinessRule]:
        """Get domain-specific business rules"""
        async with self._lock:
            return [
                rule for rule in self.business_rules.values()
                if rule.domain == domain and rule.active
            ]
    
    async def _apply_business_rule(
        self, 
        rule: BusinessRule, 
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Apply a business rule to data"""
        try:
            # This would typically use a rule engine
            # For now, we'll implement some basic rule logic
            
            if rule.name == "Tool Name Validation":
                tool_name = data.get("name", "")
                if not tool_name.replace("_", "").replace("-", "").isalnum():
                    return ValidationResult(
                        is_valid=False,
                        error_message="Tool name must contain only alphanumeric characters, hyphens, and underscores"
                    )
            
            elif rule.name == "Parameter Size Limit":
                # Estimate parameter size
                import json
                param_size = len(json.dumps(data.get("parameters", {})))
                if param_size > 1024 * 1024:  # 1MB
                    return ValidationResult(
                        is_valid=False,
                        error_message="Parameters exceed 1MB size limit"
                    )
            
            # Add more rule implementations as needed
            
            return ValidationResult(is_valid=True)
            
        except Exception as e:
            logger.error(
                "Error applying business rule",
                rule_id=rule.id,
                error=str(e)
            )
            return ValidationResult(
                is_valid=False,
                error_message=f"Error applying rule '{rule.name}': {str(e)}"
            )